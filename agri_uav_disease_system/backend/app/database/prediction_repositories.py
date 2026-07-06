from __future__ import annotations

import json
import sqlite3

from app.core.constants import ERROR_DATABASE
from app.core.exceptions import AppException
from app.database.database import get_connection
from app.schemas.detection_result import Suggestion
from app.schemas.prediction import PredictedDisease, PredictionModelInfo, RiskPredictionResponse


class PredictionRepository:
    def save(self, prediction: RiskPredictionResponse, input_snapshot: dict) -> None:
        try:
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO risk_predictions (
                        prediction_id, plot_id, prediction_time, prediction_window_days,
                        predicted_disease, risk_score, risk_probability, risk_level,
                        main_factors_json, suggestion_json, model_type, model_version,
                        input_snapshot_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prediction.prediction_id,
                        prediction.plot_id,
                        prediction.prediction_time,
                        prediction.prediction_window_days,
                        prediction.predicted_diseases[0].label if prediction.predicted_diseases else None,
                        prediction.risk_score,
                        prediction.risk_probability,
                        prediction.risk_level,
                        json.dumps(prediction.main_factors, ensure_ascii=False),
                        prediction.suggestion.model_dump_json(),
                        prediction.model.type,
                        prediction.model.version,
                        json.dumps(input_snapshot, ensure_ascii=False),
                        prediction.prediction_time,
                    ),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "预测结果保存失败", {"reason": str(exc)}) from exc

    def latest_for_plot(self, plot_id: str) -> RiskPredictionResponse | None:
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM risk_predictions WHERE plot_id = ? ORDER BY prediction_time DESC LIMIT 1",
                    (plot_id,),
                ).fetchone()
            return self._row_to_prediction(row) if row else None
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "地块预测结果查询失败", {"reason": str(exc)}) from exc

    def list_predictions(self, plot_id: str | None = None, limit: int = 100) -> list[RiskPredictionResponse]:
        clauses: list[str] = []
        params: list[object] = []
        if plot_id:
            clauses.append("plot_id = ?")
            params.append(plot_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    f"SELECT * FROM risk_predictions {where_sql} ORDER BY prediction_time DESC LIMIT ?",
                    [*params, limit],
                ).fetchall()
            return [self._row_to_prediction(row) for row in rows]
        except sqlite3.Error as exc:
            raise AppException(ERROR_DATABASE, "预测结果列表查询失败", {"reason": str(exc)}) from exc

    def _row_to_prediction(self, row: sqlite3.Row) -> RiskPredictionResponse:
        disease = row["predicted_disease"]
        probability = float(row["risk_probability"] or 0)
        return RiskPredictionResponse(
            plot_id=row["plot_id"],
            prediction_window_days=int(row["prediction_window_days"]),
            prediction_time=row["prediction_time"],
            risk_score=int(row["risk_score"]),
            risk_probability=probability,
            risk_level=row["risk_level"],
            predicted_diseases=[PredictedDisease(label=disease, probability=probability)] if disease else [],
            main_factors=json.loads(row["main_factors_json"] or "[]"),
            suggestion=Suggestion(**json.loads(row["suggestion_json"])),
            model=PredictionModelInfo(type=row["model_type"], version=row["model_version"]),
            prediction_id=row["prediction_id"],
        )
