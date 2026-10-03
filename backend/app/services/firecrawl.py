"""Only scrape the user's supplied URL; search adds news snippets without crawling."""

import asyncio
from typing import Any

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.core.config import Settings
from app.core.errors import ServiceError
from app.schemas.research import public_url
from app.services.ports import Document
from app.services.retry import retry_after_seconds, with_backoff


class FirecrawlService:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(
            base_url=str(settings.firecrawl_base_url).rstrip("/") + "/",
            headers={"Authorization": f"Bearer {settings.firecrawl_api_key.get_secret_value()}"},
            timeout=settings.provider_timeout_seconds,
            follow_redirects=False,
        )
        self._semaphore = asyncio.Semaphore(settings.firecrawl_concurrency)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        async def request() -> dict[str, Any]:
            async with self._semaphore:
                try:
                    response = await self.client.post(path, json=payload)
                except httpx.TransportError:
                    raise ServiceError(
                        "source_unavailable", "The source service could not be reached.", retryable=True
                    ) from None
                if not response.is_success:
                    status = response.status_code
                    raise ServiceError(
                        "rate_limited" if status == 429 else "source_unavailable",
                        "The source service is busy or this page could not be collected.",
                        retryable=status in (408, 429) or status >= 500,
                        retry_after=retry_after_seconds(response.headers.get("retry-after")),
                    )
                try:
                    body = response.json()
                except ValueError:
                    raise ServiceError("source_unavailable", "The source service returned an unreadable response.") from None
                if not isinstance(body, dict) or body.get("success") is not True:
                    raise ServiceError("source_unavailable", "The source could not be collected.")
                data = body.get("data")
                if not isinstance(data, dict):
                    raise ServiceError("source_unavailable", "The source service returned an incomplete response.")
                return data

        return await with_backoff(
            request,
            attempts=self.settings.provider_max_attempts,
            base_seconds=self.settings.retry_base_seconds,
            max_seconds=self.settings.retry_max_seconds,
        )

    async def scrape(self, url: str) -> Document:
        target = public_url(TypeAdapter(HttpUrl).validate_python(url))
        data = await self._post("scrape", {"url": str(target), "formats": ["markdown"], "onlyMainContent": True})
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        markdown = data.get("markdown")
        try:
            status_code = int(metadata.get("statusCode") or 200)
        except (TypeError, ValueError):
            status_code = 502
        if not isinstance(markdown, str) or not markdown.strip() or status_code >= 400:
            raise ServiceError("scrape_unavailable", "The supplied page was blocked or contained no readable text.")
        return Document(
            url=target,
            title=str(metadata.get("title") or target.host)[:4000],
            text=markdown,
        )

    async def news(self, company_name: str) -> list[Document]:
        name = company_name.replace('"', " ").strip()
        data = await self._post(
            "search",
            {"query": f'"{name}" company news', "sources": ["news"], "limit": self.settings.news_result_limit, "tbs": "qdr:m"},
        )
        documents: list[Document] = []
        news = data.get("news") or []
        if not isinstance(news, list):
            raise ServiceError("source_unavailable", "News results could not be read.")
        for item in news[: self.settings.news_result_limit]:
            if not isinstance(item, dict) or not isinstance(item.get("snippet"), str) or not item["snippet"].strip():
                continue
            try:
                url = public_url(TypeAdapter(HttpUrl).validate_python(item.get("url")))
                documents.append(Document(url=url, title=str(item.get("title") or url.host)[:4000], text=item["snippet"]))
            except (ValidationError, ValueError):
                continue
        return documents
