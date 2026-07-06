from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.uav import AbnormalRegion, UavImage, UavIndexResult, UavTask


class UavRepository:
    def save_task(self, task: UavTask) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO uav_tasks (
                        uav_task_id, field_id, task_name, flight_date, sensor_type, data_mode,
                        growth_stage, weather_text, status, summary, is_mock, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task.uav_task_id,
                        task.field_id,
                        task.task_name,
                        task.flight_date,
                        task.sensor_type,
                        task.data_mode,
                        task.growth_stage,
                        task.weather_text,
                        task.status,
                        task.summary,
                        int(task.is_mock),
                        task.created_at,
                        task.updated_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 任务保存失败", {"reason": str(exc)}) from exc

    def get_task(self, uav_task_id: str) -> UavTask | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM uav_tasks WHERE uav_task_id = ?", (uav_task_id,)).fetchone()
            return self._row_to_task(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 任务查询失败", {"reason": str(exc)}) from exc

    def list_tasks(self, field_id: str | None = None, page: int = 1, page_size: int = 50) -> list[UavTask]:
        where = "WHERE field_id = ?" if field_id else ""
        params: list[object] = [field_id] if field_id else []
        params.extend([page_size, (page - 1) * page_size])
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM uav_tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    params,
                ).fetchall()
            return [self._row_to_task(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 任务列表查询失败", {"reason": str(exc)}) from exc

    def count_tasks(self, field_id: str | None = None) -> int:
        where = "WHERE field_id = ?" if field_id else ""
        params: list[object] = [field_id] if field_id else []
        try:
            with get_connection() as conn:
                row = conn.execute(f"SELECT COUNT(*) AS total FROM uav_tasks {where}", params).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 任务统计失败", {"reason": str(exc)}) from exc

    def save_image(self, image: UavImage) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO uav_images (
                        uav_image_id, uav_task_id, field_id, image_url, image_type, band_type,
                        index_type, capture_time, lat, lng, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        image.uav_image_id,
                        image.uav_task_id,
                        image.field_id,
                        image.image_url,
                        image.image_type,
                        image.band_type,
                        image.index_type,
                        image.capture_time,
                        image.lat,
                        image.lng,
                        image.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 图像保存失败", {"reason": str(exc)}) from exc

    def save_index(self, item: UavIndexResult) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO uav_index_results (
                        index_result_id, uav_task_id, field_id, index_type, index_image_url,
                        min_value, max_value, mean_value, threshold_used, abnormal_area_ratio,
                        data_mode, is_mock, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.index_result_id,
                        item.uav_task_id,
                        item.field_id,
                        item.index_type,
                        item.index_image_url,
                        item.min_value,
                        item.max_value,
                        item.mean_value,
                        item.threshold_used,
                        item.abnormal_area_ratio,
                        item.data_mode,
                        int(item.is_mock),
                        item.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 指数结果保存失败", {"reason": str(exc)}) from exc

    def list_indices(self, uav_task_id: str) -> list[UavIndexResult]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM uav_index_results WHERE uav_task_id = ? ORDER BY index_type",
                    (uav_task_id,),
                ).fetchall()
            return [self._row_to_index(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV 指数结果查询失败", {"reason": str(exc)}) from exc

    def save_region(self, region: AbnormalRegion) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO abnormal_regions (
                        region_id, uav_task_id, field_id, region_name, region_image_url,
                        region_polygon_json, center_lat, center_lng, abnormal_type, abnormal_level,
                        abnormal_area_ratio, source_index_type, confirm_status, linked_phone_image_id,
                        linked_record_id, confirmed_disease_type, confirm_confidence, confirm_source,
                        confirmed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        region.region_id,
                        region.uav_task_id,
                        region.field_id,
                        region.region_name,
                        region.region_image_url,
                        json.dumps(region.region_polygon, ensure_ascii=False) if region.region_polygon else None,
                        region.center_lat,
                        region.center_lng,
                        region.abnormal_type,
                        region.abnormal_level,
                        region.abnormal_area_ratio,
                        region.source_index_type,
                        region.confirm_status,
                        region.linked_phone_image_id,
                        region.linked_record_id,
                        region.confirmed_disease_type,
                        region.confirm_confidence,
                        region.confirm_source,
                        region.confirmed_at,
                        region.created_at,
                        region.updated_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "异常区域保存失败", {"reason": str(exc)}) from exc

    def get_region(self, region_id: str) -> AbnormalRegion | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM abnormal_regions WHERE region_id = ?", (region_id,)).fetchone()
            return self._row_to_region(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "异常区域查询失败", {"reason": str(exc)}) from exc

    def list_regions(self, uav_task_id: str | None = None, field_id: str | None = None) -> list[AbnormalRegion]:
        clauses: list[str] = []
        params: list[object] = []
        if uav_task_id:
            clauses.append("uav_task_id = ?")
            params.append(uav_task_id)
        if field_id:
            clauses.append("field_id = ?")
            params.append(field_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM abnormal_regions {where} ORDER BY created_at DESC",
                    params,
                ).fetchall()
            return [self._row_to_region(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "异常区域列表查询失败", {"reason": str(exc)}) from exc

    def _row_to_task(self, row: sqlite3.Row) -> UavTask:
        data = dict(row)
        data["is_mock"] = bool(data["is_mock"])
        return UavTask(**data)

    def _row_to_index(self, row: sqlite3.Row) -> UavIndexResult:
        data = dict(row)
        data["is_mock"] = bool(data["is_mock"])
        return UavIndexResult(**data)

    def _row_to_region(self, row: sqlite3.Row) -> AbnormalRegion:
        data = dict(row)
        data["region_polygon"] = json.loads(data.pop("region_polygon_json") or "null")
        return AbnormalRegion(**data)


uav_repository = UavRepository()
