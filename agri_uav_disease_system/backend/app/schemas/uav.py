from __future__ import annotations

from pydantic import BaseModel, Field


class UavTaskCreate(BaseModel):
    field_id: str | None = None
    task_name: str
    flight_date: str | None = None
    sensor_type: str = "multispectral"
    data_mode: str = "dry_run"
    growth_stage: str | None = None
    weather_text: str | None = None


class UavTask(UavTaskCreate):
    uav_task_id: str
    status: str
    summary: str | None = None
    is_mock: bool = True
    created_at: str
    updated_at: str


class UavTaskListResponse(BaseModel):
    items: list[UavTask]
    total: int
    page: int
    page_size: int


class UavDryRunRequest(BaseModel):
    field_id: str | None = None
    task_name: str | None = None
    sensor_type: str = "multispectral"
    growth_stage: str | None = None
    weather_text: str | None = None
    dry_run_profile: str = "moderate_abnormal"


class UavImage(BaseModel):
    uav_image_id: str
    uav_task_id: str
    field_id: str | None = None
    image_url: str
    image_type: str
    band_type: str | None = None
    index_type: str | None = None
    capture_time: str | None = None
    lat: float | None = None
    lng: float | None = None
    created_at: str


class UavIndexResult(BaseModel):
    index_result_id: str
    uav_task_id: str
    field_id: str | None = None
    index_type: str
    index_image_url: str
    min_value: float | None = None
    max_value: float | None = None
    mean_value: float | None = None
    threshold_used: float | None = None
    abnormal_area_ratio: float
    data_mode: str = "dry_run"
    is_mock: bool = True
    created_at: str


class AbnormalRegion(BaseModel):
    region_id: str
    uav_task_id: str
    field_id: str | None = None
    region_name: str
    region_image_url: str | None = None
    region_polygon: list[dict] | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    abnormal_type: str
    abnormal_level: str
    abnormal_area_ratio: float
    source_index_type: str
    confirm_status: str
    linked_phone_image_id: str | None = None
    linked_record_id: str | None = None
    confirmed_disease_type: str | None = None
    confirm_confidence: float | None = None
    confirm_source: str | None = None
    confirmed_at: str | None = None
    phone_inference: dict | None = None
    created_at: str
    updated_at: str


class UavDryRunResponse(BaseModel):
    uav_task_id: str
    field_id: str | None = None
    status: str
    data_mode: str = "dry_run"
    is_mock: bool = True
    mock_safety_note: str = Field(
        default="UAV dry-run 使用占位指数图和规则生成异常区域，仅用于工程闭环演示，不代表真实多光谱生产结果。"
    )
    indices: list[UavIndexResult]
    abnormal_regions: list[AbnormalRegion]


class UavIndexListResponse(BaseModel):
    items: list[UavIndexResult]
    total: int


class AbnormalRegionListResponse(BaseModel):
    items: list[AbnormalRegion]
    total: int
