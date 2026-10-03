"""Seller setup, durable research jobs, history and replayable SSE snapshots."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import StreamingResponse

from app.schemas.api import (
    AcceptedRun, BriefDetail, BriefPage, BriefSummary, ConfirmLink, EmailEdit,
    FeedbackInput, RegenerateEmail, RetryRun, SaveEmail,
)
from app.schemas.research import ResearchRequest, SellerProfile
from app.services.repository import RepositoryError, SupabaseRepository

router = APIRouter()


def repository(request: Request) -> SupabaseRepository:
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise RepositoryError("not_ready", "The application is still starting.")
    return repo


@router.get("/seller-profile", response_model=SellerProfile | None)
async def get_seller(request: Request) -> SellerProfile | None:
    return await repository(request).get_seller()


@router.put("/seller-profile", response_model=SellerProfile)
async def put_seller(value: SellerProfile, request: Request) -> SellerProfile:
    return await repository(request).save_seller(value)


@router.post("/briefs", response_model=AcceptedRun, status_code=202)
async def create_brief(value: ResearchRequest, request: Request,
                       idempotency_key: Annotated[UUID | None, Header()] = None) -> AcceptedRun:
    repo = repository(request)
    seller = await repo.get_seller()
    if seller is None:
        raise RepositoryError("seller_required", "Save what you sell and your ideal customer first.", 409)
    record = await repo.create(idempotency_key or uuid4(), value, seller)
    return AcceptedRun(id=record.id, status=record.status, version=record.version)


@router.get("/briefs", response_model=BriefPage)
async def history(request: Request, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> BriefPage:
    rows = await repository(request).list_briefs(limit + 1, offset)
    return BriefPage(items=[BriefSummary(
        id=row["id"], company_name=row["request"]["company_name"], status=row["status"],
        limited_data=bool(row.get("limited_data")), created_at=row["created_at"],
    ) for row in rows[:limit]], next_offset=offset + limit if len(rows) > limit else None)


@router.get("/briefs/{brief_id}", response_model=BriefDetail)
async def get_brief(brief_id: UUID, request: Request) -> BriefDetail:
    return BriefDetail.from_record(await repository(request).get(brief_id))


@router.get("/briefs/{brief_id}/stream")
async def stream(brief_id: UUID, request: Request,
                 last_event_id: Annotated[str | None, Header()] = None) -> StreamingResponse:
    repo = repository(request)
    initial = await repo.get(brief_id)  # Return a real 404 before sending stream headers.

    async def events() -> AsyncIterator[str]:
        # Every event is a full public snapshot, so reconnects cannot miss stages.
        previous = last_event_id
        row = initial
        while True:
            if await request.is_disconnected():
                return
            detail = BriefDetail.from_record(row)
            terminal = row.status not in ("queued", "running")
            version = str(row.version)
            if previous != version or terminal:
                kind = "result" if terminal else "progress"
                yield f"id: {version}\nevent: {kind}\ndata: {detail.model_dump_json()}\n\n"
                previous = version
            else:
                yield ": keep-alive\n\n"
            if terminal:
                return
            await asyncio.sleep(request.app.state.settings.stream_poll_seconds)
            try:
                row = await repo.get(brief_id)
            except RepositoryError:
                yield "event: unavailable\ndata: " + json.dumps({"message": "Progress is temporarily unavailable. Reconnect to continue."}) + "\n\n"
                return

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@router.post("/briefs/{brief_id}/confirm-link", response_model=AcceptedRun, status_code=202)
async def confirm_link(brief_id: UUID, value: ConfirmLink, request: Request) -> AcceptedRun:
    row = await repository(request).enqueue_again(brief_id, value.expected_version, "confirm")
    return AcceptedRun(id=row.id, status=row.status, version=row.version)


@router.post("/briefs/{brief_id}/retry", response_model=AcceptedRun, status_code=202)
async def retry_stage(brief_id: UUID, value: RetryRun, request: Request) -> AcceptedRun:
    row = await repository(request).enqueue_again(brief_id, value.expected_version, "retry")
    return AcceptedRun(id=row.id, status=row.status, version=row.version)


@router.post("/briefs/{brief_id}/email/regenerate", response_model=AcceptedRun, status_code=202)
async def regenerate(brief_id: UUID, value: RegenerateEmail, request: Request) -> AcceptedRun:
    row = await repository(request).enqueue_again(brief_id, value.expected_version, "email", value.tone)
    return AcceptedRun(id=row.id, status=row.status, version=row.version)


@router.put("/briefs/{brief_id}/email", response_model=BriefDetail)
async def save_email(brief_id: UUID, value: SaveEmail, request: Request) -> BriefDetail:
    email = EmailEdit(subject=value.subject, body=value.body)
    row = await repository(request).save_email(brief_id, value.expected_version, email)
    return BriefDetail.from_record(row)


@router.post("/briefs/{brief_id}/feedback", status_code=204)
async def feedback(brief_id: UUID, value: FeedbackInput, request: Request) -> Response:
    repo = repository(request)
    row = await repo.get(brief_id)
    if row.result is None:
        raise RepositoryError("brief_required", "Feedback is available after a brief has been generated.", 409)
    await repo.feedback(brief_id, value, row.result_trace_id)
    return Response(status_code=204)
