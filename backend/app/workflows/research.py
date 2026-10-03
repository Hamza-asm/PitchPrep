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
    WorkflowNode,
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
            "sources": [
                {"id": source.id, "type": source.type.value, "title": source.title, "url": str(source.url) if source.url else None}
                for source in state.sources
            ],
            "evidence_quotes": [quote.model_dump() for quote in state.evidence.excerpts] if state.evidence else [],
        }

    async def _parse(self, state: WorkflowState) -> WorkflowState:
        if not state.request.pasted_text:
            return updated(state, parsed=ParsedCompany(company_name=state.request.company_name))
        parsed = await self._generate(
            "parser", ParsedCompany, prompts.PARSER,
            {"pasted_text": state.request.pasted_text[: self.settings.parser_input_chars]}, state,
        )
        if not parsed.company_name:
            return updated(
                state, parsed=parsed, status=RunStatus.NEEDS_INPUT,
                error_code="company_not_identified",
                message="The pasted text does not identify a company. Check the text or remove it to use the company name and link you entered.",
            )
        return updated(state, parsed=parsed)

    async def _fetch_sources(self, state: WorkflowState) -> WorkflowState:
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
                retry_node="source_fetch",
                message="The link could not be read and no usable news was found. Paste company details or provide another link.",
            )
        return updated(state, sources=sources, limitations=notes, limited_data=limited)

    async def _collect(self, state: WorkflowState) -> WorkflowState:
        by_id = {source.id: source for source in state.sources}
        collector_input = {
            "company_name": state.request.company_name,
            "sources": [
                {"id": source.id, "type": source.type.value, "title": source.title,
                 "excerpt": source.excerpt[: self.settings.collector_excerpt_chars]}
                for source in state.sources
            ],
        }
        evidence = await self._generate("source_collector", CollectedEvidence, prompts.COLLECTOR, collector_input, state)
        valid = [
            quote for quote in evidence.excerpts
            if len(quote.quote) <= self.settings.evidence_quote_chars and quote_exists(quote, by_id)
        ]
        retained = valid[: self.settings.evidence_quote_limit]
        notes = list(state.limitations)
        if len(valid) != len(evidence.excerpts) or len(retained) != len(valid):
            notes.append("Some extracted excerpts were discarded because they were unmatched or exceeded the evidence limit.")
        return updated(state, evidence=CollectedEvidence(excerpts=retained), limited_data=state.limited_data or not retained, limitations=notes)

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
            {"company_name": state.request.company_name,
             "page": {"title": page.title, "excerpt": page.excerpt[: self.settings.collector_excerpt_chars]}}, state,
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

    @staticmethod
    def _prepare_stage_retry(state: WorkflowState, node: WorkflowNode) -> WorkflowState:
        downstream: dict[WorkflowNode, set[str]] = {
            "parser": {"parsed", "sources", "evidence", "analysis", "matches", "draft", "verification"},
            "source_fetch": {"sources", "evidence", "analysis", "matches", "draft", "verification"},
            "source_collector": {"evidence", "analysis", "matches", "draft", "verification"},
            "link_check": {"analysis", "matches", "draft", "verification"},
            "analyst": {"analysis", "matches", "draft", "verification"},
            "matcher": {"matches", "draft", "verification"},
            "writer": {"draft", "verification"},
            "verifier": {"verification"},
        }
        cleared: dict[str, Any] = {
            "parsed": None, "sources": [], "evidence": None, "analysis": None,
            "matches": None, "draft": None, "verification": None,
        }
        changes = {key: cleared[key] for key in downstream[node]}
        keep_previous_result = state.email_tone is not None and state.result is not None
        changes.update(
            status=RunStatus.RUNNING,
            error_code=None,
            message=None,
            retry_node=node,
            revision_attempts=0 if node in {"parser", "source_fetch", "source_collector", "link_check", "analyst", "matcher"} else state.revision_attempts,
            result=state.result if keep_previous_result else None,
        )
        if node in {"parser", "source_fetch"}:
            changes["limitations"] = []
            changes["limited_data"] = False
        elif "sources" in changes:
            changes["sources"] = []
        return updated(state, **changes)

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
            elif mode == "retry" and saved_state.retry_node:
                initial = self._prepare_stage_retry(saved_state, saved_state.retry_node)
            else:
                raise ValueError("Invalid workflow mode")
        latest = initial
        active_stage: Stage | None = None
        active_node: WorkflowNode | None = None
        graph = StateGraph(WorkflowState)

        def node(name: WorkflowNode, stage: Stage, operation: Callable[[WorkflowState], Awaitable[WorkflowState]]) -> Callable[[WorkflowState], Awaitable[WorkflowState]]:
            async def wrapped(state: WorkflowState) -> WorkflowState:
                nonlocal active_node, active_stage, latest
                active_node = name
                active_stage = stage
                ready = updated(state, retry_node=name)
                latest = ready
                if on_state:
                    await on_state(ready)
                if on_progress:
                    await on_progress(ProgressEvent(stage=stage, status="active", revision_attempt=state.revision_attempts))
                span = self.tracer.span(operation.__name__.lstrip("_")) if self.tracer else nullcontext()
                with span:
                    result = await operation(state)
                result = updated(
                    result,
                    retry_node=name if name == "source_fetch" and result.status == RunStatus.NEEDS_INPUT else None,
                )
                if on_progress:
                    await on_progress(ProgressEvent(stage=stage, status="complete", revision_attempt=result.revision_attempts))
                return result
            return wrapped

        for name, stage, operation in (
            ("parser", Stage.PARSING, self._parse),
            ("source_fetch", Stage.COLLECTING, self._fetch_sources),
            ("source_collector", Stage.COLLECTING, self._collect),
            ("link_check", Stage.COLLECTING, self._link_check),
            ("analyst", Stage.ANALYZING, self._analyze),
            ("matcher", Stage.MATCHING, self._match),
            ("writer", Stage.WRITING, self._write),
            ("verifier", Stage.VERIFYING, self._verify),
        ):
            graph.add_node(name, node(name, stage, operation))

        def revise(state: WorkflowState) -> WorkflowState:
            return updated(state, revision_attempts=state.revision_attempts + 1)

        def finish(state: WorkflowState) -> WorkflowState:
            result = finalize(state)
            if initial.email_tone is not None and initial.result:
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
            return "source_fetch" if state.status == RunStatus.RUNNING else END

        def after_fetch(state: WorkflowState) -> str:
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
        retry_entry: dict[WorkflowNode, str] | None = None
        if mode == "retry" and initial.retry_node:
            retry_entry = {
                "parser": "parser", "source_fetch": "source_fetch",
                "source_collector": "source_collector", "link_check": "link_check",
                "analyst": "analyst", "matcher": "matcher", "writer": "writer", "verifier": "verifier",
            }
        entry = {"research": "parser", "confirm": "analyst", "email": "writer"}.get(mode)
        if mode == "retry" and retry_entry and initial.retry_node:
            entry = retry_entry[initial.retry_node]
        if entry is None:
            raise ValueError("Invalid workflow mode")
        graph.add_edge(START, entry)
        graph.add_conditional_edges("parser", after_parse, ["source_fetch", END])
        graph.add_conditional_edges("source_fetch", after_fetch, ["source_collector", END])
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
            latest = updated(latest, status=RunStatus.FAILED, error_code=error.code,
                             message=error.message, retry_node=active_node or latest.retry_node)
            if on_state:
                await on_state(latest)
            if on_progress and active_stage:
                await on_progress(ProgressEvent(stage=active_stage, status="failed", revision_attempt=latest.revision_attempts))
        return latest
