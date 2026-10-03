"""Backend-only Supabase Data API access; mutations use atomic RPCs where needed."""

from typing import Any
from uuid import UUID, uuid4

import httpx

from app.core.config import Settings
from app.core.errors import ServiceError
from app.schemas.api import BriefRecord, EmailEdit, FeedbackInput
from app.schemas.research import ProgressEvent, ResearchRequest, SellerProfile, WorkflowState


class RepositoryError(ServiceError):
    def __init__(self, code: str, message: str, status_code: int = 503) -> None:
        super().__init__(code, message)
        self.status_code = status_code


class SupabaseRepository:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        key = settings.supabase_service_role_key.get_secret_value()
        base_url = str(settings.supabase_url).rstrip("/")
        if base_url.endswith("/rest/v1"):
            base_url = base_url[:-len("/rest/v1")]
        self.client = client or httpx.AsyncClient(
            base_url=base_url + "/rest/v1/",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15, follow_redirects=False,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self.client.request(method, path, **kwargs)
        except httpx.TransportError:
            raise RepositoryError("database_unavailable", "Saved data is temporarily unavailable. Try again shortly.") from None
        if not response.is_success:
            if response.status_code == 409:
                raise RepositoryError("conflict", "This run changed. Refresh it before trying again.", 409)
            raise RepositoryError("database_unavailable", "Saved data is temporarily unavailable. Try again shortly.")
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            raise RepositoryError("database_unavailable", "Saved data could not be read.") from None

    async def get_seller(self) -> SellerProfile | None:
        rows = await self._request("GET", "seller_profiles", params={"id": "eq.true", "select": "profile"})
        return SellerProfile.model_validate(rows[0]["profile"]) if rows else None

    async def save_seller(self, profile: SellerProfile) -> SellerProfile:
        await self._request("POST", "seller_profiles", params={"on_conflict": "id"},
                            headers={"Prefer": "resolution=merge-duplicates"},
                            json={"id": True, "profile": profile.model_dump(mode="json")})
        return profile

    async def get(self, brief_id: UUID) -> BriefRecord:
        rows = await self._request("GET", "briefs", params={"id": f"eq.{brief_id}", "select": "*", "limit": 1})
        if not rows:
            raise RepositoryError("not_found", "Brief not found.", 404)
        return BriefRecord.model_validate(rows[0])

    async def list_briefs(self, limit: int, offset: int) -> list[dict[str, Any]]:
        return await self._request("GET", "briefs", params={
            "select": "id,request,status,result->limited_data,created_at",
            "order": "created_at.desc,id.desc", "limit": limit, "offset": offset,
        })

    async def create(self, brief_id: UUID, request: ResearchRequest, seller: SellerProfile) -> BriefRecord:
        # Ignore a repeated UUID so network retries never enqueue another provider run.
        await self._request("POST", "briefs", params={"on_conflict": "id"},
                            headers={"Prefer": "resolution=ignore-duplicates"},
                            json={"id": str(brief_id), "request": request.model_dump(mode="json"), "seller": seller.model_dump(mode="json")})
        row = await self.get(brief_id)
        if row.request != request:
            raise RepositoryError("idempotency_conflict", "This request key was already used for different input.", 409)
        return row

    async def claim(self, lease_token: UUID, lease_seconds: int) -> BriefRecord | None:
        rows = await self._request("POST", "rpc/pitchprep_claim_job", json={"p_token": str(lease_token), "p_seconds": lease_seconds})
        return BriefRecord.model_validate(rows[0]) if rows else None

    async def save_job(self, brief_id: UUID, token: UUID, lease_seconds: int, *,
                       state: WorkflowState | None = None, event: ProgressEvent | None = None,
                       finish: bool = False) -> None:
        success = await self._request("POST", "rpc/pitchprep_save_job", json={
            "p_id": str(brief_id), "p_token": str(token), "p_seconds": lease_seconds,
            "p_state": state.model_dump(mode="json") if state else None,
            "p_event": event.model_dump(mode="json") if event else None, "p_finish": finish,
        })
        if not success:
            raise RepositoryError("lease_lost", "The run was interrupted. Its saved input is still available.", 409)

    async def enqueue_again(self, brief_id: UUID, version: int, kind: str, tone: str | None = None) -> BriefRecord:
        rows = await self._request("POST", "rpc/pitchprep_enqueue_again", json={
            "p_id": str(brief_id), "p_version": version, "p_kind": kind, "p_tone": tone,
        })
        if not rows:
            raise RepositoryError("conflict", "This action is not available for the current run. Refresh it first.", 409)
        return BriefRecord.model_validate(rows[0])

    async def save_email(self, brief_id: UUID, version: int, email: EmailEdit) -> BriefRecord:
        rows = await self._request("POST", "rpc/pitchprep_save_email", json={
            "p_id": str(brief_id), "p_version": version, "p_email": email.model_dump(),
        })
        if not rows:
            raise RepositoryError("conflict", "The email changed or a run is active. Refresh it before saving.", 409)
        return BriefRecord.model_validate(rows[0])

    async def feedback(self, brief_id: UUID, value: FeedbackInput, trace_id: UUID | None) -> None:
        await self._request("POST", "feedback", params={"on_conflict": "brief_id"},
                            headers={"Prefer": "resolution=merge-duplicates"}, json={
                                "brief_id": str(brief_id), **value.model_dump(),
                                "trace_id": str(trace_id) if trace_id else None, "trace_synced": False,
                                "event_id": str(uuid4()),
                            })

    async def pending_feedback(self) -> list[dict[str, Any]]:
        return await self._request("GET", "feedback", params={
            "select": "brief_id,rating,trace_id,event_id", "trace_synced": "eq.false",
            "trace_id": "not.is.null", "order": "updated_at.asc", "limit": 10,
        })

    async def mark_feedback_synced(self, brief_id: str, event_id: str) -> None:
        await self._request("PATCH", "feedback", params={
            "brief_id": f"eq.{brief_id}", "event_id": f"eq.{event_id}",
        }, json={"trace_synced": True})
