from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.detection_result import Suggestion


RISK_PROBABILITY_NOTE = "当前为规则分数归一化值，不代表真实统计概率。"


class PredictedDisease(BaseModel):
    label: str
    probability: float


class PredictionModelInfo(BaseModel):
    type: str = "rule_based"
    version: str = "risk-rule-v0.1"
    metrics: dict[str, str] = Field(
        default_factory=lambda: {
            "prediction_accuracy": "未指定",
            "auc": "未指定",
            "f1_score": "未指定",
        }
    )


class RiskPredictionResponse(BaseModel):
    plot_id: str
    prediction_window_days: int
    prediction_time: str
    risk_score: int
    risk_probability: float
    risk_probability_note: str = RISK_PROBABILITY_NOTE
    risk_level: str
    predicted_diseases: list[PredictedDisease]
    main_factors: list[str]
    suggestion: Suggestion
    model: PredictionModelInfo
    prediction_id: str | None = None


class PredictionSummaryResponse(BaseModel):
    high_risk_plot_count: int
    medium_risk_plot_count: int
    top_risk_plots: list[dict]
    top_predicted_diseases: list[dict]
    risk_factor_counts: dict[str, int]


class PredictionRiskMapPoint(BaseModel):
    plot_id: str
    plot_name: str | None = None
    lng: float | None = None
    lat: float | None = None
    predicted_risk_level: str
    predicted_disease: str | None = None
    risk_score: int
    intensity: float
    color: str


class PredictionRiskMapResponse(BaseModel):
    type: str = "prediction_risk_map"
    total: int
    points: list[PredictionRiskMapPoint]


class MobilePredictionListResponse(BaseModel):
    items: list[RiskPredictionResponse]
    total: int
