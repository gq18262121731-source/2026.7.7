from __future__ import annotations

from pydantic import BaseModel

from app.schemas.detection_result import DetectionResult, Geo


class DiseaseStatisticItem(BaseModel):
    label: str
    count: int
    ratio: float
    risk_level_max: str | None = None


class DiseaseStatisticsResponse(BaseModel):
    items: list[DiseaseStatisticItem]


class PlotStatisticItem(BaseModel):
    plot_id: str
    plot_name: str | None = None
    region_name: str
    record_count: int
    disease_record_count: int
    main_disease: str | None = None
    max_severity: str
    risk_level: str
    latest_detect_time: str
    geo: Geo


class PlotStatisticsResponse(BaseModel):
    total: int
    items: list[PlotStatisticItem]


class DiseaseTypeCount(BaseModel):
    label: str
    count: int


class PlotDetailResponse(BaseModel):
    plot_id: str
    plot_name: str | None = None
    region_name: str
    geo: Geo
    record_count: int
    disease_record_count: int
    normal_record_count: int
    main_disease: str | None = None
    disease_types: list[DiseaseTypeCount]
    max_severity: str
    risk_level: str
    latest_detect_time: str
    latest_record: DetectionResult
    latest_alert: object | None = None
    suggestion_summary: str


class HeatmapPoint(BaseModel):
    plot_id: str
    plot_name: str | None = None
    region_name: str
    lng: float
    lat: float
    risk_level: str
    severity: str
    main_disease: str | None = None
    intensity: float
    color: str
    record_count: int


class HeatmapResponse(BaseModel):
    type: str = "heatmap_data"
    total: int
    points: list[HeatmapPoint]


class LatestRecordItem(BaseModel):
    record_id: str
    plot_name: str | None = None
    main_disease: str | None = None
    severity: str
    risk_level: str
    result_image_url: str
    timestamp: str
    source_type: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    detector_mode: str | None = None
    is_smoke: bool = False
    model_stage: str | None = None
    formal_metric_available: bool = False
    current_target_type: str | None = None
    fallback_to_mock: bool = False
    model_hint: str | None = None
    target_type: str | None = None
    model_display_name: str | None = None
    model_warning: str | None = None
    model_usage_scope: str | None = None
    model_capability_level: str | None = None


class LatestRecordsResponse(BaseModel):
    items: list[LatestRecordItem]


class LatestAlertItem(BaseModel):
    alert_id: str
    record_id: str
    plot_id: str | None = None
    plot_name: str | None = None
    main_disease: str | None = None
    severity: str
    risk_level: str
    message: str
    timestamp: str
    is_smoke: bool = False
    model_stage: str | None = None
    current_target_type: str | None = None
    model_name: str | None = None
    fallback_to_mock: bool = False
    model_warning: str | None = None


class LatestAlertsResponse(BaseModel):
    items: list[LatestAlertItem]


class DashboardSummary(BaseModel):
    today_detect_count: int
    total_record_count: int
    disease_record_count: int
    normal_record_count: int
    high_risk_plot_count: int
    medium_risk_plot_count: int
    low_risk_plot_count: int
    risk_level_counts: dict[str, int]
    severity_counts: dict[str, int]
    top_diseases: list[DiseaseStatisticItem]
    latest_alerts: list[LatestAlertItem]
    latest_records: list[LatestRecordItem]
