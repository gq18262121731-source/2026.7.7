from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.risk_fusion import RiskFeatureSnapshot, RiskFusionResponse, UavIndexAnalysis


class RiskFusionRepository:
    def save_uav_index_analysis(self, item: UavIndexAnalysis) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO uav_index_analysis (
                        analysis_id, uav_task_id, field_id, index_type, mean_value, std_value,
                        min_value, max_value, z_threshold, abnormal_pixel_ratio,
                        abnormal_area_ratio, index_anomaly_score, abnormal_level, data_mode,
                        is_mock, main_reasons_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.analysis_id,
                        item.uav_task_id,
                        item.field_id,
                        item.index_type,
                        item.mean_value,
                        item.std_value,
                        item.min_value,
                        item.max_value,
                        item.z_threshold,
                        item.abnormal_pixel_ratio,
                        item.abnormal_area_ratio,
                        item.index_anomaly_score,
                        item.abnormal_level,
                        item.data_mode,
                        int(item.is_mock),
                        json.dumps(item.main_reasons, ensure_ascii=False),
                        item.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV index analysis save failed", {"reason": str(exc)}) from exc

    def list_uav_index_analysis(self, uav_task_id: str) -> list[UavIndexAnalysis]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM uav_index_analysis WHERE uav_task_id = ? ORDER BY index_type",
                    (uav_task_id,),
                ).fetchall()
            return [self._row_to_index_analysis(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "UAV index analysis query failed", {"reason": str(exc)}) from exc

    def save_feature_snapshot(self, item: RiskFeatureSnapshot) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO risk_feature_snapshots (
                        feature_id, prediction_id, field_id, uav_task_id, abnormal_region_id,
                        phone_image_id, disease_type, ndvi_mean, ndvi_std, ndvi_min, ndvi_max,
                        ndre_mean, ndre_std, ndre_min, ndre_max, abnormal_area_ratio,
                        uav_risk_score, phone_confidence, image_risk_score, severity_level,
                        humidity_avg, rainfall_3d, rainfall_7d, continuous_rain_days,
                        environment_risk_score, growth_stage, growth_stage_risk_score,
                        historical_same_disease, history_risk_score, recent_treatment,
                        treatment_effect, treatment_risk_score, factor_scores_json,
                        main_factors_json, total_risk_score, risk_level, model_type,
                        model_stage, probability_claim, feature_payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.feature_id,
                        item.prediction_id,
                        item.field_id,
                        item.uav_task_id,
                        item.abnormal_region_id,
                        item.phone_image_id,
                        item.disease_type,
                        item.ndvi_mean,
                        item.ndvi_std,
                        item.ndvi_min,
                        item.ndvi_max,
                        item.ndre_mean,
                        item.ndre_std,
                        item.ndre_min,
                        item.ndre_max,
                        item.abnormal_area_ratio,
                        item.uav_risk_score,
                        item.phone_confidence,
                        item.image_risk_score,
                        item.severity_level,
                        item.humidity_avg,
                        item.rainfall_3d,
                        item.rainfall_7d,
                        item.continuous_rain_days,
                        item.environment_risk_score,
                        item.growth_stage,
                        item.growth_stage_risk_score,
                        int(item.historical_same_disease),
                        item.history_risk_score,
                        item.recent_treatment,
                        item.treatment_effect,
                        item.treatment_risk_score,
                        json.dumps(item.factor_scores, ensure_ascii=False),
                        json.dumps(item.main_factors, ensure_ascii=False),
                        item.total_risk_score,
                        item.risk_level,
                        item.model_type,
                        item.model_stage,
                        int(item.probability_claim),
                        json.dumps(item.feature_payload, ensure_ascii=False),
                        item.created_at,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "Risk feature snapshot save failed", {"reason": str(exc)}) from exc

    def save_fusion_prediction(self, item: RiskFusionResponse, snapshot: RiskFeatureSnapshot) -> None:
        suggestion_json = json.dumps(
            {
                "title": "Rule-weighted multisource risk score",
                "content": item.safety_note,
                "need_expert_confirm": True,
                "actions": ["field_review", "expert_confirmation"],
                "knowledge_tags": ["risk_fusion", item.risk_level],
                "disclaimer": item.safety_note,
            },
            ensure_ascii=False,
        )
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO risk_predictions (
                        prediction_id, plot_id, prediction_time, prediction_window_days,
                        predicted_disease, risk_score, risk_probability, risk_level,
                        main_factors_json, suggestion_json, model_type, model_version,
                        input_snapshot_json, created_at, uav_risk_score, image_risk_score,
                        environment_risk_score, growth_stage_risk_score, history_risk_score,
                        treatment_risk_score, factor_scores_json, probability_claim, model_stage
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.prediction_id,
                        item.field_id,
                        item.created_at,
                        0,
                        item.disease_type,
                        item.total_risk_score,
                        0.0,
                        item.risk_level,
                        json.dumps(item.main_factors, ensure_ascii=False),
                        suggestion_json,
                        item.model_type,
                        "p9-rule-weighted-v0.1",
                        json.dumps(snapshot.model_dump(), ensure_ascii=False),
                        item.created_at,
                        item.factor_scores.get("uav", 0),
                        item.factor_scores.get("image", 0),
                        item.factor_scores.get("environment", 0),
                        item.factor_scores.get("growth_stage", 0),
                        item.factor_scores.get("history", 0),
                        item.factor_scores.get("treatment", 0),
                        json.dumps(item.factor_scores, ensure_ascii=False),
                        int(item.probability_claim),
                        item.model_stage,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "Risk fusion prediction save failed", {"reason": str(exc)}) from exc

    def get_fusion_prediction(self, prediction_id: str) -> RiskFusionResponse | None:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM risk_predictions WHERE prediction_id = ?",
                    (prediction_id,),
                ).fetchone()
                snapshot = conn.execute(
                    "SELECT * FROM risk_feature_snapshots WHERE prediction_id = ? ORDER BY created_at DESC LIMIT 1",
                    (prediction_id,),
                ).fetchone()
            if not row:
                return None
            return self._row_to_fusion_response(row, snapshot)
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "Risk fusion prediction query failed", {"reason": str(exc)}) from exc

    def list_fusion_predictions(self, field_id: str, limit: int = 100) -> list[RiskFusionResponse]:
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM risk_predictions
                    WHERE plot_id = ? AND model_type = 'rule_weighted_score'
                    ORDER BY prediction_time DESC LIMIT ?
                    """,
                    (field_id, limit),
                ).fetchall()
                snapshots = {
                    row["prediction_id"]: row
                    for row in conn.execute(
                        "SELECT * FROM risk_feature_snapshots WHERE field_id = ? ORDER BY created_at DESC",
                        (field_id,),
                    ).fetchall()
                }
            return [self._row_to_fusion_response(row, snapshots.get(row["prediction_id"])) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "Risk fusion prediction list failed", {"reason": str(exc)}) from exc

    def _row_to_index_analysis(self, row: sqlite3.Row) -> UavIndexAnalysis:
        return UavIndexAnalysis(
            analysis_id=row["analysis_id"],
            uav_task_id=row["uav_task_id"],
            field_id=row["field_id"],
            index_type=row["index_type"],
            mean_value=row["mean_value"],
            std_value=row["std_value"],
            min_value=row["min_value"],
            max_value=row["max_value"],
            z_threshold=row["z_threshold"],
            abnormal_pixel_ratio=row["abnormal_pixel_ratio"],
            abnormal_area_ratio=row["abnormal_area_ratio"] or 0.0,
            index_anomaly_score=int(row["index_anomaly_score"] or 0),
            abnormal_level=row["abnormal_level"],
            main_reasons=json.loads(row["main_reasons_json"] or "[]"),
            data_mode=row["data_mode"],
            is_mock=bool(row["is_mock"]),
            created_at=row["created_at"],
        )

    def _row_to_fusion_response(self, row: sqlite3.Row, snapshot: sqlite3.Row | None) -> RiskFusionResponse:
        keys = set(row.keys())
        factor_scores = json.loads(row["factor_scores_json"] or "{}") if "factor_scores_json" in keys else {}
        if not factor_scores:
            factor_scores = {
                "uav": row["uav_risk_score"] or 0,
                "image": row["image_risk_score"] or 0,
                "environment": row["environment_risk_score"] or 0,
                "growth_stage": row["growth_stage_risk_score"] or 0,
                "history": row["history_risk_score"] or 0,
                "treatment": row["treatment_risk_score"] or 0,
            }
        return RiskFusionResponse(
            prediction_id=row["prediction_id"],
            field_id=row["plot_id"],
            uav_task_id=snapshot["uav_task_id"] if snapshot else None,
            abnormal_region_id=snapshot["abnormal_region_id"] if snapshot else None,
            phone_image_id=snapshot["phone_image_id"] if snapshot else None,
            disease_type=row["predicted_disease"],
            total_risk_score=int(row["risk_score"] or 0),
            risk_level=row["risk_level"],
            factor_scores={key: int(value or 0) for key, value in factor_scores.items()},
            main_factors=json.loads(row["main_factors_json"] or "[]"),
            feature_snapshot_id=snapshot["feature_id"] if snapshot else None,
            model_type=row["model_type"],
            model_stage=row["model_stage"] if "model_stage" in keys and row["model_stage"] else "experimental",
            probability_claim=bool(row["probability_claim"]) if "probability_claim" in keys else False,
            created_at=row["created_at"],
        )


risk_fusion_repository = RiskFusionRepository()
