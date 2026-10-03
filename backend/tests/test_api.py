"""API and worker integration against an in-memory repository and fake providers."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
import pytest

from app.main import create_app
from app.schemas.api import BriefRecord
from app.schemas.research import WorkflowState
from app.services.repository import RepositoryError
from app.services.worker import ResearchWorker
from app.workflows.research import ResearchWorkflow
from test_workflow import FakeModel, FakeWeb, SELLER, request


class MemoryRepository:
    def __init__(self):
        self.seller = None
        self.rows = {}
        self.feedback_values = {}

    async def get_seller(self):
        return self.seller

    async def save_seller(self, seller):
        self.seller = seller
        return seller

    async def get(self, key):
        if key not in self.rows:
            raise RepositoryError("not_found", "Brief not found.", 404)
        return self.rows[key]

    async def create(self, key, value, seller):
        if key in self.rows:
            if self.rows[key].request != value:
                raise RepositoryError("idempotency_conflict", "Different input.", 409)
            return self.rows[key]
        now = datetime.now(timezone.utc)
        self.rows[key] = BriefRecord(id=key, request=value, seller=seller, status="queued", created_at=now, updated_at=now)
        return self.rows[key]

    async def list_briefs(self, limit, offset):
        return [{"id": row.id, "request": row.request.model_dump(), "status": row.status,
                 "limited_data": row.result.limited_data if row.result else None, "created_at": row.created_at}
                for row in list(self.rows.values())[offset:offset + limit]]

    async def claim(self, token, seconds):
        if any(row.status == "running" for row in self.rows.values()):
            return None
        row = next((row for row in self.rows.values() if row.status == "queued"), None)
        if row:
            row.status, row.lease_token, row.trace_id = "running", token, token
            row.version += 1
        return row

    async def save_job(self, key, token, seconds, *, state=None, event=None, finish=False):
        row = await self.get(key)
        if row.lease_token != token or row.status != "running":
            raise RepositoryError("lease_lost", "Lease lost.", 409)
        if event:
            row.progress.append(event)
        if state:
            row.state = state
        if finish:
            row.status = state.status.value
            row.error_code, row.message = state.error_code, state.message
            if state.result and state.status == "completed":
                row.result = state.result
                row.result_trace_id = token
                row.email_edit = None
            row.lease_token = None
        row.version += 1

    async def enqueue_again(self, key, version, kind, tone=None):
        row = await self.get(key)
        allowed = row.status == "needs_confirmation" if kind == "confirm" else row.result and row.status in ("completed", "failed")
        if row.version != version or not allowed:
            raise RepositoryError("conflict", "Refresh first.", 409)
        row.status, row.job_kind, row.tone = "queued", kind, tone
        row.progress = []
        row.version += 1
        return row

    async def save_email(self, key, version, email):
        row = await self.get(key)
        if row.version != version or row.status not in ("completed", "failed") or not row.result:
            raise RepositoryError("conflict", "Refresh first.", 409)
        row.email_edit = email
        row.version += 1
        return row

    async def feedback(self, key, value, trace_id):
        self.feedback_values[key] = (value, trace_id)


@pytest.fixture
def repo():
    return MemoryRepository()


async def test_api_round_trip_and_stream(settings, repo):
    web, model = FakeWeb(), FakeModel()
    workflow = ResearchWorkflow(settings, model, web)
    app = create_app(settings, repository=repo, workflow=workflow)
    worker = ResearchWorker(settings, repo, workflow)
    key = uuid4()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/seller-profile")).json() is None
        assert (await client.post("/api/briefs", json=request().model_dump(mode="json"))).status_code == 409
        assert (await client.put("/api/seller-profile", json=SELLER.model_dump())).status_code == 200
        created = await client.post("/api/briefs", json=request().model_dump(mode="json"), headers={"Idempotency-Key": str(key)})
        assert created.status_code == 202
        assert model.calls == {}  # Enqueueing does not call providers in the request.
        duplicate = await client.post("/api/briefs", json=request().model_dump(mode="json"), headers={"Idempotency-Key": str(key)})
        assert duplicate.json()["id"] == str(key)
        assert len(repo.rows) == 1
        assert await worker.run_once()
        detail = (await client.get(f"/api/briefs/{key}")).json()
        assert detail["status"] == "completed"
        assert "state" not in detail and "lease_token" not in detail and "seller" not in detail
        history = (await client.get("/api/briefs")).json()
        assert history["items"][0]["company_name"] == "Fixture Co"
        stream = await client.get(f"/api/briefs/{key}/stream", headers={"Last-Event-ID": str(detail["version"])})
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "event: result" in stream.text
        assert '"status":"completed"' in stream.text
        assert len(web.urls) == 1
        assert (await client.post(f"/api/briefs/{key}/feedback", json={"rating": 1, "comment": "Useful"})).status_code == 204
        assert repo.feedback_values[key][0].rating == 1


async def test_confirm_and_regenerate_do_not_recollect(settings, repo):
    await repo.save_seller(SELLER)
    web = FakeWeb(text="Other business")
    model = FakeModel(mismatch=True)
    workflow = ResearchWorkflow(settings, model, web)
    worker = ResearchWorker(settings, repo, workflow)
    row = await repo.create(uuid4(), request(), SELLER)
    app = create_app(settings, repository=repo, workflow=workflow)
    await worker.run_once()
    assert row.status == "needs_confirmation"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        confirmed = await client.post(f"/api/briefs/{row.id}/confirm-link", json={"confirmed": True, "expected_version": row.version})
        assert confirmed.status_code == 202
        assert (await client.post(f"/api/briefs/{row.id}/confirm-link", json={"confirmed": True, "expected_version": row.version})).status_code == 409
        await worker.run_once()
        assert row.status == "completed"
        claims = row.result.claims
        edit = await client.put(f"/api/briefs/{row.id}/email", json={"subject": "My subject", "body": "My edited message", "expected_version": row.version})
        assert edit.status_code == 200
        assert edit.json()["email_edit"]["subject"] == "My subject"
        stale = await client.put(f"/api/briefs/{row.id}/email", json={"subject": "Old", "body": "Old", "expected_version": 0})
        assert stale.status_code == 409
        regenerated = await client.post(f"/api/briefs/{row.id}/email/regenerate", json={"tone": "friendly", "expected_version": row.version})
        assert regenerated.status_code == 202
        await worker.run_once()
        assert row.status == "completed"
        assert row.email_edit is None
        assert row.result.claims == claims
        assert len(web.urls) == 1
        assert model.calls["analyst"] == 1
        assert model.calls["writer"] == 2


async def test_validation_and_not_found_do_not_reflect_input(settings, repo):
    app = create_app(settings, repository=repo)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/briefs", json={"company_name": "Fixture", "target_url": "private-invalid-sentinel"})
        assert response.status_code == 422
        assert "private-invalid-sentinel" not in response.text
        assert (await client.get(f"/api/briefs/{uuid4()}/stream")).status_code == 404
        assert (await client.get("/api/briefs?limit=101")).status_code == 422


async def test_shutdown_cancels_work_without_retry(settings, repo):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class SlowWorkflow:
        async def run(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    row = await repo.create(uuid4(), request(), SELLER)
    worker = ResearchWorker(settings, repo, SlowWorkflow())
    worker.start()
    await asyncio.wait_for(started.wait(), 1)
    await worker.stop()
    assert cancelled.is_set()
    assert row.status == "failed"
    assert row.error_code == "run_interrupted"
    assert not await worker.run_once()


async def test_repository_outage_returns_safe_error(settings, repo):
    async def fail():
        raise RepositoryError("database_unavailable", "Saved data is unavailable.")

    repo.get_seller = fail
    app = create_app(settings, repository=repo)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/seller-profile")
    assert response.status_code == 503
    assert response.json()["error"] == "database_unavailable"


async def test_app_lifespan_processes_queued_work(settings, repo):
    row = await repo.create(uuid4(), request(), SELLER)
    app = create_app(settings, repository=repo, workflow=ResearchWorkflow(settings, FakeModel(), FakeWeb()))
    async with app.router.lifespan_context(app):
        async with asyncio.timeout(2):
            while row.status != "completed":
                await asyncio.sleep(0.01)
    assert app.state.worker.task.done()
