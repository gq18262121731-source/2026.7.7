from __future__ import annotations

from pydantic import BaseModel

from app.schemas.detection_result import DetectionResult


class RecordListResponse(BaseModel):
    items: list[DetectionResult]
    total: int
    page: int
    page_size: int
