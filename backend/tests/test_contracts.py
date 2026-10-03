import httpx
import pytest
from pydantic import ValidationError

from app.main import create_app
from app.schemas.research import Draft, ResearchRequest, Source, Verification
from app.workflows.verification import check_verdicts


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://localhost", "http://10.0.0.1", "https://user:password@fixture.example", "https://www.google.com/maps/place/test", "https://maps.app.goo.gl/test"])
def test_rejects_private_or_maps_targets(url):
    with pytest.raises(ValidationError):
        ResearchRequest(company_name="Fixture", target_url=url)


@pytest.mark.parametrize("fault", ["missing", "duplicate", "invented_quote", "wrong_basis", "unknown_source"])
def test_verification_fails_closed(fault):
    source = Source(id="page", type="scraped", title="Fixture", url="https://fixture.example", excerpt="Fixture provides repairs.")
    draft = Draft.model_validate({"claims": [{"id": "claim", "section": "snapshot", "text": "Fixture provides repairs.", "source_ids": ["missing" if fault == "unknown_source" else "page"]}], "email": {"subject": {"id": "subject", "text": "Hello"}, "paragraphs": [{"id": "body", "text": "May we speak?"}]}})
    verdict = {"unit_id": "claim", "supported": True, "basis": "non_factual" if fault == "wrong_basis" else "sources", "reason": "Fixture", "evidence": [{"source_id": "page", "quote": "Invented quote" if fault == "invented_quote" else source.excerpt}]}
    report = Verification.model_validate({"verdicts": [] if fault == "missing" else [verdict, verdict] if fault == "duplicate" else [verdict]})
    checked = check_verdicts(draft, report, [source])
    assert len(checked.verdicts) == 3
    assert all(not item.supported for item in checked.verdicts)


async def test_health_is_local_and_cors_is_specific(settings):
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health", headers={"origin": "http://localhost:3000"})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        other = await client.get("/api/health", headers={"origin": "https://untrusted.example"})
        assert "access-control-allow-origin" not in other.headers


def test_settings_repr_hides_secrets(settings):
    assert "synthetic-test-secret" not in repr(settings)


async def test_outbound_http_is_blocked():
    async with httpx.AsyncClient() as client:
        with pytest.raises(AssertionError, match="Outbound network"):
            await client.get("https://must-not-connect.example")
