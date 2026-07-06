from __future__ import annotations

import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.field import FieldCreate, FieldInfo, FieldUpdate


class FieldRepository:
    def create(self, field: FieldCreate, now: str) -> FieldInfo:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO field_info (
                        field_id, field_name, location_city, location_district, location_town,
                        location_village, center_lat, center_lng, area_estimate_mu, crop_type,
                        current_growth_stage, field_status, notes, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        field.field_id,
                        field.field_name,
                        field.location_city,
                        field.location_district,
                        field.location_town,
                        field.location_village,
                        field.center_lat,
                        field.center_lng,
                        field.area_estimate_mu,
                        field.crop_type,
                        field.current_growth_stage,
                        field.field_status,
                        field.notes,
                        now,
                        now,
                    ),
                )
                conn.commit()
            created = self.get(field.field_id)
            assert created is not None
            return created
        except sqlite3.IntegrityError as exc:
            raise AppException("FIELD_ALREADY_EXISTS", "田块编号已存在", {"field_id": field.field_id}) from exc
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "田块保存失败", {"reason": str(exc)}) from exc

    def get(self, field_id: str) -> FieldInfo | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM field_info WHERE field_id = ?", (field_id,)).fetchone()
            return self._row_to_field(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "田块详情查询失败", {"reason": str(exc)}) from exc

    def list_fields(self, page: int = 1, page_size: int = 50, status: str | None = None) -> list[FieldInfo]:
        where = "WHERE field_status = ?" if status else ""
        params: list[object] = [status] if status else []
        params.extend([page_size, (page - 1) * page_size])
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM field_info {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    params,
                ).fetchall()
            return [self._row_to_field(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "田块列表查询失败", {"reason": str(exc)}) from exc

    def count(self, status: str | None = None) -> int:
        where = "WHERE field_status = ?" if status else ""
        params: list[object] = [status] if status else []
        try:
            with get_connection() as conn:
                row = conn.execute(f"SELECT COUNT(*) AS total FROM field_info {where}", params).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "田块统计失败", {"reason": str(exc)}) from exc

    def update(self, field_id: str, update: FieldUpdate, now: str) -> FieldInfo | None:
        values = update.model_dump(exclude_unset=True)
        if not values:
            return self.get(field_id)
        values["updated_at"] = now
        assignments = ", ".join(f"{key} = ?" for key in values)
        try:
            with get_connection() as conn:
                cur = conn.execute(
                    f"UPDATE field_info SET {assignments} WHERE field_id = ?",
                    [*values.values(), field_id],
                )
                conn.commit()
            if cur.rowcount == 0:
                return None
            return self.get(field_id)
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "田块更新失败", {"reason": str(exc)}) from exc

    def archive(self, field_id: str, now: str) -> FieldInfo | None:
        return self.update(field_id, FieldUpdate(field_status="archived"), now)

    def _row_to_field(self, row: sqlite3.Row) -> FieldInfo:
        return FieldInfo(**dict(row))


field_repository = FieldRepository()
