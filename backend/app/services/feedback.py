"""Deliver saved numeric feedback to LangSmith without blocking user requests."""

import asyncio
import logging
from contextlib import suppress
from uuid import UUID

from app.services.repository import SupabaseRepository
from app.services.tracing import WorkflowTracer

logger = logging.getLogger(__name__)


class FeedbackDelivery:
    def __init__(self, repository: SupabaseRepository, tracer: WorkflowTracer) -> None:
        self.repository = repository
        self.tracer = tracer
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.tracer.enabled:
            self.task = asyncio.create_task(self._loop(), name="pitchprep-feedback")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def deliver_once(self) -> None:
        for item in await self.repository.pending_feedback():
            await asyncio.to_thread(self.tracer.feedback, run_id=UUID(item["trace_id"]),
                                    event_id=UUID(item["event_id"]), rating=item["rating"])
            await self.repository.mark_feedback_synced(item["brief_id"], item["event_id"])

    async def _loop(self) -> None:
        while True:
            try:
                await self.deliver_once()
            except Exception:
                logger.warning("Feedback is saved; trace delivery will retry later.")
            await asyncio.sleep(30)
