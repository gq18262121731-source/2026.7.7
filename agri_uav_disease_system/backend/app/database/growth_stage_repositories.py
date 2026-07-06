from __future__ import annotations

import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.growth_stage import GrowthStage


class GrowthStageRepository:
    def save(self, item: GrowthStage) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO plot_growth_stages (
                        growth_id, plot_id, rice_variety, sowing_date, transplanting_date,
                        growth_stage, manual_growth_stage, inferred_growth_stage, updated_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.growth_id,
                        item.plot_id,
                        item.rice_variety,
                        item.sowing_date,
                        item.transplanting_date,
                        item.growth_stage,
                        item.manual_growth_stage,
                        item.inferred_growth_stage,
                        item.updated_at,
                        item.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "生育期记录保存失败", {"reason": str(exc)}) from exc

    def list_by_plot(self, plot_id: str) -> list[GrowthStage]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM plot_growth_stages WHERE plot_id = ? ORDER BY updated_at DESC",
                    (plot_id,),
                ).fetchall()
            return [self._row_to_item(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "生育期记录查询失败", {"reason": str(exc)}) from exc

    def latest_for_plot(self, plot_id: str) -> GrowthStage | None:
        items = self.list_by_plot(plot_id)
        return items[0] if items else None

    def _row_to_item(self, row: sqlite3.Row) -> GrowthStage:
        return GrowthStage(**dict(row))
