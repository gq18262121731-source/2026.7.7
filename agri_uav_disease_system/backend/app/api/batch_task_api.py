from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile

from app.core.config import settings
from app.core.constants import ERROR_TASK_NOT_FOUND
from app.core.exceptions import AppException
from app.schemas.batch_task import BatchTaskCreateResponse, BatchTaskStatus
from app.schemas.upload import DetectImageMetadata
from app.services.batch_task_service import batch_task_service

router = APIRouter(tags=["batch-tasks"])


@router.post("/api/detect/batch", response_model=BatchTaskCreateResponse)
async def detect_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    plot_id: str | None = Form(default=None),
    plot_name: str | None = Form(default=None),
    region_name: str | None = Form(default=None),
    lng: float | None = Form(default=None),
    lat: float | None = Form(default=None),
    source: str | None = Form(default=None),
    source_type: str | None = Form(default=None),
) -> BatchTaskCreateResponse:
    metadata = DetectImageMetadata(
        plot_id=plot_id,
        plot_name=plot_name,
        region_name=region_name,
        lng=lng,
        lat=lat,
        source=source,
        source_type=source_type or source or settings.default_source_type,
    )
    task, saved_items = await batch_task_service.create_task(files, metadata)
    if saved_items:
        background_tasks.add_task(batch_task_service.process_saved_items, task.task_id, saved_items, metadata)
    return BatchTaskCreateResponse(**task.model_dump())


@router.get("/api/tasks/{task_id}", response_model=BatchTaskStatus)
async def get_batch_task(task_id: str) -> BatchTaskStatus:
    task = batch_task_service.get_task(task_id)
    if not task:
        raise AppException(ERROR_TASK_NOT_FOUND, "\u6279\u91cf\u4efb\u52a1\u4e0d\u5b58\u5728", {"task_id": task_id})
    return task
