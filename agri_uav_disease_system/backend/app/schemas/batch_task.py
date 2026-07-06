from __future__ import annotations

from pydantic import BaseModel


class BatchTaskStatus(BaseModel):
    task_id: str
    task_type: str = "batch_image_detection"
    status: str
    total_images: int
    processed_images: int
    failed_images: int
    progress: float
    record_ids: list[str]
    failed_items: list[dict]
    created_at: str
    updated_at: str


class BatchTaskCreateResponse(BatchTaskStatus):
    pass
