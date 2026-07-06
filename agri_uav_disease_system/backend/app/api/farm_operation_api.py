from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.farm_operation import FarmOperation, FarmOperationCreate, FarmOperationListResponse
from app.services.farm_operation.farm_operation_service import farm_operation_service

router = APIRouter(prefix="/api/farm-operations", tags=["farm-operations"])


@router.post("", response_model=FarmOperation)
async def create_farm_operation(request: FarmOperationCreate) -> FarmOperation:
    return farm_operation_service.create(request)


@router.get("", response_model=FarmOperationListResponse)
async def list_farm_operations(
    plot_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> FarmOperationListResponse:
    items = farm_operation_service.list_operations(plot_id=plot_id, limit=limit)
    return FarmOperationListResponse(items=items, total=len(items))


@router.get("/plots/{plot_id}", response_model=FarmOperationListResponse)
async def list_plot_farm_operations(
    plot_id: str,
    limit: int = Query(default=100, ge=1, le=500),
) -> FarmOperationListResponse:
    items = farm_operation_service.list_operations(plot_id=plot_id, limit=limit)
    return FarmOperationListResponse(items=items, total=len(items))
