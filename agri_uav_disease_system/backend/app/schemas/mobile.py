from __future__ import annotations

from pydantic import BaseModel

from app.schemas.dashboard import LatestAlertItem, LatestRecordItem
from app.schemas.detection_result import Detection, Suggestion


class MobileOverview(BaseModel):
    today_detect_count: int
    my_plot_count: int
    high_risk_count: int
    medium_risk_count: int
    latest_alerts: list[LatestAlertItem]
    latest_records: list[LatestRecordItem]
    summary_text: str


class MobilePlotItem(BaseModel):
    plot_id: str
    plot_name: str | None = None
    region_name: str
    risk_level: str
    max_severity: str
    main_disease: str | None = None
    latest_detect_time: str
    suggestion_summary: str


class MobilePlotListResponse(BaseModel):
    items: list[MobilePlotItem]
    total: int


class MobilePlotDetail(BaseModel):
    plot_id: str
    plot_name: str | None = None
    risk_level: str
    risk_text: str
    main_disease: str | None = None
    severity: str
    latest_result_image_url: str
    latest_detect_time: str
    suggestion: Suggestion
    recent_records: list[LatestRecordItem]


class MobileRecordDetail(BaseModel):
    record_id: str
    plot_id: str | None = None
    plot_name: str | None = None
    image_url: str
    result_image_url: str
    main_disease: str | None = None
    severity: str
    risk_level: str
    detections: list[Detection]
    suggestion: Suggestion
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
