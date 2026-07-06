from __future__ import annotations

from pydantic import BaseModel, Field


class Geo(BaseModel):
    lng: float | None = None
    lat: float | None = None


class Detection(BaseModel):
    class_id: int
    label: str
    class_name: str | None = None
    category_type: str | None = None
    class_code: str | None = None
    confidence: float
    bbox: list[int] = Field(..., min_length=4, max_length=4)
    area_ratio: float


class DetectionSummary(BaseModel):
    disease_count: int
    main_disease: str | None = None
    max_confidence: float
    severity: str
    risk_level: str


class Suggestion(BaseModel):
    title: str
    content: str
    need_expert_confirm: bool = True
    actions: list[str] = []
    knowledge_tags: list[str] = []
    disclaimer: str | None = None


class DetectionResult(BaseModel):
    type: str = "detection_result"
    record_id: str
    image_id: str
    field_id: str | None = None
    plot_id: str | None = None
    plot_name: str | None = None
    region_name: str
    timestamp: str
    image_url: str
    result_image_url: str
    image_width: int
    image_height: int
    source_type: str
    model_name: str
    model_version: str
    detector_mode: str
    is_smoke: bool = False
    model_stage: str = "mock"
    formal_metric_available: bool = False
    current_target_type: str | None = None
    category_type: str | None = None
    fallback_to_mock: bool = False
    model_hint: str | None = None
    target_type: str | None = None
    model_stage_hint: str | None = None
    uav_task_id: str | None = None
    abnormal_region_id: str | None = None
    model_display_name: str | None = None
    model_warning: str | None = None
    model_usage_scope: str | None = None
    model_capability_level: str | None = None
    task_type: str | None = None
    result_type: str | None = None
    disease_name: str | None = None
    model_sha256: str | None = None
    input_config: str | None = None
    threshold: float | None = None
    min_area: int | None = None
    disease_area_ratio: float | None = None
    mask_url: str | None = None
    overlay_url: str | None = None
    probability_map_url: str | None = None
    production_scope: str | None = None
    human_review_required: bool = False
    human_review_status: str | None = None
    human_review_label: str | None = None
    issue_tags: list[str] = Field(default_factory=list)
    reviewer_note: str | None = None
    alerting_enabled: bool | None = None
    latest_alerts_enabled: bool | None = None
    active_model_version: str | None = None
    geo: Geo
    detections: list[Detection]
    summary: DetectionSummary
    suggestion: Suggestion
