from __future__ import annotations

from pydantic import BaseModel


class CapabilityStatus(BaseModel):
    single_image_detection: bool
    batch_detection: bool
    dashboard_api: bool
    mobile_api: bool
    alert_governance: bool
    ws_results: bool
    ws_tasks: bool
    ws_alerts: bool
    real_model_ready: bool
    mock_mode: bool


class ModelCapabilityStatus(BaseModel):
    detector_mode: str
    current_model: str
    uav_model_path_configured: bool
    phone_model_path_configured: bool


class StorageStatus(BaseModel):
    database_status: str
    static_original_writable: bool
    static_result_writable: bool


class StatusResponse(BaseModel):
    service_status: str
    model_loaded: bool
    model_name: str
    model_version: str
    detector_mode: str
    database_status: str
    storage_status: str
    websocket_clients: int
    capabilities: CapabilityStatus
    models: ModelCapabilityStatus
    storage: StorageStatus
    error_message: str | None = None


class ModelPathStatus(BaseModel):
    name: str
    display_name: str | None = None
    path: str | None = None
    path_exists: bool
    ready: bool
    loaded: bool | None = None
    model_stage: str | None = None
    is_smoke: bool | None = None
    current_target_type: str | None = None
    category_type: str | None = None
    formal_metric_available: bool | None = None
    class_codes: list[str] = []
    source_types: list[str] = []
    route_condition: str | None = None
    warning: str | None = None
    usage_scope: str | None = None
    capability_level: str | None = None
    dataset_actual_images: int | None = None
    dataset_target_name: str | None = None
    is_true_multichannel_model: bool | None = None
    dataset_images: int | None = None
    dataset_bbox: int | None = None
    healthy_excluded: bool | None = None
    class_mapping_strategy: str | None = None


class ModelsCatalog(BaseModel):
    phone_model: ModelPathStatus
    phone_experimental_model: ModelPathStatus
    uav_crop_model: ModelPathStatus
    uav_blb_model: ModelPathStatus
    uav_blb_experimental_model: ModelPathStatus
    mock_model: ModelPathStatus


class DemoSafetyStatus(BaseModel):
    demo_safe: bool
    has_smoke_models: bool
    has_formal_models: bool
    formal_metric_available: bool
    warnings: list[str]
    display_rules: list[str]


class ModelsStatusResponse(BaseModel):
    detector_mode: str
    active_model_name: str
    active_model_version: str
    uav_model: ModelPathStatus
    uav_crop_model: ModelPathStatus
    uav_blb_model: ModelPathStatus
    uav_blb_experimental_model: ModelPathStatus
    phone_model: ModelPathStatus
    phone_experimental_model: ModelPathStatus
    mock_model: ModelPathStatus
    models: ModelsCatalog
    active_routing: dict[str, str]
    fallback_to_mock: bool
    demo_safety: DemoSafetyStatus
