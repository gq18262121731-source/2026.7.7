from __future__ import annotations

import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.farm_operation import FarmOperation


class FarmOperationRepository:
    def save(self, item: FarmOperation) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO farm_operations (
                        operation_id, plot_id, operation_type, operation_time, target_disease,
                        material_name, dosage_text, operator_id, operator_name, note, photo_url, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.operation_id,
                        item.plot_id,
                        item.operation_type,
                        item.operation_time,
                        item.target_disease,
                        item.material_name,
                        item.dosage_text,
                        item.operator_id,
                        item.operator_name,
                        item.note,
                        item.photo_url,
                        item.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "管护记录保存失败", {"reason": str(exc)}) from exc

    def list_operations(self, plot_id: str | None = None, limit: int = 100) -> list[FarmOperation]:
        clauses: list[str] = []
        params: list[object] = []
        if plot_id:
            clauses.append("plot_id = ?")
            params.append(plot_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM farm_operations {where_sql} ORDER BY operation_time DESC, created_at DESC LIMIT ?",
                    [*params, limit],
                ).fetchall()
            return [self._row_to_item(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "管护记录查询失败", {"reason": str(exc)}) from exc

    def recent_for_plot(self, plot_id: str, limit: int = 20) -> list[FarmOperation]:
        return self.list_operations(plot_id=plot_id, limit=limit)

    def _row_to_item(self, row: sqlite3.Row) -> FarmOperation:
        return FarmOperation(**dict(row))
