"""Shared contracts. Model-generated citations refer to application-owned source IDs."""

import ipaddress
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    ValidationInfo,
    field_validator,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]{1,64}$")]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)


def public_url(value: HttpUrl) -> HttpUrl:
    host = (value.host or "").strip("[]").lower().rstrip(".")
    if value.username or value.password:
        raise ValueError("Links cannot contain credentials")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("Use a public company website or social link")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if "." not in host:
            raise ValueError("Use a public company website or social link") from None
    else:
        if not address.is_global:
            raise ValueError("Use a public company website or social link")
    return value


class SellerProfile(Schema):
    offering: Text
    ideal_customer: Text


class ResearchRequest(Schema):
    company_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    target_url: HttpUrl
    pasted_text: Annotated[str, StringConstraints(strip_whitespace=False, max_length=20000)] = ""
    link_confirmed: bool = False

    @field_validator("target_url")
    @classmethod
    def validate_target(cls, value: HttpUrl) -> HttpUrl:
        public_url(value)
        host = (value.host or "").lower()
        if (
            host.startswith("maps.google.")
            or host == "maps.app.goo.gl"
            or host == "goo.gl" and (value.path or "").startswith("/maps")
            or (host.startswith("google.") or host.startswith("www.google."))
            and (value.path or "").startswith("/maps")
        ):
            raise ValueError("Paste Google Maps details as text and supply a website or social link")
        return value


class ParsedCompany(Schema):
    company_name: Text | None = None
    location: Text | None = None
    category: Text | None = None
    website: HttpUrl | None = None
    phone: Text | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    hours: list[Text] = Field(default_factory=list)
    reviews: list[Text] = Field(default_factory=list)


class SourceType(StrEnum):
    SCRAPED = "scraped"
    SEARCH = "search"
    USER_PROVIDED = "user_provided"


class Source(Schema):
    id: Identifier
    type: SourceType
    title: Text
    url: HttpUrl | None = None
    excerpt: str = Field(min_length=1, max_length=20000)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_origin(self) -> Self:
        if self.type == SourceType.USER_PROVIDED:
            if self.url is not None:
                raise ValueError("User-provided text does not have an invented source URL")
        elif self.url is None:
            raise ValueError("Web evidence requires a source URL")
        else:
            public_url(self.url)
        return self


class EvidenceQuote(Schema):
    source_id: Identifier
    quote: Text


class CollectedEvidence(Schema):
    excerpts: list[EvidenceQuote] = Field(max_length=20)


class LinkAssessment(Schema):
    matches: bool
    reason: Text


class CitedText(Schema):
    text: Text
    source_ids: list[Identifier] = Field(min_length=1, max_length=10)

    @field_validator("source_ids")
    @classmethod
    def validate_sources(cls, values: list[str], info: ValidationInfo) -> list[str]:
        known = (info.context or {}).get("source_ids")
        if known is not None and any(value not in known for value in values):
            raise ValueError("Citation must reference an available source ID")
        if len(values) != len(set(values)):
            raise ValueError("Citation IDs must not repeat")
        return values


class Finding(CitedText):
    category: Literal["snapshot", "trigger", "need"]


class Analysis(Schema):
    # Persisted states remain compatible with older, larger workflow outputs.
    findings: list[Finding] = Field(max_length=16)


class AnalysisOutput(Analysis):
    findings: list[Finding] = Field(max_length=8)


class Opportunity(CitedText):
    seller_fit: Text
    target_role: Text


class Matches(Schema):
    opportunities: list[Opportunity] = Field(max_length=8)


class MatchesOutput(Matches):
    opportunities: list[Opportunity] = Field(max_length=4)


class Claim(CitedText):
    id: Identifier
    section: Literal["snapshot", "trigger", "need", "role"]


class EmailSegment(Schema):
    id: Identifier
    text: Text
    source_ids: list[Identifier] = Field(default_factory=list, max_length=10)


class EmailDraft(Schema):
    subject: EmailSegment
    paragraphs: list[EmailSegment] = Field(min_length=1, max_length=8)


class EmailDraftOutput(EmailDraft):
    paragraphs: list[EmailSegment] = Field(min_length=1, max_length=4)


class Draft(Schema):
    claims: list[Claim] = Field(max_length=24)
    email: EmailDraft

    @model_validator(mode="after")
    def unique_ids(self) -> Self:
        ids = [unit.id for unit in self.units()]
        if len(ids) != len(set(ids)):
            raise ValueError("Every claim, email subject and email paragraph needs a unique ID")
        return self

    def units(self) -> list[Claim | EmailSegment]:
        return [*self.claims, self.email.subject, *self.email.paragraphs]


class DraftOutput(Draft):
    claims: list[Claim] = Field(max_length=12)
    email: EmailDraftOutput


class Verdict(Schema):
    unit_id: Identifier
    supported: bool
    basis: Literal["sources", "seller_profile", "non_factual"]
    reason: Text
    evidence: list[EvidenceQuote] = Field(default_factory=list, max_length=10)


class Verification(Schema):
    verdicts: list[Verdict] = Field(max_length=40)


class VerificationOutput(Verification):
    verdicts: list[Verdict] = Field(max_length=17)


class VerifiedClaim(Claim):
    verification_status: Literal["verified"] = "verified"


class FinalEmail(Schema):
    subject: EmailSegment
    paragraphs: list[EmailSegment]


class VerificationSummary(Schema):
    checked_units: int = Field(ge=0)
    supported_units: int = Field(ge=0)
    removed_units: int = Field(ge=0)
    revision_attempts: int = Field(ge=0, le=2)


class FinalBrief(Schema):
    company_name: Text
    claims: list[VerifiedClaim]
    email: FinalEmail
    sources: list[Source]
    limited_data: bool
    evidence_limitations: list[str]
    verification: VerificationSummary


class Stage(StrEnum):
    PARSING = "parsing"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    MATCHING = "matching"
    WRITING = "writing"
    VERIFYING = "verifying"


class RunStatus(StrEnum):
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    NEEDS_CONFIRMATION = "needs_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"


WorkflowNode = Literal[
    "parser", "source_fetch", "source_collector", "link_check",
    "analyst", "matcher", "writer", "verifier",
]


class ProgressEvent(Schema):
    stage: Stage
    status: Literal["active", "complete", "failed"]
    revision_attempt: int = Field(default=0, ge=0, le=2)


class WorkflowState(Schema):
    request: ResearchRequest
    seller: SellerProfile
    status: RunStatus = RunStatus.RUNNING
    parsed: ParsedCompany | None = None
    sources: list[Source] = Field(default_factory=list)
    evidence: CollectedEvidence | None = None
    analysis: Analysis | None = None
    matches: Matches | None = None
    draft: Draft | None = None
    verification: Verification | None = None
    result: FinalBrief | None = None
    revision_attempts: int = Field(default=0, ge=0, le=2)
    retry_node: WorkflowNode | None = None
    limited_data: bool = False
    limitations: list[str] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None
    email_tone: Literal["professional", "friendly", "concise"] | None = None
