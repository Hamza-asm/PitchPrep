"""One bounded retry layer; provider SDK retries must be disabled."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from random import uniform
from typing import TypeVar

from app.core.errors import ServiceError

T = TypeVar("T")


def retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0, float(value))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
            return max(0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


async def with_backoff(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base_seconds: float,
    max_seconds: float,
) -> T:
    for attempt in range(attempts):
        try:
            return await operation()
        except ServiceError as error:
            if not error.retryable or attempt == attempts - 1:
                raise
            delay = min(max_seconds, base_seconds * 2**attempt + uniform(0, base_seconds / 4))
            if error.retry_after is not None:
                # Never shorten a provider's cooldown and immediately hit it again.
                if error.retry_after > max_seconds:
                    raise
                delay = max(delay, error.retry_after)
            await asyncio.sleep(delay)
    raise RuntimeError("At least one attempt is required")
