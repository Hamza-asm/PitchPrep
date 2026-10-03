"""Small service interfaces keep workflow tests completely offline."""

from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, HttpUrl

from app.schemas.research import Schema, Text

Output = TypeVar("Output", bound=BaseModel)


class Document(Schema):
    url: HttpUrl
    title: Text
    text: str


class ModelService(Protocol):
    async def generate(
        self,
        *,
        node: str,
        schema: type[Output],
        instructions: str,
        payload: dict[str, Any],
        validation_context: dict[str, Any] | None = None,
    ) -> Output: ...


class WebService(Protocol):
    async def scrape(self, url: str) -> Document: ...

    async def news(self, company_name: str) -> list[Document]: ...
