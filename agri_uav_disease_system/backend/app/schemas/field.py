from __future__ import annotations

from pydantic import BaseModel


class FieldBase(BaseModel):
    field_name: str
    location_city: str = "宿迁市"
    location_district: str | None = None
    location_town: str | None = None
    location_village: str | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    area_estimate_mu: float | None = None
    crop_type: str = "rice"
    current_growth_stage: str | None = None
    field_status: str = "active"
    notes: str | None = None


class FieldCreate(FieldBase):
    field_id: str


class FieldUpdate(BaseModel):
    field_name: str | None = None
    location_city: str | None = None
    location_district: str | None = None
    location_town: str | None = None
    location_village: str | None = None
    center_lat: float | None = None
    center_lng: float | None = None
    area_estimate_mu: float | None = None
    crop_type: str | None = None
    current_growth_stage: str | None = None
    field_status: str | None = None
    notes: str | None = None


class FieldInfo(FieldBase):
    field_id: str
    created_at: str
    updated_at: str


class FieldListResponse(BaseModel):
    items: list[FieldInfo]
    total: int
    page: int
    page_size: int
