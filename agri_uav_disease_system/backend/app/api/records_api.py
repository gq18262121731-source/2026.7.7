from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.constants import ERROR_RECORD_NOT_FOUND
from app.core.exceptions import AppException
from app.schemas.detection_result import DetectionResult
from app.schemas.record import RecordListResponse
from app.services.storage.result_store import result_store

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("", response_model=RecordListResponse)
async def list_records(
    plot_id: str | None = None,
    risk_level: str | None = None,
    severity: str | None = None,
    disease: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="created_at_desc"),
) -> RecordListResponse:
    records = result_store.list_records(
        plot_id=plot_id,
        risk_level=risk_level,
        severity=severity,
        disease=disease,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
        sort=sort,
    )
    total = result_store.count_records(
        plot_id=plot_id,
        risk_level=risk_level,
        severity=severity,
        disease=disease,
        start_time=start_time,
        end_time=end_time,
    )
    return RecordListResponse(items=records, total=total, page=page, page_size=page_size)


@router.get("/{record_id}", response_model=DetectionResult)
async def get_record(record_id: str) -> DetectionResult:
    record = result_store.get(record_id)
    if not record:
        raise AppException(ERROR_RECORD_NOT_FOUND, "\u8bc6\u522b\u8bb0\u5f55\u4e0d\u5b58\u5728", {"record_id": record_id})
    return record
