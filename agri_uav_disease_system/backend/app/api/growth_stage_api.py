from __future__ import annotations

from fastapi import APIRouter

from app.schemas.growth_stage import GrowthStage, GrowthStageCreate, GrowthStageListResponse
from app.services.growth.growth_stage_service import growth_stage_service

router = APIRouter(prefix="/api/growth-stages", tags=["growth-stages"])


@router.post("", response_model=GrowthStage)
async def create_growth_stage(request: GrowthStageCreate) -> GrowthStage:
    return growth_stage_service.create(request)


@router.get("/plots/{plot_id}", response_model=GrowthStageListResponse)
async def list_growth_stages(plot_id: str) -> GrowthStageListResponse:
    items = growth_stage_service.list_by_plot(plot_id)
    return GrowthStageListResponse(items=items, total=len(items))
