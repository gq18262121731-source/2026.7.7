from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.batch_task import BatchTaskStatus


class BatchTaskRepository:
    def create(self, task: BatchTaskStatus) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO batch_tasks (
                        task_id, task_type, status, total_images, processed_images,
                        failed_images, progress, record_ids_json, failed_items_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        task.task_type,
                        task.status,
                        task.total_images,
                        task.processed_images,
                        task.failed_images,
                        task.progress,
                        json.dumps(task.record_ids, ensure_ascii=False),
                        json.dumps(task.failed_items, ensure_ascii=False),
                        task.created_at,
                        task.updated_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u6279\u91cf\u4efb\u52a1\u521b\u5efa\u5931\u8d25", {"reason": str(exc)}) from exc

    def get(self, task_id: str) -> BatchTaskStatus | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM batch_tasks WHERE task_id = ?", (task_id,)).fetchone()
            return self._row_to_task(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u6279\u91cf\u4efb\u52a1\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def update(self, task: BatchTaskStatus) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE batch_tasks
                    SET status = ?, processed_images = ?, failed_images = ?, progress = ?,
                        record_ids_json = ?, failed_items_json = ?, updated_at = ?
                    WHERE task_id = ?
                    """,
                    (
                        task.status,
                        task.processed_images,
                        task.failed_images,
                        task.progress,
                        json.dumps(task.record_ids, ensure_ascii=False),
                        json.dumps(task.failed_items, ensure_ascii=False),
                        task.updated_at,
                        task.task_id,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u6279\u91cf\u4efb\u52a1\u66f4\u65b0\u5931\u8d25", {"reason": str(exc)}) from exc

    def _row_to_task(self, row: sqlite3.Row) -> BatchTaskStatus:
        return BatchTaskStatus(
            task_id=row["task_id"],
            task_type=row["task_type"],
            status=row["status"],
            total_images=row["total_images"],
            processed_images=row["processed_images"],
            failed_images=row["failed_images"],
            progress=row["progress"],
            record_ids=json.loads(row["record_ids_json"]),
            failed_items=json.loads(row["failed_items_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

