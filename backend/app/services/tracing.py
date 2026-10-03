"""Trace node timings while excluding source contents, credentials and pasted text."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from langsmith import Client, trace, tracing_context
from langsmith.utils import LangSmithConflictError

from app.core.config import Settings


class WorkflowTracer:
    def __init__(self, settings: Settings) -> None:
        self.project = settings.langsmith_project
        self.enabled = settings.langsmith_tracing and settings.app_env != "test"
        self.client = (
            Client(
                api_key=settings.langsmith_api_key.get_secret_value() if settings.langsmith_api_key else None,
                api_url=str(settings.langsmith_endpoint) if settings.langsmith_endpoint else None,
                hide_inputs=True,
                hide_outputs=True,
                omit_traced_runtime_info=True,
            )
            if self.enabled else None
        )

    @contextmanager
    def span(self, name: str, *, metadata: dict[str, Any] | None = None, run_id: UUID | None = None) -> Iterator[None]:
        # Explicitly disabling the context also prevents LangGraph auto-tracing in tests.
        with tracing_context(enabled=self.enabled, client=self.client, project_name=self.project):
            if not self.enabled:
                yield
            else:
                with trace(name, run_type="chain", inputs={}, metadata=metadata or {}, client=self.client, run_id=run_id):
                    yield

    def feedback(self, *, run_id: UUID, event_id: UUID, rating: int) -> None:
        if self.client:
            try:
                self.client.create_feedback(run_id=run_id, key="helpfulness", score=rating,
                                            feedback_id=event_id, stop_after_attempt=1)
            except LangSmithConflictError:
                pass  # This durable event was already delivered before a worker restart.

    def flush(self) -> None:
        if self.client:
            self.client.flush(timeout=5)
