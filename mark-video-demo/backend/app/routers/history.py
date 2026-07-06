from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.data_store import get_history_record, list_history

router = APIRouter(tags=["history"])


@router.get("/history")
def history(
    keyword: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
) -> dict:
    return {"records": list_history(keyword=keyword, status=status, type=type)}


@router.get("/history/{record_id}")
def history_detail(record_id: str) -> dict:
    record = get_history_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail={"code": "RECORD_NOT_FOUND", "message": record_id})
    return record

