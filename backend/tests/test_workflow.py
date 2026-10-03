"""Synthetic fixtures exercise the real graph without using provider clients."""

from collections import Counter

import pytest

from app.core.errors import ServiceError
from app.schemas.research import Analysis, Finding, ResearchRequest, SellerProfile
from app.services.ports import Document
from app.workflows.research import ResearchWorkflow


class FakeWeb:
    def __init__(self, blocked=False, text="Fixture Co provides repair services."):
        self.blocked = blocked
        self.text = text
        self.urls = []

    async def scrape(self, url):
        self.urls.append(url)
        if self.blocked:
            raise ServiceError("blocked", "Synthetic blocked page")
        return Document(url=url, title="Fixture Co", text=self.text)

    async def news(self, company_name):
        return []


class FakeModel:
    def __init__(self, *, unsupported=False, missing_name=False, mismatch=False, missing_verdict=False):
        self.calls = Counter()
        self.unsupported = unsupported
        self.missing_name = missing_name
        self.mismatch = mismatch
        self.missing_verdict = missing_verdict

    async def generate(self, *, node, schema, instructions, payload, validation_context=None):
        self.calls[node] += 1
        sources = payload.get("sources", [])
        evidence_quotes = payload.get("evidence_quotes", [])
        source_id = sources[0]["id"] if sources else "supplied_page"
        quote = evidence_quotes[0]["quote"] if evidence_quotes else "Fixture Co provides repair services."
        if node == "parser":
            value = {"company_name": None if self.missing_name else "Fixture Co", "website": "https://ignored.example/"}
        elif node == "source_collector":
            value = {"excerpts": [{"source_id": source_id, "quote": quote}]}
        elif node == "link_check":
            value = {"matches": not self.mismatch, "reason": "Synthetic assessment"}
        elif node == "analyst":
            value = {"findings": [{"category": "snapshot", "text": quote, "source_ids": [source_id]}]}
        elif node == "matcher":
            value = {"opportunities": []}
        elif node == "writer":
            value = {
                "claims": [{"id": "fact", "section": "snapshot", "text": quote, "source_ids": [source_id]}],
                "email": {
                    "subject": {"id": "subject", "text": "An introduction", "source_ids": []},
                    "paragraphs": [{"id": "body", "text": quote, "source_ids": [source_id]}],
                },
            }
        else:
            value = {"verdicts": [
                {"unit_id": unit["id"], "supported": not self.unsupported or unit["id"] == "subject",
                 "basis": "sources" if unit["source_ids"] else "non_factual", "reason": "Synthetic verdict",
                 "evidence": [{"source_id": source_id, "quote": quote}] if unit["source_ids"] else []}
                for unit in payload["units"] if not self.missing_verdict or unit["id"] == "subject"
            ]}
        return schema.model_validate(value, context=validation_context)


def request(**overrides):
    return ResearchRequest(company_name="Fixture Co", target_url="https://fixture.example/exact-page", **overrides)


SELLER = SellerProfile(offering="Maintenance software", ideal_customer="Repair businesses")


def test_analysis_accepts_legacy_checkpoint_with_nine_findings():
    finding = {"category": "snapshot", "text": "Fixture Co provides repair services.", "source_ids": ["supplied_page"]}
    analysis = Analysis.model_validate({"findings": [Finding.model_validate(finding) for _ in range(9)]})
    assert len(analysis.findings) == 9


async def test_full_graph_and_progress(settings):
    model, web, events = FakeModel(), FakeWeb(), []

    async def progress(event):
        events.append(event)

    result = await ResearchWorkflow(settings, model, web).run(request(pasted_text="Fixture Co provides repair services."), SELLER, on_progress=progress)
    assert result.status == "completed"
    assert result.result.verification.removed_units == 0
    assert result.result.claims[0].verification_status == "verified"
    assert web.urls == ["https://fixture.example/exact-page"]
    assert model.calls["writer"] == model.calls["verifier"] == 1
    assert {event.stage.value for event in events} == {"parsing", "collecting", "analyzing", "matching", "writing", "verifying"}


@pytest.mark.parametrize("missing", [False, True])
async def test_two_revisions_then_prunes_brief_and_email(settings, missing):
    model = FakeModel(unsupported=not missing, missing_verdict=missing)
    result = await ResearchWorkflow(settings, model, FakeWeb()).run(request(), SELLER)
    assert result.status == "completed"
    assert model.calls["writer"] == model.calls["verifier"] == 3
    assert result.revision_attempts == 2
    assert result.result.claims == []
    assert result.result.email.paragraphs == []
    assert result.result.verification.removed_units == 2
    assert result.result.limited_data


async def test_missing_name_stops_before_collection(settings):
    web = FakeWeb()
    result = await ResearchWorkflow(settings, FakeModel(missing_name=True), web).run(request(pasted_text="Open weekdays"), SELLER)
    assert result.status == "needs_input"
    assert not web.urls


async def test_mismatch_requires_confirmation(settings):
    model = FakeModel(mismatch=True)
    result = await ResearchWorkflow(settings, model, FakeWeb(text="Other business")).run(request(), SELLER)
    assert result.status == "needs_confirmation"
    assert model.calls["analyst"] == 0


async def test_explicit_confirmation_continues(settings):
    model = FakeModel(mismatch=True)
    result = await ResearchWorkflow(settings, model, FakeWeb(text="Other business")).run(request(link_confirmed=True), SELLER)
    assert result.status == "completed"
    assert model.calls["link_check"] == 0


async def test_blocked_page_uses_pasted_text(settings):
    result = await ResearchWorkflow(settings, FakeModel(), FakeWeb(blocked=True)).run(request(pasted_text="Fixture Co provides repair services."), SELLER)
    assert result.status == "completed"
    assert result.result.limited_data
    assert [source.type for source in result.sources] == ["user_provided"]
    assert result.sources[0].url is None


async def test_no_evidence_stops(settings):
    model = FakeModel()
    result = await ResearchWorkflow(settings, model, FakeWeb(blocked=True)).run(request(), SELLER)
    assert result.status == "needs_input"
    assert model.calls["writer"] == 0


async def test_provider_failure_keeps_input(settings):
    class FailingModel(FakeModel):
        async def generate(self, **kwargs):
            raise ServiceError("rate_limited", "Try again later")

    result = await ResearchWorkflow(settings, FailingModel(), FakeWeb()).run(request(), SELLER)
    assert result.status == "failed"
    assert result.error_code == "rate_limited"
    assert result.request == request()
