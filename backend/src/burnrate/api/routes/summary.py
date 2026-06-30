from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from burnrate.api.dependencies import get_summary_service
from burnrate.api.schemas.summary import SummaryResponse
from burnrate.services.summary_service import SummaryService

router = APIRouter(tags=["summary"])


@router.get("/summary", response_model=SummaryResponse)
def get_summary(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    try:
        payload = service.get_summary(month=month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return SummaryResponse.model_validate(payload)
