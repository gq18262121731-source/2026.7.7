from __future__ import annotations

from pydantic import BaseModel


class FarmOperationCreate(BaseModel):
    plot_id: str
    operation_type: str
    operation_time: str
    target_disease: str | None = None
    material_name: str | None = None
    dosage_text: str | None = None
    operator_id: str | None = None
    operator_name: str | None = None
    note: str | None = None
    photo_url: str | None = None


class FarmOperation(FarmOperationCreate):
    operation_id: str
    created_at: str


class FarmOperationListResponse(BaseModel):
    items: list[FarmOperation]
    total: int
