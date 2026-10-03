from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "pitchprep"


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Liveness only: this endpoint never spends external API quota."""
    return HealthResponse()
