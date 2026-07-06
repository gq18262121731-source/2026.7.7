from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.detection_result import DetectionResult
from app.services.inference.model_display import get_model_display_info


class DetectionRecordRepository:
    def save(self, result: DetectionResult) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO detection_records (
                        record_id, image_id, field_id, plot_id, plot_name, region_name, timestamp,
                        image_url, result_image_url, image_width, image_height,
                        source_type, model_name, model_version, detector_mode,
                        is_smoke, model_stage, formal_metric_available, current_target_type, category_type, fallback_to_mock,
                        model_hint, target_type, uav_task_id, abnormal_region_id,
                        model_display_name, model_warning, model_usage_scope, model_capability_level,
                        task_type, result_type, disease_name, model_sha256, input_config,
                        threshold, min_area, disease_area_ratio, mask_url, overlay_url,
                        probability_map_url, production_scope, human_review_required,
                        human_review_status, human_review_label, issue_tags_json, reviewer_note,
                        alerting_enabled, latest_alerts_enabled, active_model_version,
                        lng, lat, detections_json, severity, risk_level, main_disease,
                        suggestion_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.record_id,
                        result.image_id,
                        result.field_id,
                        result.plot_id,
                        result.plot_name,
                        result.region_name,
                        result.timestamp,
                        result.image_url,
                        result.result_image_url,
                        result.image_width,
                        result.image_height,
                        result.source_type,
                        result.model_name,
                        result.model_version,
                        result.detector_mode,
                        int(result.is_smoke),
                        result.model_stage,
                        int(result.formal_metric_available),
                        result.current_target_type,
                        result.category_type,
                        int(result.fallback_to_mock),
                        result.model_hint,
                        result.target_type,
                        result.uav_task_id,
                        result.abnormal_region_id,
                        result.model_display_name,
                        result.model_warning,
                        result.model_usage_scope,
                        result.model_capability_level,
                        result.task_type,
                        result.result_type,
                        result.disease_name,
                        result.model_sha256,
                        result.input_config,
                        result.threshold,
                        result.min_area,
                        result.disease_area_ratio,
                        result.mask_url,
                        result.overlay_url,
                        result.probability_map_url,
                        result.production_scope,
                        int(result.human_review_required),
                        result.human_review_status,
                        result.human_review_label,
                        json.dumps(result.issue_tags, ensure_ascii=False),
                        result.reviewer_note,
                        None if result.alerting_enabled is None else int(result.alerting_enabled),
                        None if result.latest_alerts_enabled is None else int(result.latest_alerts_enabled),
                        result.active_model_version,
                        result.geo.lng,
                        result.geo.lat,
                        json.dumps([item.model_dump() for item in result.detections], ensure_ascii=False),
                        result.summary.severity,
                        result.summary.risk_level,
                        result.summary.main_disease,
                        result.suggestion.model_dump_json(),
                        result.timestamp,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u8bc6\u522b\u8bb0\u5f55\u4fdd\u5b58\u5931\u8d25", {"reason": str(exc)}) from exc

    def get_by_record_id(self, record_id: str) -> DetectionResult | None:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT * FROM detection_records WHERE record_id = ?", (record_id,)).fetchone()
            return self._row_to_result(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u8bc6\u522b\u8bb0\u5f55\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def list_records(
        self,
        plot_id: str | None = None,
        risk_level: str | None = None,
        severity: str | None = None,
        disease: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort: str = "created_at_desc",
        limit: int | None = None,
    ) -> list[DetectionResult]:
        where_sql, params = self._build_where(plot_id, risk_level, severity, disease, start_time, end_time)
        order_sql = self._sort_sql(sort)
        if limit is not None:
            page_size = limit
            offset = 0
        else:
            offset = (page - 1) * page_size

        query_params = [*params, page_size, offset]
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM detection_records {where_sql} {order_sql} LIMIT ? OFFSET ?",
                    query_params,
                ).fetchall()
            return [self._row_to_result(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u8bc6\u522b\u8bb0\u5f55\u5217\u8868\u67e5\u8be2\u5931\u8d25", {"reason": str(exc)}) from exc

    def count_records(
        self,
        plot_id: str | None = None,
        risk_level: str | None = None,
        severity: str | None = None,
        disease: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        where_sql, params = self._build_where(plot_id, risk_level, severity, disease, start_time, end_time)
        try:
            with get_connection() as conn:
                row = conn.execute(f"SELECT COUNT(*) AS total FROM detection_records {where_sql}", params).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u8bc6\u522b\u8bb0\u5f55\u7edf\u8ba1\u5931\u8d25", {"reason": str(exc)}) from exc

    def count_today(self, date_prefix: str) -> int:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM detection_records WHERE timestamp LIKE ?",
                    (f"{date_prefix}%",),
                ).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u4eca\u65e5\u8bc6\u522b\u6570\u7edf\u8ba1\u5931\u8d25", {"reason": str(exc)}) from exc

    def count_disease_records(self) -> int:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM detection_records WHERE severity != ?",
                    ("\u65e0\u75c5",),
                ).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u75c5\u5bb3\u8bb0\u5f55\u7edf\u8ba1\u5931\u8d25", {"reason": str(exc)}) from exc

    def risk_level_counts(self) -> dict[str, int]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT risk_level, COUNT(*) AS total FROM detection_records GROUP BY risk_level"
                ).fetchall()
            return {row["risk_level"]: int(row["total"]) for row in rows}
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u98ce\u9669\u7edf\u8ba1\u5931\u8d25", {"reason": str(exc)}) from exc

    def high_risk_plot_count(self) -> int:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(DISTINCT COALESCE(plot_id, record_id)) AS total FROM detection_records WHERE risk_level = ?",
                    ("high",),
                ).fetchone()
            return int(row["total"])
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "\u9ad8\u98ce\u9669\u5730\u5757\u7edf\u8ba1\u5931\u8d25", {"reason": str(exc)}) from exc

    def _build_where(
        self,
        plot_id: str | None,
        risk_level: str | None,
        severity: str | None,
        disease: str | None,
        start_time: str | None,
        end_time: str | None,
    ) -> tuple[str, list[str]]:
        clauses: list[str] = []
        params: list[str] = []
        if plot_id:
            clauses.append("plot_id = ?")
            params.append(plot_id)
        if risk_level:
            clauses.append("risk_level = ?")
            params.append(risk_level)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if disease:
            clauses.append("main_disease = ?")
            params.append(disease)
        if start_time:
            clauses.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            clauses.append("timestamp <= ?")
            params.append(end_time)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def _sort_sql(self, sort: str) -> str:
        mapping = {
            "created_at_asc": "ORDER BY created_at ASC",
            "timestamp_desc": "ORDER BY timestamp DESC",
            "timestamp_asc": "ORDER BY timestamp ASC",
            "risk_level_desc": "ORDER BY risk_level DESC, created_at DESC",
            "created_at_desc": "ORDER BY created_at DESC",
        }
        return mapping.get(sort, mapping["created_at_desc"])

    def _row_to_result(self, row: sqlite3.Row) -> DetectionResult:
        detections = json.loads(row["detections_json"])
        suggestion = json.loads(row["suggestion_json"])
        max_confidence = max((item.get("confidence", 0.0) for item in detections), default=0.0)
        keys = set(row.keys())
        model_name = row["model_name"] if "model_name" in keys else "mock_disease_detector"
        display = get_model_display_info(model_name)
        return DetectionResult(
            record_id=row["record_id"],
            image_id=row["image_id"],
            field_id=row["field_id"] if "field_id" in keys and row["field_id"] else row["plot_id"],
            plot_id=row["plot_id"],
            plot_name=row["plot_name"],
            region_name=row["region_name"],
            timestamp=row["timestamp"],
            image_url=row["image_url"],
            result_image_url=row["result_image_url"],
            image_width=row["image_width"],
            image_height=row["image_height"],
            source_type=row["source_type"] if "source_type" in keys else "manual_upload",
            model_name=model_name,
            model_version=row["model_version"] if "model_version" in keys else "mock-v1",
            detector_mode=row["detector_mode"] if "detector_mode" in keys else "mock",
            is_smoke=bool(row["is_smoke"]) if "is_smoke" in keys else False,
            model_stage=row["model_stage"] if "model_stage" in keys else "mock",
            formal_metric_available=bool(row["formal_metric_available"]) if "formal_metric_available" in keys else False,
            current_target_type=row["current_target_type"] if "current_target_type" in keys else None,
            category_type=row["category_type"] if "category_type" in keys else None,
            fallback_to_mock=bool(row["fallback_to_mock"]) if "fallback_to_mock" in keys else False,
            model_hint=row["model_hint"] if "model_hint" in keys else None,
            target_type=row["target_type"] if "target_type" in keys else None,
            uav_task_id=row["uav_task_id"] if "uav_task_id" in keys else None,
            abnormal_region_id=row["abnormal_region_id"] if "abnormal_region_id" in keys else None,
            model_display_name=row["model_display_name"] if "model_display_name" in keys and row["model_display_name"] else display.display_name,
            model_warning=row["model_warning"] if "model_warning" in keys and row["model_warning"] else display.warning,
            model_usage_scope=row["model_usage_scope"] if "model_usage_scope" in keys and row["model_usage_scope"] else display.usage_scope,
            model_capability_level=(
                row["model_capability_level"]
                if "model_capability_level" in keys and row["model_capability_level"]
                else display.capability_level
            ),
            task_type=row["task_type"] if "task_type" in keys else None,
            result_type=row["result_type"] if "result_type" in keys else None,
            disease_name=row["disease_name"] if "disease_name" in keys else None,
            model_sha256=row["model_sha256"] if "model_sha256" in keys else None,
            input_config=row["input_config"] if "input_config" in keys else None,
            threshold=row["threshold"] if "threshold" in keys else None,
            min_area=row["min_area"] if "min_area" in keys else None,
            disease_area_ratio=row["disease_area_ratio"] if "disease_area_ratio" in keys else None,
            mask_url=row["mask_url"] if "mask_url" in keys else None,
            overlay_url=row["overlay_url"] if "overlay_url" in keys else None,
            probability_map_url=row["probability_map_url"] if "probability_map_url" in keys else None,
            production_scope=row["production_scope"] if "production_scope" in keys else None,
            human_review_required=bool(row["human_review_required"]) if "human_review_required" in keys else False,
            human_review_status=row["human_review_status"] if "human_review_status" in keys else None,
            human_review_label=row["human_review_label"] if "human_review_label" in keys else None,
            issue_tags=json.loads(row["issue_tags_json"]) if "issue_tags_json" in keys and row["issue_tags_json"] else [],
            reviewer_note=row["reviewer_note"] if "reviewer_note" in keys else None,
            alerting_enabled=bool(row["alerting_enabled"]) if "alerting_enabled" in keys and row["alerting_enabled"] is not None else None,
            latest_alerts_enabled=(
                bool(row["latest_alerts_enabled"]) if "latest_alerts_enabled" in keys and row["latest_alerts_enabled"] is not None else None
            ),
            active_model_version=row["active_model_version"] if "active_model_version" in keys else None,
            geo={"lng": row["lng"], "lat": row["lat"]},
            detections=detections,
            summary={
                "disease_count": len(detections),
                "main_disease": row["main_disease"],
                "max_confidence": max_confidence,
                "severity": row["severity"],
                "risk_level": row["risk_level"],
            },
            suggestion=suggestion,
        )
