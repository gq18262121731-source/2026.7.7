from __future__ import annotations

from pydantic import BaseModel


class GrowthStageCreate(BaseModel):
    plot_id: str
    rice_variety: str | None = None
    sowing_date: str | None = None
    transplanting_date: str | None = None
    growth_stage: str | None = None
    manual_growth_stage: str | None = None
    inferred_growth_stage: str | None = None


class GrowthStage(GrowthStageCreate):
    growth_id: str
    updated_at: str
    created_at: str


class GrowthStageListResponse(BaseModel):
    items: list[GrowthStage]
    total: int
