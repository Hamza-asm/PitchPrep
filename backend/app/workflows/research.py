"""Fixed research graph, including link confirmation and a capped Writer loop."""

import re
from collections.abc import Awaitable, Callable
from contextlib import nullcontext
from typing import Any
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from app.core.config import Settings
from app.core.errors import ServiceError
from app.schemas.research import (
    Analysis,
    CollectedEvidence,
    Draft,
    LinkAssessment,
    Matches,
    ParsedCompany,
    ProgressEvent,
    ResearchRequest,
    RunStatus,
    SellerProfile,
    Source,
    SourceType,
    Stage,
    Verification,
    WorkflowState,
)
from app.services.ports import ModelService, Output, WebService
from app.services.tracing import WorkflowTracer
from app.workflows import prompts
from app.workflows.verification import check_verdicts, finalize, quote_exists

MAX_WRITER_REVISIONS = 2
ProgressCallback = Callable[[ProgressEvent], Awaitable[None]]
StateCallback = Callable[[WorkflowState], Awaitable[None]]


def updated(state: WorkflowState, **changes: Any) -> WorkflowState:
    return WorkflowState.model_validate({**state.model_dump(), **changes})


class ResearchWorkflow:
    def __init__(
        self,
        settings: Settings,
        model: ModelService,
        web: WebService,
        tracer: WorkflowTracer | None = None,
    ) -> None:
        self.settings = settings
        self.model = model
        self.web = web
        self.tracer = tracer

    async def _generate(
        self,
        node: str,
        schema: type[Output],
        instructions: str,
        payload: dict[str, Any],
        state: WorkflowState,
    ) -> Output:
        return await self.model.generate(
            node=node,
            schema=schema,
            instructions=instructions,
            payload=payload,
            validation_context={"source_ids": {source.id for source in state.sources}},
        )

    @staticmethod
    def _evidence_payload(state: WorkflowState) -> dict[str, Any]:
        return {
            "company_name": state.request.company_name,
            "sources": [source.model_dump(mode="json") for source in state.sources],
            "selected_excerpts": state.evidence.model_dump() if state.evidence else None,
        }

    async def _parse(self, state: WorkflowState) -> WorkflowState:
        if not state.request.pasted_text:
            return updated(state, parsed=ParsedCompany(company_name=state.request.company_name))
        parsed = await self._generate(
            "parser", ParsedCompany, prompts.PARSER,
            {"pasted_text": state.request.pasted_text}, state,
        )
        if not parsed.company_name:
            return updated(
                state, parsed=parsed, status=RunStatus.NEEDS_INPUT,
                error_code="company_not_identified",
                message="The pasted text does not identify a company. Check the text or remove it to use the company name and link you entered.",
            )
        return updated(state, parsed=parsed)

    async def _collect(self, state: WorkflowState) -> WorkflowState:
        sources: list[Source] = []
        notes = list(state.limitations)
        limited = False
        if state.request.pasted_text:
            sources.append(Source(id="user_provided", type=SourceType.USER_PROVIDED, title="User-provided text", excerpt=state.request.pasted_text))
        try:
            # The parser's extracted website and model outputs never select this URL.
            page = await self.web.scrape(str(state.request.target_url))
            if page.text.strip():
                sources.append(Source(id="supplied_page", type=SourceType.SCRAPED, title=page.title, url=state.request.target_url, excerpt=page.text[: self.settings.source_max_chars]))
            else:
                raise ServiceError("scrape_unavailable", "The supplied page contained no readable text.")
        except ServiceError:
            limited = True
            notes.append("The supplied page could not be read; available pasted text and news are used instead.")
        try:
            news = await self.web.news(state.request.company_name)
            for index, document in enumerate(news[: self.settings.news_result_limit]):
                if document.text.strip():
                    sources.append(Source(id=f"news_{index + 1}", type=SourceType.SEARCH, title=document.title, url=document.url, excerpt=document.text[: self.settings.source_max_chars]))
        except ServiceError:
            limited = True
            notes.append("Recent news could not be collected.")
        if not sources:
            return updated(
                state, limited_data=True, limitations=notes, status=RunStatus.NEEDS_INPUT,
                error_code="no_sources",
                message="The link could not be read and no usable news was found. Paste company details or provide another link.",
            )
        collected = updated(state, sources=sources, limitations=notes, limited_data=limited)
        evidence = await self._generate("source_collector", CollectedEvidence, prompts.COLLECTOR, self._evidence_payload(collected), collected)
        by_id = {source.id: source for source in sources}
        valid = [quote for quote in evidence.excerpts if quote_exists(quote, by_id)]
        if len(valid) != len(evidence.excerpts):
            notes.append("Some extracted excerpts were discarded because they did not match the original source text.")
        return updated(collected, evidence=CollectedEvidence(excerpts=valid), limited_data=limited or not valid, limitations=notes)

    async def _link_check(self, state: WorkflowState) -> WorkflowState:
        if state.request.link_confirmed:
            return state
        page = next((source for source in state.sources if source.type == SourceType.SCRAPED), None)
        if page is None:
            return state  # Unreadable social pages use the documented limited-data path.
        normal_name = " ".join(re.findall(r"\w+", state.request.company_name.casefold()))
        normal_page = " ".join(re.findall(r"\w+", page.excerpt.casefold()))
        if normal_name and f" {normal_name} " in f" {normal_page} ":
            return state
        assessment = await self._generate(
            "link_check", LinkAssessment, prompts.LINK_CHECK,
            {"company_name": state.request.company_name, "page": page.model_dump(mode="json")}, state,
        )
        if not assessment.matches:
            return updated(
                state, status=RunStatus.NEEDS_CONFIRMATION, error_code="link_mismatch",
                message="This link does not appear to match the company. Confirm that it is the right link before continuing.",
            )
        return state

    async def _analyze(self, state: WorkflowState) -> WorkflowState:
        analysis = await self._generate("analyst", Analysis, prompts.ANALYST, self._evidence_payload(state), state)
        return updated(state, analysis=analysis)

    async def _match(self, state: WorkflowState) -> WorkflowState:
        matches = await self._generate(
            "matcher", Matches, prompts.MATCHER,
            {**self._evidence_payload(state), "analysis": state.analysis.model_dump() if state.analysis else None, "seller": state.seller.model_dump()}, state,
        )
        return updated(state, matches=matches)

    async def _write(self, state: WorkflowState) -> WorkflowState:
        draft = await self._generate(
            "writer", Draft, prompts.WRITER,
            {
                **self._evidence_payload(state), "seller": state.seller.model_dump(),
                "analysis": state.analysis.model_dump() if state.analysis else None,
                "matches": state.matches.model_dump() if state.matches else None,
                "previous_draft": state.draft.model_dump() if state.draft else None,
                "verifier_feedback": state.verification.model_dump() if state.verification else None,
                "revision_attempt": state.revision_attempts,
                "email_tone": state.email_tone,
            }, state,
        )
        if state.email_tone is not None and state.result is not None:
            # Only email units are regenerated/reverified; saved claims stay intact.
            draft = Draft.model_validate({
                **draft.model_dump(),
                "claims": [],
            })
        return updated(state, draft=draft)

    async def _verify(self, state: WorkflowState) -> WorkflowState:
        if state.draft is None:
            raise ValueError("Writer must run before Verifier")
        report = await self._generate(
            "verifier", Verification, prompts.VERIFIER,
            {**self._evidence_payload(state), "seller": state.seller.model_dump(), "units": [unit.model_dump() for unit in state.draft.units()]}, state,
        )
        return updated(state, verification=check_verdicts(state.draft, report, state.sources))

    async def run(
        self, request: ResearchRequest, seller: SellerProfile, *, on_progress: ProgressCallback | None = None,
        on_state: StateCallback | None = None, saved_state: WorkflowState | None = None,
        mode: str = "research", tone: str | None = None, trace_id: UUID | None = None,
    ) -> WorkflowState:
        initial = WorkflowState(request=request, seller=seller)
        if mode != "research":
            if saved_state is None:
                raise ValueError("A saved state is required to resume or regenerate")
            if mode == "confirm":
                initial = updated(saved_state, request=request.model_copy(update={"link_confirmed": True}), status=RunStatus.RUNNING, error_code=None, message=None)
            elif mode == "email" and saved_state.result:
                initial = updated(saved_state, status=RunStatus.RUNNING, error_code=None, message=None,
                                  revision_attempts=0, verification=None, email_tone=tone)
            else:
                raise ValueError("Invalid workflow mode")
        latest = initial
        active_stage: Stage | None = None
        graph = StateGraph(WorkflowState)

        def node(stage: Stage, operation: Callable[[WorkflowState], Awaitable[WorkflowState]]) -> Callable[[WorkflowState], Awaitable[WorkflowState]]:
            async def wrapped(state: WorkflowState) -> WorkflowState:
                nonlocal active_stage
                active_stage = stage
                if on_progress:
                    await on_progress(ProgressEvent(stage=stage, status="active", revision_attempt=state.revision_attempts))
                span = self.tracer.span(operation.__name__.lstrip("_")) if self.tracer else nullcontext()
                with span:
                    result = await operation(state)
                if on_progress:
                    await on_progress(ProgressEvent(stage=stage, status="complete", revision_attempt=result.revision_attempts))
                return result
            return wrapped

        for name, stage, operation in (
            ("parser", Stage.PARSING, self._parse),
            ("source_collector", Stage.COLLECTING, self._collect),
            ("link_check", Stage.COLLECTING, self._link_check),
            ("analyst", Stage.ANALYZING, self._analyze),
            ("matcher", Stage.MATCHING, self._match),
            ("writer", Stage.WRITING, self._write),
            ("verifier", Stage.VERIFYING, self._verify),
        ):
            graph.add_node(name, node(stage, operation))

        def revise(state: WorkflowState) -> WorkflowState:
            return updated(state, revision_attempts=state.revision_attempts + 1)

        def finish(state: WorkflowState) -> WorkflowState:
            result = finalize(state)
            if mode == "email" and initial.result:
                result = result.model_copy(update={
                    "claims": initial.result.claims,
                    "limited_data": initial.result.limited_data or any(not v.supported for v in state.verification.verdicts),
                    "evidence_limitations": list(dict.fromkeys([
                        *initial.result.evidence_limitations,
                        *[note for note in result.evidence_limitations if note != "There was not enough evidence for a verified company brief."],
                    ])),
                })
            return updated(state, result=result, status=RunStatus.COMPLETED)

        def after_parse(state: WorkflowState) -> str:
            return "source_collector" if state.status == RunStatus.RUNNING else END

        def after_collect(state: WorkflowState) -> str:
            return "link_check" if state.status == RunStatus.RUNNING else END

        def after_link(state: WorkflowState) -> str:
            return "analyst" if state.status == RunStatus.RUNNING else END

        def after_verify(state: WorkflowState) -> str:
            unsupported = state.verification is None or any(not verdict.supported for verdict in state.verification.verdicts)
            return "revise" if unsupported and state.revision_attempts < MAX_WRITER_REVISIONS else "finalize"

        graph.add_node("revise", revise)
        graph.add_node("finalize", finish)
        graph.add_edge(START, {"research": "parser", "confirm": "analyst", "email": "writer"}[mode])
        graph.add_conditional_edges("parser", after_parse, ["source_collector", END])
        graph.add_conditional_edges("source_collector", after_collect, ["link_check", END])
        graph.add_conditional_edges("link_check", after_link, ["analyst", END])
        graph.add_edge("analyst", "matcher")
        graph.add_edge("matcher", "writer")
        graph.add_edge("writer", "verifier")
        graph.add_conditional_edges("verifier", after_verify, ["revise", "finalize"])
        graph.add_edge("revise", "writer")
        graph.add_edge("finalize", END)
        compiled = graph.compile()
        context = self.tracer.span("pitchprep_research", run_id=trace_id) if self.tracer else tracing_context(enabled=False)
        try:
            with context:
                async for value in compiled.astream(initial, config={"recursion_limit": 32}, stream_mode="values"):
                    latest = WorkflowState.model_validate(value)
                    if on_state:
                        await on_state(latest)
        except ServiceError as error:
            latest = updated(latest, status=RunStatus.FAILED, error_code=error.code, message=error.message)
            if on_progress and active_stage:
                await on_progress(ProgressEvent(stage=active_stage, status="failed", revision_attempt=latest.revision_attempts))
        return latest
