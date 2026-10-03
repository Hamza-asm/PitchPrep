import asyncio
import json

import httpx
import pytest
from groq import AsyncGroq

from app.core.errors import InvalidModelOutput, ServiceError
from app.schemas.research import LinkAssessment
from app.services.firecrawl import FirecrawlService
from app.services.groq import GroqService


async def test_firecrawl_fixed_scrape_and_news_only(settings):
    sent = []

    def handle(req):
        sent.append((req.url.path, json.loads(req.content)))
        data = {"markdown": "Fixture text", "metadata": {"title": "Fixture"}} if req.url.path.endswith("scrape") else {"news": [{"url": "https://news.example/story", "title": "Story", "snippet": "Fixture news"}]}
        return httpx.Response(200, json={"success": True, "data": data})

    async with httpx.AsyncClient(base_url="https://firecrawl.example/v2/", transport=httpx.MockTransport(handle)) as client:
        service = FirecrawlService(settings, client)
        assert (await service.scrape("https://fixture.example/page")).text == "Fixture text"
        assert len(await service.news("Fixture Co")) == 1
    assert sent[0] == ("/v2/scrape", {"url": "https://fixture.example/page", "formats": ["markdown"], "onlyMainContent": True})
    assert sent[1][1]["sources"] == ["news"]
    assert "scrapeOptions" not in sent[1][1]
    assert len(sent) == 2


@pytest.mark.parametrize("status,expected", [(401, 1), (429, 2), (500, 2)])
async def test_firecrawl_retries_are_bounded(settings, status, expected):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(status, json={"error": "sensitive-provider-body"})

    async with httpx.AsyncClient(base_url="https://firecrawl.example/", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ServiceError) as caught:
            await FirecrawlService(settings, client).scrape("https://fixture.example")
    assert len(calls) == expected
    assert "sensitive" not in str(caught.value)


async def test_long_retry_after_does_not_retry_early(settings):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(429, headers={"retry-after": "60"})

    async with httpx.AsyncClient(base_url="https://firecrawl.example/", transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(ServiceError):
            await FirecrawlService(settings, client).news("Fixture")
    assert len(calls) == 1


async def test_firecrawl_concurrency_cap(settings):
    active = peak = 0

    async def handle(req):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return httpx.Response(200, json={"success": True, "data": {"news": []}})

    async with httpx.AsyncClient(base_url="https://firecrawl.example/", transport=httpx.MockTransport(handle)) as client:
        service = FirecrawlService(settings, client)
        await asyncio.gather(*(service.news("Fixture") for _ in range(4)))
    assert peak == 1


@pytest.mark.parametrize("recover", [True, False])
async def test_groq_validates_output_and_caps_schema_retries(settings, recover):
    sent = []

    def handle(req):
        sent.append(json.loads(req.content))
        content = json.dumps({"matches": True, "reason": "Fixture"}) if recover and len(sent) == 2 else "{}"
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0, "model": "test-link_check", "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        client = AsyncGroq(api_key="synthetic", base_url="https://groq.example/", max_retries=0, http_client=http)
        service = GroqService(settings, client)
        if recover:
            assert (await service.generate(node="link_check", schema=LinkAssessment, instructions="Test", payload={})).matches
        else:
            with pytest.raises(InvalidModelOutput):
                await service.generate(node="link_check", schema=LinkAssessment, instructions="Test", payload={})
    assert len(sent) == 2
    assert sent[0]["model"] == "test-link_check"
    assert sent[0]["response_format"]["json_schema"]["strict"]


async def test_groq_rate_limit_attempt_cap(settings):
    calls = []

    def handle(req):
        calls.append(req)
        return httpx.Response(429, json={"error": {"message": "private-provider-detail"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
        client = AsyncGroq(api_key="synthetic", base_url="https://groq.example/", max_retries=0, http_client=http)
        with pytest.raises(ServiceError) as caught:
            await GroqService(settings, client).generate(node="link_check", schema=LinkAssessment, instructions="Test", payload={})
    assert len(calls) == 2
    assert caught.value.code == "rate_limited"
    assert "private-provider-detail" not in str(caught.value)
