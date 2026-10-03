"""Public API contracts and persisted run records."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.research import (
    FinalBrief, ProgressEvent, ResearchRequest, Schema, SellerProfile, WorkflowNode, WorkflowState,
)

JobStatus = Literal["queued", "running", "needs_input", "needs_confirmation", "completed", "failed"]


class EmailEdit(Schema):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=12000)


class SaveEmail(EmailEdit):
    expected_version: int = Field(ge=0)


class RegenerateEmail(Schema):
    tone: Literal["professional", "friendly", "concise"] = "professional"
    expected_version: int = Field(ge=0)


class ConfirmLink(Schema):
    confirmed: Literal[True]
    expected_version: int = Field(ge=0)


class RetryRun(Schema):
    expected_version: int = Field(ge=0)


class FeedbackInput(Schema):
    rating: Literal[-1, 1]
    comment: str = Field(default="", max_length=2000)


class BriefRecord(Schema):
    id: UUID
    request: ResearchRequest
    seller: SellerProfile
    status: JobStatus
    progress: list[ProgressEvent] = Field(default_factory=list)
    state: WorkflowState | None = None
    result: FinalBrief | None = None
    email_edit: EmailEdit | None = None
    version: int = 0
    job_kind: Literal["research", "confirm", "email", "retry"] = "research"
    tone: str | None = None
    lease_token: UUID | None = None
    lease_expires_at: datetime | None = None
    trace_id: UUID | None = None
    result_trace_id: UUID | None = None
    error_code: str | None = None
    message: str | None = None
    created_at: datetime
    updated_at: datetime


class BriefDetail(Schema):
    id: UUID
    request: ResearchRequest
    status: JobStatus
    progress: list[ProgressEvent]
    result: FinalBrief | None
    email_edit: EmailEdit | None
    version: int
    error_code: str | None
    message: str | None
    retry_node: WorkflowNode | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: BriefRecord) -> "BriefDetail":
        data = record.model_dump(include=set(cls.model_fields))
        retryable_input = (
            record.status == "needs_input" and record.state
            and record.state.retry_node == "source_fetch"
        )
        data["retry_node"] = (
            record.state.retry_node
            if record.state and (record.status == "failed" or retryable_input)
            else None
        )
        return cls.model_validate(data)


class BriefSummary(Schema):
    id: UUID
    company_name: str
    status: JobStatus
    limited_data: bool
    created_at: datetime


class BriefPage(Schema):
    items: list[BriefSummary]
    next_offset: int | None


class AcceptedRun(Schema):
    id: UUID
    status: JobStatus
    version: int
