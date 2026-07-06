from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.alert import AlertAction, AlertDetail


class AlertRepository:
    def save(self, alert: AlertDetail) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO alerts (
                        alert_id, plot_id, plot_name, region_name, main_disease,
                        severity, risk_level, status, message, suggestion_json,
                        record_ids_json, first_record_id, latest_record_id,
                        first_seen_at, latest_seen_at, cooldown_until, created_at, updated_at,
                        alert_source, prediction_id, prediction_window_days
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._params(alert),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u4e8b\u4ef6\u4fdd\u5b58\u5931\u8d25", {"reason": str(exc)}) from exc

    def update(self, alert: AlertDetail) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE alerts
                    SET plot_name = ?, region_name = ?, main_disease = ?, severity = ?,
                        risk_level = ?, status = ?, message = ?, suggestion_json = ?,
                        record_ids_json = ?, latest_record_id = ?, latest_seen_at = ?,
                        cooldown_until = ?, updated_at = ?, alert_source = ?,
                        prediction_id = ?, prediction_window_days = ?
                    WHERE alert_id = ?
                    """,
                    (
                        alert.plot_name,
                        alert.region_name,
                        alert.main_disease,
                        alert.severity,
                        alert.risk_level,
                        alert.status,
                        alert.message,
                        alert.suggestion.model_dump_json(),
                        json.dumps(alert.record_ids, ensure_ascii=False),
                        alert.latest_record_id,
                        alert.latest_seen_at,
                        alert.cooldown_until,
                        alert.updated_at,
                        alert.alert_source,
                        alert.prediction_id,
                        alert.prediction_window_days,
                        alert.alert_id,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u4e8b\u4ef6\u66f4\u65b0\u5931\u8d25", {"reason": str(exc)}) from exc

    def find_active_in_cooldown(
        self,
        plot_id: str,
        main_disease: str | None,
        now: str,
    ) -> AlertDetail | None:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM alerts
                    WHERE plot_id = ?
                      AND COALESCE(main_disease, '') = COALESCE(?, '')
                      AND status = 'active'
                      AND cooldown_until >= ?
                    ORDER BY latest_seen_at DESC
                    LIMIT 1
                    """,
                    (plot_id, main_disease, now),
                ).fetchone()
            return self._row_to_alert(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u4e8b\u4ef6\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def get(self, alert_id: str) -> AlertDetail | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
            return self._row_to_alert(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u8be6\u60c5\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def list_alerts(
        self,
        status: str | None = None,
        risk_level: str | None = None,
        plot_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[AlertDetail]:
        where_sql, params = self._where(status, risk_level, plot_id)
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM alerts {where_sql} ORDER BY latest_seen_at DESC LIMIT ? OFFSET ?",
                    [*params, page_size, (page - 1) * page_size],
                ).fetchall()
            return [self._row_to_alert(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u5217\u8868\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def count_alerts(
        self,
        status: str | None = None,
        risk_level: str | None = None,
        plot_id: str | None = None,
    ) -> int:
        where_sql, params = self._where(status, risk_level, plot_id)
        try:
            with get_connection() as conn:
                row = conn.execute(f"SELECT COUNT(*) AS total FROM alerts {where_sql}", params).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u7edf\u8ba1\u5931\u8d25", {"reason": str(exc)}) from exc

    def latest_for_plot(self, plot_id: str) -> AlertDetail | None:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM alerts WHERE plot_id = ? ORDER BY latest_seen_at DESC LIMIT 1",
                    (plot_id,),
                ).fetchone()
            return self._row_to_alert(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u5730\u5757\u6700\u65b0\u9884\u8b66\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def save_action(self, action: AlertAction) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO alert_actions (
                        action_id, alert_id, action_type, operator_id,
                        operator_name, note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action.action_id,
                        action.alert_id,
                        action.action_type,
                        action.operator_id,
                        action.operator_name,
                        action.note,
                        action.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u5904\u7406\u8bb0\u5f55\u4fdd\u5b58\u5931\u8d25", {"reason": str(exc)}) from exc

    def list_actions(self, alert_id: str) -> list[AlertAction]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM alert_actions WHERE alert_id = ? ORDER BY created_at ASC",
                    (alert_id,),
                ).fetchall()
            return [self._row_to_action(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9884\u8b66\u5904\u7406\u8bb0\u5f55\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def _where(self, status: str | None, risk_level: str | None, plot_id: str | None) -> tuple[str, list[str]]:
        clauses: list[str] = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if risk_level:
            clauses.append("risk_level = ?")
            params.append(risk_level)
        if plot_id:
            clauses.append("plot_id = ?")
            params.append(plot_id)
        return (f"WHERE {' AND '.join(clauses)}" if clauses else ""), params

    def _params(self, alert: AlertDetail) -> tuple:
        return (
            alert.alert_id,
            alert.plot_id,
            alert.plot_name,
            alert.region_name,
            alert.main_disease,
            alert.severity,
            alert.risk_level,
            alert.status,
            alert.message,
            alert.suggestion.model_dump_json(),
            json.dumps(alert.record_ids, ensure_ascii=False),
            alert.first_record_id,
            alert.latest_record_id,
            alert.first_seen_at,
            alert.latest_seen_at,
            alert.cooldown_until,
            alert.created_at,
            alert.updated_at,
            alert.alert_source,
            alert.prediction_id,
            alert.prediction_window_days,
        )

    def _row_to_alert(self, row: sqlite3.Row) -> AlertDetail:
        keys = set(row.keys())
        return AlertDetail(
            alert_id=row["alert_id"],
            alert_source=row["alert_source"] if "alert_source" in keys and row["alert_source"] else "detection",
            plot_id=row["plot_id"],
            plot_name=row["plot_name"],
            region_name=row["region_name"],
            main_disease=row["main_disease"],
            severity=row["severity"],
            risk_level=row["risk_level"],
            status=row["status"],
            message=row["message"],
            suggestion=json.loads(row["suggestion_json"]),
            record_ids=json.loads(row["record_ids_json"]),
            first_record_id=row["first_record_id"],
            latest_record_id=row["latest_record_id"],
            prediction_id=row["prediction_id"] if "prediction_id" in keys else None,
            prediction_window_days=row["prediction_window_days"] if "prediction_window_days" in keys else None,
            first_seen_at=row["first_seen_at"],
            latest_seen_at=row["latest_seen_at"],
            cooldown_until=row["cooldown_until"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_action(self, row: sqlite3.Row) -> AlertAction:
        return AlertAction(
            action_id=row["action_id"],
            alert_id=row["alert_id"],
            action_type=row["action_type"],
            operator_id=row["operator_id"],
            operator_name=row["operator_name"],
            note=row["note"],
            created_at=row["created_at"],
        )
