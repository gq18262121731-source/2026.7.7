from __future__ import annotations

from pydantic import BaseModel, Field


class UavBlbSegmentationDryRunResponse(BaseModel):
    success: bool = True
    mode: str = "dry_run_only"
    production_ready: bool = False
    backend_integration_allowed: str = "dry_run_only"
    model_stage: str = "formal_candidate"
    model_name: str
    input_config: str = "D2_5BAND_NDVI"
    weight_sha256: str
    patch_size: int = 256
    stride: int = 128
    threshold: float = 0.45
    min_area: int = 128
    disease_area_ratio: float
    mask_url: str
    overlay_url: str
    probability_map_url: str
    warning: str = "experimental_dry_run_only_not_for_production"
    original_preview_url: str | None = None


class UavBlbSegmentationFieldTrialRecord(BaseModel):
    trial_id: str
    plot_id: str | None = None
    plot_name: str | None = None
    tif_filename: str
    input_config: str = "D2_5BAND_NDVI"
    model_name: str
    model_sha256: str
    threshold: float = 0.45
    min_area: int = 128
    disease_area_ratio: float
    mask_url: str
    overlay_url: str
    probability_map_url: str
    original_preview_url: str | None = None
    inference_time_ms: int
    mode: str = "field_trial_only"
    model_stage: str = "formal_candidate"
    production_ready: bool = False
    warning: str = "field_trial_not_for_production"
    created_at: str
    operator_note: str | None = None
    human_review_status: str = "pending"
    human_review_label: str | None = None
    issue_tags: list[str] = Field(default_factory=list)


class UavBlbSegmentationFieldTrialResponse(BaseModel):
    success: bool = True
    mode: str = "field_trial_only"
    production_ready: bool = False
    backend_integration_allowed: str = "field_trial_only"
    model_stage: str = "formal_candidate"
    model_name: str
    input_config: str = "D2_5BAND_NDVI"
    weight_sha256: str
    patch_size: int = 256
    stride: int = 128
    threshold: float = 0.45
    min_area: int = 128
    disease_area_ratio: float
    mask_url: str
    overlay_url: str
    probability_map_url: str
    original_preview_url: str | None = None
    warning: str = "field_trial_not_for_production"
    trial_record: UavBlbSegmentationFieldTrialRecord


class UavBlbSegmentationFieldTrialRecordsResponse(BaseModel):
    success: bool = True
    mode: str = "field_trial_only"
    production_ready: bool = False
    backend_integration_allowed: str = "field_trial_only"
    records: list[UavBlbSegmentationFieldTrialRecord]
    total: int
