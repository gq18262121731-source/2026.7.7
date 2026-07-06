from __future__ import annotations

from pydantic import BaseModel, Field


RULE_RISK_SAFETY_NOTE = (
    "Rule-weighted risk scores are for assisted inspection and experiment review only; "
    "they are not disease probability claims, agronomic diagnoses, or pesticide prescriptions."
)


class UavIndexAnalysis(BaseModel):
    analysis_id: str
    uav_task_id: str
    field_id: str | None = None
    index_type: str
    mean_value: float | None = None
    std_value: float | None = None
    min_value: float | None = None
    max_value: float | None = None
    z_threshold: float = -1.5
    abnormal_pixel_ratio: float | None = None
    abnormal_area_ratio: float = 0.0
    index_anomaly_score: int = 0
    abnormal_level: str = "normal"
    main_reasons: list[str] = Field(default_factory=list)
    data_mode: str = "dry_run"
    is_mock: bool = True
    created_at: str


class UavIndexAnalysisResponse(BaseModel):
    uav_task_id: str
    field_id: str | None = None
    analysis: list[UavIndexAnalysis]
    uav_risk_score: int
    uav_abnormal_level: str
    main_reasons: list[str]
    data_mode: str = "dry_run"
    is_mock: bool = True
    model_stage: str = "experimental"
    probability_claim: bool = False
    safety_note: str = RULE_RISK_SAFETY_NOTE


class RiskFusionEvaluateRequest(BaseModel):
    field_id: str
    uav_task_id: str | None = None
    abnormal_region_id: str | None = None
    phone_image_id: str | None = None
    include_weather: bool = True
    include_history: bool = True
    include_treatment: bool = True


class RiskFeatureSnapshot(BaseModel):
    feature_id: str
    prediction_id: str | None = None
    field_id: str
    uav_task_id: str | None = None
    abnormal_region_id: str | None = None
    phone_image_id: str | None = None
    disease_type: str | None = None
    ndvi_mean: float | None = None
    ndvi_std: float | None = None
    ndvi_min: float | None = None
    ndvi_max: float | None = None
    ndre_mean: float | None = None
    ndre_std: float | None = None
    ndre_min: float | None = None
    ndre_max: float | None = None
    abnormal_area_ratio: float | None = None
    uav_risk_score: int = 0
    phone_confidence: float | None = None
    image_risk_score: int = 0
    severity_level: str | None = None
    humidity_avg: float | None = None
    rainfall_3d: float | None = None
    rainfall_7d: float | None = None
    continuous_rain_days: int = 0
    environment_risk_score: int = 0
    growth_stage: str | None = None
    growth_stage_risk_score: int = 0
    historical_same_disease: bool = False
    history_risk_score: int = 0
    recent_treatment: str | None = None
    treatment_effect: str | None = None
    treatment_risk_score: int = 0
    factor_scores: dict[str, int] = Field(default_factory=dict)
    main_factors: list[str] = Field(default_factory=list)
    total_risk_score: int = 0
    risk_level: str = "low"
    model_type: str = "rule_weighted_score"
    model_stage: str = "experimental"
    probability_claim: bool = False
    feature_payload: dict = Field(default_factory=dict)
    created_at: str


class RiskFusionResponse(BaseModel):
    prediction_id: str
    field_id: str
    uav_task_id: str | None = None
    abnormal_region_id: str | None = None
    phone_image_id: str | None = None
    disease_type: str | None = None
    total_risk_score: int
    risk_level: str
    factor_scores: dict[str, int]
    main_factors: list[str]
    feature_snapshot_id: str | None = None
    model_type: str = "rule_weighted_score"
    model_stage: str = "experimental"
    probability_claim: bool = False
    experimental_only: bool = True
    not_for_production: bool = True
    safety_note: str = RULE_RISK_SAFETY_NOTE
    created_at: str


class RiskFusionListResponse(BaseModel):
    items: list[RiskFusionResponse]
    total: int
