"""A durable database queue, independent of HTTP requests and SSE connections."""

import asyncio
import logging
from contextlib import suppress
from uuid import UUID, uuid4

from app.core.config import Settings
from app.schemas.api import BriefRecord
from app.schemas.research import ProgressEvent, RunStatus, WorkflowState
from app.services.repository import RepositoryError, SupabaseRepository
from app.workflows.research import ResearchWorkflow, updated

logger = logging.getLogger(__name__)


class ResearchWorker:
    def __init__(self, settings: Settings, repository: SupabaseRepository, workflow: ResearchWorkflow) -> None:
        self.settings = settings
        self.repository = repository
        self.workflow = workflow
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self.task = asyncio.create_task(self._loop(), name="pitchprep-worker")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def _loop(self) -> None:
        while True:
            try:
                if await self.run_once():
                    continue
            except Exception:
                # Do not log exception strings, requests, credentials or source text.
                logger.warning("Research worker could not access saved work; it will poll again.")
            await asyncio.sleep(self.settings.worker_poll_seconds)

    async def run_once(self) -> bool:
        token = uuid4()
        record = await self.repository.claim(token, self.settings.worker_lease_seconds)
        if record is None:
            return False
        await self._process(record, token)
        return True

    async def _process(self, record: BriefRecord, token: UUID) -> None:
        latest = record.state or WorkflowState(request=record.request, seller=record.seller)
        lease = self.settings.worker_lease_seconds

        async def progress(event: ProgressEvent) -> None:
            await self.repository.save_job(record.id, token, lease, event=event)

        async def checkpoint(state: WorkflowState) -> None:
            nonlocal latest
            latest = state
            await self.repository.save_job(record.id, token, lease, state=state)

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(lease / 3)
                await self.repository.save_job(record.id, token, lease)

        async def run() -> WorkflowState:
            return await self.workflow.run(
                record.request, record.seller, on_progress=progress, on_state=checkpoint,
                saved_state=record.state, mode=record.job_kind, tone=record.tone, trace_id=token,
            )

        job = asyncio.create_task(run())
        pulse = asyncio.create_task(heartbeat())
        try:
            done, _ = await asyncio.wait({job, pulse}, return_when=asyncio.FIRST_COMPLETED)
            if pulse in done:
                await pulse  # A lost lease cancels the workflow before further API calls.
                raise RuntimeError("Heartbeat ended unexpectedly")
            result = await job
            await self.repository.save_job(record.id, token, lease, state=result, finish=True)
        except asyncio.CancelledError:
            job.cancel()
            pulse.cancel()
            await asyncio.gather(job, pulse, return_exceptions=True)
            await self._mark_interrupted(record.id, token, latest, "run_interrupted")
            raise
        except Exception:
            job.cancel()
            pulse.cancel()
            await asyncio.gather(job, pulse, return_exceptions=True)
            await self._mark_interrupted(record.id, token, latest, "run_failed")
        finally:
            job.cancel()
            pulse.cancel()
            await asyncio.gather(job, pulse, return_exceptions=True)

    async def _mark_interrupted(self, brief_id: UUID, token: UUID, state: WorkflowState, code: str) -> None:
        failed = updated(state, status=RunStatus.FAILED, error_code=code,
                         message="The run could not finish. Your input and any previous result have been saved.")
        try:
            await self.repository.save_job(brief_id, token, self.settings.worker_lease_seconds, state=failed, finish=True)
        except RepositoryError:
            # The lease will expire in the database; never rerun automatically.
            logger.warning("Run interruption will be recorded when its lease expires.")
