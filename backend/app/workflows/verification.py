"""Fail-closed structural checks supplement the model's semantic verification."""

from collections import Counter

from app.schemas.research import (
    Claim,
    Draft,
    EmailSegment,
    EvidenceQuote,
    FinalBrief,
    FinalEmail,
    Source,
    Verdict,
    Verification,
    VerificationSummary,
    VerifiedClaim,
    WorkflowState,
)


def quote_exists(quote: EvidenceQuote, sources: dict[str, Source]) -> bool:
    source = sources.get(quote.source_id)
    if not source or not quote.quote.strip():
        return False
    # Whitespace normalization accepts harmless line wrapping, never paraphrases.
    return " ".join(quote.quote.split()) in " ".join(source.excerpt.split())


def check_verdicts(draft: Draft, report: Verification, sources: list[Source]) -> Verification:
    by_id = {source.id: source for source in sources}
    counts = Counter(verdict.unit_id for verdict in report.verdicts)
    reported = {verdict.unit_id: verdict for verdict in report.verdicts}
    checked: list[Verdict] = []
    for unit in draft.units():
        verdict = reported.get(unit.id)
        reason: str | None = None
        if counts[unit.id] != 1 or verdict is None:
            reason = "The verifier did not return exactly one decision for this unit."
        elif any(source_id not in by_id for source_id in unit.source_ids):
            reason = "This unit references an unavailable source."
        elif verdict.supported:
            if isinstance(unit, Claim) and verdict.basis != "sources":
                reason = "Every brief claim requires source evidence."
            elif unit.source_ids and verdict.basis != "sources":
                reason = "A cited statement must be verified against its sources."
            elif verdict.basis == "sources" and (
                not verdict.evidence
                or any(quote.source_id not in unit.source_ids or not quote_exists(quote, by_id) for quote in verdict.evidence)
            ):
                reason = "The verification evidence is missing or is not a verbatim quote from the cited sources."
        if reason:
            checked.append(Verdict(unit_id=unit.id, supported=False, basis="sources", reason=reason))
        elif verdict is not None:
            checked.append(verdict)
    return Verification(verdicts=checked)


def finalize(state: WorkflowState) -> FinalBrief:
    if state.draft is None or state.verification is None:
        raise ValueError("A draft and verification report are required")
    verdicts = {item.unit_id: item for item in state.verification.verdicts}
    supported = {unit_id for unit_id, verdict in verdicts.items() if verdict.supported}
    removed = len(state.draft.units()) - len(supported)
    notes = list(state.limitations)
    if removed:
        notes.append("Statements that could not be verified were removed from the brief and email.")
    claims = [VerifiedClaim(**claim.model_dump()) for claim in state.draft.claims if claim.id in supported]
    paragraphs = [paragraph for paragraph in state.draft.email.paragraphs if paragraph.id in supported]
    if not claims:
        notes.append("There was not enough evidence for a verified company brief.")
    if not paragraphs:
        notes.append("There was not enough evidence to retain an email draft.")
    return FinalBrief(
        company_name=state.request.company_name,
        claims=claims,
        email=FinalEmail(
            subject=state.draft.email.subject if state.draft.email.subject.id in supported else EmailSegment(id=state.draft.email.subject.id, text="A quick introduction"),
            paragraphs=paragraphs,
        ),
        sources=state.sources,
        limited_data=state.limited_data or removed > 0 or not claims,
        evidence_limitations=list(dict.fromkeys(notes)),
        verification=VerificationSummary(
            checked_units=len(state.draft.units()),
            supported_units=len(supported),
            removed_units=removed,
            revision_attempts=state.revision_attempts,
        ),
    )
