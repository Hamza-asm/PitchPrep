"""Offline tests: real HTTP transports are forbidden, including tracing."""

import socket

import httpx
import pytest
import requests

from app.core.config import Settings


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Outbound network is forbidden in tests")

    async def async_blocked(*args, **kwargs):
        blocked()

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
def settings():
    nodes = ("parser", "source_collector", "link_check", "analyst", "matcher", "writer", "verifier", "eval_judge")
    return Settings(
        _env_file=None,
        app_env="test",
        frontend_origin="http://localhost:3000",
        groq_api_key="synthetic-test-secret",
        firecrawl_api_key="synthetic-test-secret",
        firecrawl_base_url="https://firecrawl.example/v2",
        supabase_url="https://supabase.example",
        supabase_service_role_key="synthetic-test-secret",
        langsmith_project="offline-tests",
        langsmith_tracing=False,
        retry_base_seconds=0,
        retry_max_seconds=0,
        **{f"groq_model_{node}": f"test-{node}" for node in nodes},
    )
