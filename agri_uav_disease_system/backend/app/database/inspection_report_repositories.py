from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.inspection_report import InspectionReport


class InspectionReportRepository:
    def save(self, report: InspectionReport) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO inspection_reports (
                        report_id, field_id, uav_task_id, report_title, report_date, summary,
                        uav_summary_json, abnormal_region_summary_json, phone_followup_summary_json,
                        risk_summary_json, risk_model_detail_json, rag_suggestion, model_safety_note, report_status,
                        payload_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.report_id,
                        report.field_id,
                        report.uav_task_id,
                        report.report_title,
                        report.report_date,
                        report.summary,
                        json.dumps(report.uav_summary, ensure_ascii=False),
                        json.dumps(report.abnormal_region_summary, ensure_ascii=False),
                        json.dumps(report.phone_followup_summary, ensure_ascii=False),
                        json.dumps(report.risk_summary, ensure_ascii=False),
                        json.dumps(report.risk_model_detail, ensure_ascii=False),
                        report.rag_suggestion,
                        report.model_safety_note,
                        report.report_status,
                        json.dumps(report.payload, ensure_ascii=False),
                        report.created_at,
                        report.updated_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "巡检报告保存失败", {"reason": str(exc)}) from exc

    def get(self, report_id: str) -> InspectionReport | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM inspection_reports WHERE report_id = ?", (report_id,)).fetchone()
            return self._row_to_report(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "巡检报告查询失败", {"reason": str(exc)}) from exc

    def list_reports(self, field_id: str | None = None) -> list[InspectionReport]:
        where = "WHERE field_id = ?" if field_id else ""
        params: list[object] = [field_id] if field_id else []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM inspection_reports {where} ORDER BY report_date DESC",
                    params,
                ).fetchall()
            return [self._row_to_report(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "巡检报告列表查询失败", {"reason": str(exc)}) from exc

    def _row_to_report(self, row: sqlite3.Row) -> InspectionReport:
        return InspectionReport(
            report_id=row["report_id"],
            field_id=row["field_id"],
            uav_task_id=row["uav_task_id"],
            report_title=row["report_title"],
            report_date=row["report_date"],
            summary=row["summary"],
            uav_summary=json.loads(row["uav_summary_json"] or "{}"),
            abnormal_region_summary=json.loads(row["abnormal_region_summary_json"] or "{}"),
            phone_followup_summary=json.loads(row["phone_followup_summary_json"] or "{}"),
            risk_summary=json.loads(row["risk_summary_json"] or "{}"),
            risk_model_detail=json.loads(row["risk_model_detail_json"] or "{}")
            if "risk_model_detail_json" in row.keys()
            else {},
            rag_suggestion=row["rag_suggestion"],
            model_safety_note=row["model_safety_note"],
            report_status=row["report_status"],
            payload=json.loads(row["payload_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


inspection_report_repository = InspectionReportRepository()
