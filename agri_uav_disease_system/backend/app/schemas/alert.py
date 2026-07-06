from __future__ import annotations

from pydantic import BaseModel

from app.schemas.detection_result import DetectionResult, Suggestion


class AlertEvent(BaseModel):
    type: str = "alert_event"
    alert_source: str = "detection"
    alert_id: str
    plot_id: str
    plot_name: str | None = None
    region_name: str
    main_disease: str | None = None
    severity: str
    risk_level: str
    status: str
    message: str
    latest_record_id: str
    prediction_id: str | None = None
    prediction_window_days: int | None = None
    timestamp: str


class AlertDetail(BaseModel):
    alert_id: str
    alert_source: str = "detection"
    plot_id: str
    plot_name: str | None = None
    region_name: str
    main_disease: str | None = None
    severity: str
    risk_level: str
    status: str
    message: str
    suggestion: Suggestion
    record_ids: list[str]
    first_record_id: str
    latest_record_id: str
    prediction_id: str | None = None
    prediction_window_days: int | None = None
    first_seen_at: str
    latest_seen_at: str
    cooldown_until: str
    created_at: str
    updated_at: str


class AlertPageResponse(BaseModel):
    items: list[AlertDetail]
    total: int
    page: int
    page_size: int


class AlertListResponse(BaseModel):
    total: int
    alerts: list[DetectionResult]


class AlertResolveRequest(BaseModel):
    operator_id: str | None = None
    operator_name: str | None = None
    note: str | None = None


class AlertAction(BaseModel):
    action_id: str
    alert_id: str
    action_type: str
    operator_id: str | None = None
    operator_name: str | None = None
    note: str | None = None
    created_at: str


class AlertActionListResponse(BaseModel):
    items: list[AlertAction]
    total: int
