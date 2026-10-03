"""Groq structured generation with bounded retries and a shared concurrency cap."""

import asyncio
import json
import logging
from copy import deepcopy
from typing import Any

from groq import APIConnectionError, APIStatusError, AsyncGroq
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import InvalidModelOutput, ServiceError
from app.services.ports import Output
from app.services.retry import retry_after_seconds, with_backoff

logger = logging.getLogger(__name__)

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
    """Build Groq's strict-schema subset; Pydantic enforces omitted constraints locally."""
    result = deepcopy(schema)
    # Groq's constrained decoder accepts a JSON Schema subset. Keep validation
    # bounds in the Pydantic models, but omit these keywords from its grammar.
    local_only_keywords = {
        "default", "title", "pattern", "minLength", "maxLength",
        "minItems", "maxItems", "format", "description", "minimum", "maximum",
        "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minProperties",
        "maxProperties", "uniqueItems", "examples", "deprecated", "readOnly", "writeOnly",
    }
    map_keys = {"properties", "$defs", "definitions"}

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            for keyword in local_only_keywords:
                item.pop(keyword, None)
            if item.get("type") == "object" or "properties" in item:
                item["additionalProperties"] = False
                item["required"] = list(item.get("properties", {}))
            for key, value in item.items():
                if key in map_keys and isinstance(value, dict):
                    for child in value.values():
                        walk(child)
                else:
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
                        request_options: dict[str, Any] = {
                            "model": self.settings.model_for(node),
                            "messages": [
                                {"role": "system", "content": instructions + correction},
                                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                            ],
                            "response_format": {
                                "type": "json_schema",
                                "json_schema": {
                                    "name": schema.__name__,
                                    "strict": True,
                                    "schema": strict_schema(schema.model_json_schema()),
                                },
                            },
                            "max_completion_tokens": min(
                                self.settings.model_max_output_tokens,
                                NODE_OUTPUT_TOKEN_LIMITS[node],
                            ),
                            "temperature": 0.2,
                        }
                        if request_options["model"].startswith("openai/gpt-oss-"):
                            request_options["reasoning_effort"] = "low"
                        completion = await self.client.chat.completions.create(**request_options)
                        usage = completion.usage
                        logger.info(
                            "Groq usage node=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                            node,
                            getattr(usage, "prompt_tokens", "unavailable"),
                            getattr(usage, "completion_tokens", "unavailable"),
                            getattr(usage, "total_tokens", "unavailable"),
                        )
                        finish_reason = completion.choices[0].finish_reason if completion.choices else None
                        if finish_reason == "length":
                            raise ServiceError(
                                "model_output_truncated",
                                "The model ran out of output space. Retry this stage with the saved research.",
                            )
                        if not completion.choices:
                            return ""
                        return completion.choices[0].message.content or ""
                    except APIStatusError as error:
                        status = error.status_code
                        request_id = (
                            error.response.headers.get("x-request-id")
                            or error.response.headers.get("x-groq-id")
                        )
                        # Log allowlisted metadata only. Provider messages can
                        # echo request content, so never log the response body.
                        try:
                            error_payload = error.response.json()
                            provider_error = error_payload.get("error", {})
                            provider_code = provider_error.get("code")
                            provider_type = provider_error.get("type")
                            provider_param = provider_error.get("param")
                        except (ValueError, AttributeError):
                            provider_code = provider_type = provider_param = None
                        logger.warning(
                            "Groq request failed node=%s status=%s request_id=%s code=%s type=%s param=%s",
                            node,
                            status,
                            request_id or "unavailable",
                            provider_code or "unavailable",
                            provider_type or "unavailable",
                            provider_param or "unavailable",
                        )
                        if status == 400:
                            code = "model_request_rejected"
                            message = "Groq rejected this model request. Check the model ID and structured-output support."
                        elif status in (401, 403):
                            code = "model_auth_failed"
                            message = "Groq rejected the configured credentials. Check the Groq API key in deployment settings."
                        elif status == 404:
                            code = "model_not_found"
                            message = "The configured Groq model was not found. Check the model ID in deployment settings."
                        elif status == 429:
                            code = "rate_limited"
                            message = (
                                "Groq rate limit reached. Your input and completed stages are saved; "
                                "wait for the limit to reset, then retry this stage."
                            )
                        elif status >= 500:
                            code = "model_upstream_error"
                            message = (
                                f"Groq returned a temporary server error (HTTP {status}). "
                                "Your input and completed stages are saved; wait a moment, then retry this stage."
                            )
                        else:
                            code = "model_unavailable"
                            message = "The model service is busy or unavailable. Your input has been kept; try again later."
                        raise ServiceError(
                            code,
                            message,
                            # A 429 often means the token window is still full. Do not spend more
                            # requests retrying it automatically; let the user resume this node.
                            retryable=status in (408, 409) or status >= 500,
                            retry_after=retry_after_seconds(error.response.headers.get("retry-after")),
                        ) from None
                    except APIConnectionError:
                        logger.warning("Groq connection failed node=%s", node)
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
