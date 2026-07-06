from __future__ import annotations

from app.core.logger import logger
from app.schemas.batch_task import BatchTaskStatus
from app.services.realtime.websocket_manager import task_websocket_manager


class TaskStatusPublisher:
    async def publish(self, task: BatchTaskStatus) -> None:
        try:
            await task_websocket_manager.broadcast_json(
                {
                    "type": "task_status",
                    "task_id": task.task_id,
                    "status": task.status,
                    "total_images": task.total_images,
                    "processed_images": task.processed_images,
                    "failed_images": task.failed_images,
                    "progress": task.progress,
                    "updated_at": task.updated_at,
                }
            )
        except Exception as exc:
            logger.warning("Task status publish failed: %s", exc)


task_status_publisher = TaskStatusPublisher()
