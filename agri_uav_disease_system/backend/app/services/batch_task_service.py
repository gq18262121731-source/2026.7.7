from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import UploadFile

from app.core.constants import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PARTIAL_FAILED,
    TASK_STATUS_PENDING,
    TASK_STATUS_PROCESSING,
)
from app.core.exceptions import AppException
from app.database.batch_repositories import BatchTaskRepository
from app.schemas.batch_task import BatchTaskStatus
from app.schemas.upload import DetectImageMetadata
from app.services.detection_service import detection_service
from app.services.realtime.task_status_publisher import task_status_publisher
from app.services.storage.file_storage import file_storage_service


class BatchTaskService:
    def __init__(self, repository: BatchTaskRepository | None = None) -> None:
        self.repository = repository or BatchTaskRepository()

    async def create_task(self, files: list[UploadFile], metadata: DetectImageMetadata) -> tuple[BatchTaskStatus, list[dict[str, str]]]:
        now = self._now()
        task = BatchTaskStatus(
            task_id=f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            status=TASK_STATUS_PENDING,
            total_images=len(files),
            processed_images=0,
            failed_images=0,
            progress=0.0,
            record_ids=[],
            failed_items=[],
            created_at=now,
            updated_at=now,
        )
        self.repository.create(task)

        saved_items: list[dict[str, str]] = []
        for file in files:
            try:
                image_id, image_path, image_url = await file_storage_service.save_upload(file)
                saved_items.append(
                    {
                        "filename": file.filename or image_id,
                        "image_id": image_id,
                        "image_path": image_path,
                        "image_url": image_url,
                    }
                )
            except AppException as exc:
                task.failed_items.append(
                    {
                        "filename": file.filename,
                        "error_code": exc.error_code,
                        "message": exc.message,
                        "detail": exc.detail,
                    }
                )
                task.failed_images += 1
                task.processed_images += 1
                self._refresh_progress(task)
                self.repository.update(task)
                await task_status_publisher.publish(task)

        if not saved_items:
            task.status = TASK_STATUS_FAILED if task.failed_images else TASK_STATUS_COMPLETED
            task.updated_at = self._now()
            self.repository.update(task)
            await task_status_publisher.publish(task)
        return task, saved_items

    async def process_saved_items(self, task_id: str, saved_items: list[dict[str, str]], metadata: DetectImageMetadata) -> None:
        task = self.get_task(task_id)
        if not task:
            return
        if not saved_items:
            return

        task.status = TASK_STATUS_PROCESSING
        task.updated_at = self._now()
        self.repository.update(task)
        await task_status_publisher.publish(task)

        for item in saved_items:
            task = self.get_task(task_id)
            if not task:
                return
            try:
                result = await detection_service.detect_saved_image(
                    item["image_id"],
                    item["image_path"],
                    item["image_url"],
                    metadata,
                )
                task.record_ids.append(result.record_id)
            except AppException as exc:
                task.failed_items.append(
                    {
                        "filename": item.get("filename"),
                        "image_id": item.get("image_id"),
                        "error_code": exc.error_code,
                        "message": exc.message,
                        "detail": exc.detail,
                    }
                )
                task.failed_images += 1
            task.processed_images += 1
            self._refresh_progress(task)
            task.status = TASK_STATUS_PROCESSING
            task.updated_at = self._now()
            self.repository.update(task)
            await task_status_publisher.publish(task)

        task = self.get_task(task_id)
        if not task:
            return
        if task.failed_images == 0:
            task.status = TASK_STATUS_COMPLETED
        elif task.record_ids:
            task.status = TASK_STATUS_PARTIAL_FAILED
        else:
            task.status = TASK_STATUS_FAILED
        self._refresh_progress(task)
        task.updated_at = self._now()
        self.repository.update(task)
        await task_status_publisher.publish(task)

    def get_task(self, task_id: str) -> BatchTaskStatus | None:
        return self.repository.get(task_id)

    def _refresh_progress(self, task: BatchTaskStatus) -> None:
        task.progress = round(task.processed_images / task.total_images, 4) if task.total_images else 1.0

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


batch_task_service = BatchTaskService()
