import json
from uuid import uuid4

import httpx
import pytest

from app.services.repository import RepositoryError, SupabaseRepository


async def test_backend_database_headers_and_base_url(settings, monkeypatch):
    captured = {}
    original = httpx.AsyncClient

    def factory(**kwargs):
        captured.update(kwargs)
        kwargs["transport"] = httpx.MockTransport(lambda req: httpx.Response(200, json=[]))
        return original(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    repo = SupabaseRepository(settings)
    try:
        assert await repo.get_seller() is None
        assert captured["base_url"] == "https://supabase.example/rest/v1/"
        assert captured["headers"]["apikey"] == "synthetic-test-secret"
        assert captured["headers"]["Authorization"] == "Bearer synthetic-test-secret"
    finally:
        await repo.aclose()


async def test_backend_database_normalizes_rest_api_url(settings, monkeypatch):
    captured = {}
    original = httpx.AsyncClient

    def factory(**kwargs):
        captured.update(kwargs)
        kwargs["transport"] = httpx.MockTransport(lambda req: httpx.Response(200, json=[]))
        return original(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
    repo = SupabaseRepository(settings.model_copy(update={"supabase_url": "https://supabase.example/rest/v1/"}))
    try:
        await repo.get_seller()
        assert captured["base_url"] == "https://supabase.example/rest/v1/"
    finally:
        await repo.aclose()


@pytest.mark.parametrize("status", [401, 403, 500])
async def test_repository_does_not_leak_provider_errors(settings, status):
    async with httpx.AsyncClient(base_url="https://db.example/", transport=httpx.MockTransport(lambda req: httpx.Response(status, json={"message": "private detail"}))) as client:
        with pytest.raises(RepositoryError) as caught:
            await SupabaseRepository(settings, client).get_seller()
    assert "private detail" not in str(caught.value)


async def test_expired_lease_stops_writes(settings):
    captured = []

    def handle(req):
        captured.append((req.url.path, json.loads(req.content)))
        return httpx.Response(200, json=False)

    async with httpx.AsyncClient(base_url="https://db.example/", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RepositoryError, match="interrupted"):
            await SupabaseRepository(settings, client).save_job(uuid4(), uuid4(), 120)
    assert captured[0][0] == "/rpc/pitchprep_save_job"
    assert captured[0][1]["p_finish"] is False
