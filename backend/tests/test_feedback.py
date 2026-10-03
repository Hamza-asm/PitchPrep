from uuid import uuid4

import pytest

from app.services.feedback import FeedbackDelivery
from app.services.tracing import WorkflowTracer


async def test_feedback_delivery_acknowledges_only_success():
    row = {"brief_id": str(uuid4()), "event_id": str(uuid4()), "trace_id": str(uuid4()), "rating": 1}
    acknowledgements = []
    delivered = []

    class Repo:
        async def pending_feedback(self):
            return [row]

        async def mark_feedback_synced(self, brief_id, event_id):
            acknowledgements.append((brief_id, event_id))

    class Tracer:
        def feedback(self, **kwargs):
            delivered.append(kwargs)

    await FeedbackDelivery(Repo(), Tracer()).deliver_once()
    assert delivered[0]["rating"] == 1
    assert str(delivered[0]["run_id"]) == row["trace_id"]
    assert acknowledgements == [(row["brief_id"], row["event_id"])]

    class UnavailableTracer:
        def feedback(self, **kwargs):
            raise RuntimeError("Offline fixture")

    with pytest.raises(RuntimeError):
        await FeedbackDelivery(Repo(), UnavailableTracer()).deliver_once()
    assert len(acknowledgements) == 1


def test_tracing_is_disabled_for_tests_even_if_requested(settings):
    settings.langsmith_tracing = True
    tracer = WorkflowTracer(settings)
    assert tracer.client is None
    assert tracer.enabled is False
    with tracer.span("offline", run_id=uuid4()):
        pass


def test_tracer_uses_explicit_run_id(settings, monkeypatch):
    from contextlib import contextmanager
    from app.services import tracing

    captured = []

    @contextmanager
    def fake_trace(*args, **kwargs):
        captured.append(kwargs)
        yield

    tracer = WorkflowTracer(settings)
    tracer.enabled = True
    monkeypatch.setattr(tracing, "trace", fake_trace)
    run_id = uuid4()
    with tracer.span("fixture", run_id=run_id):
        pass
    assert captured[0]["run_id"] == run_id
