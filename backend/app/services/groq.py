"""Groq structured generation with bounded retries and a shared concurrency cap."""

import asyncio
import json
from copy import deepcopy
from typing import Any

from groq import APIConnectionError, APIStatusError, AsyncGroq
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import InvalidModelOutput, ServiceError
from app.services.ports import Output
from app.services.retry import retry_after_seconds, with_backoff

NODE_OUTPUT_TOKEN_LIMITS = {
    "parser": 800,
    "source_collector": 1200,
    "link_check": 300,
    "analyst": 1000,
    "matcher": 900,
    "writer": 1400,
    "verifier": 1200,
    "eval_judge": 1200,
}


def strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Keep nullable fields but require every key, including nested model keys."""
    result = deepcopy(schema)

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            item.pop("default", None)
            if item.get("type") == "object" or "properties" in item:
                item["additionalProperties"] = False
                item["required"] = list(item.get("properties", {}))
            for value in item.values():
                walk(value)
        elif isinstance(item, list):
            for value in item:
                walk(value)

    walk(result)
    return result


class GroqService:
    def __init__(self, settings: Settings, client: AsyncGroq | None = None) -> None:
        self.settings = settings
        self.client = client or AsyncGroq(
            api_key=settings.groq_api_key.get_secret_value(),
            base_url=str(settings.groq_base_url) if settings.groq_base_url else None,
            max_retries=0,
            timeout=settings.provider_timeout_seconds,
        )
        self._semaphore = asyncio.Semaphore(settings.groq_concurrency)

    async def aclose(self) -> None:
        await self.client.close()

    async def generate(
        self,
        *,
        node: str,
        schema: type[Output],
        instructions: str,
        payload: dict[str, Any],
        validation_context: dict[str, Any] | None = None,
    ) -> Output:
        for schema_attempt in range(self.settings.schema_max_attempts):
            correction = (
                "\nYour previous response failed schema validation. Return all required fields, "
                "valid supplied source IDs, and no extra fields."
                if schema_attempt else ""
            )

            async def request() -> str:
                async with self._semaphore:
                    try:
                        completion = await self.client.chat.completions.create(
                            model=self.settings.model_for(node),
                            messages=[
                                {"role": "system", "content": instructions + correction},
                                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                            ],
                            response_format={
                                "type": "json_schema",
                                "json_schema": {
                                    "name": schema.__name__,
                                    "strict": True,
                                    "schema": strict_schema(schema.model_json_schema()),
                                },
                            },
                            max_completion_tokens=min(
                                self.settings.model_max_output_tokens,
                                NODE_OUTPUT_TOKEN_LIMITS[node],
                            ),
                            temperature=0.2,
                        )
                        if not completion.choices:
                            return ""
                        return completion.choices[0].message.content or ""
                    except APIStatusError as error:
                        status = error.status_code
                        raise ServiceError(
                            "rate_limited" if status == 429 else "model_unavailable",
                            (
                                "Groq rate limit reached. Your input and completed stages are saved; "
                                "wait for the limit to reset, then retry this stage."
                                if status == 429 else
                                "The model service is busy or unavailable. Your input has been kept; try again later."
                            ),
                            # A 429 often means the token window is still full. Do not spend more
                            # requests retrying it automatically; let the user resume this node.
                            retryable=status in (408, 409) or status >= 500,
                            retry_after=retry_after_seconds(error.response.headers.get("retry-after")),
                        ) from None
                    except APIConnectionError:
                        raise ServiceError(
                            "model_unavailable",
                            "The model service could not be reached. Your input has been kept; try again later.",
                            retryable=True,
                        ) from None

            content = await with_backoff(
                request,
                attempts=self.settings.provider_max_attempts,
                base_seconds=self.settings.retry_base_seconds,
                max_seconds=self.settings.retry_max_seconds,
            )
            try:
                return schema.model_validate_json(content, context=validation_context)
            except ValidationError:
                # Never echo provider responses or validation inputs into logs.
                continue
        raise InvalidModelOutput()
