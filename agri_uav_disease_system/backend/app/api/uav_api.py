from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.core.config import settings
from app.schemas.detection_result import DetectionResult
from app.schemas.upload import DetectImageMetadata
from app.schemas.uav import (
    AbnormalRegion,
    AbnormalRegionListResponse,
    UavDryRunRequest,
    UavDryRunResponse,
    UavIndexListResponse,
    UavTask,
    UavTaskCreate,
    UavTaskListResponse,
)
from app.schemas.risk_fusion import UavIndexAnalysisResponse
from app.services.uav_index_analyzer import uav_index_analyzer
from app.services.uav_service import uav_service

router = APIRouter(prefix="/api/uav", tags=["uav"])


@router.post("/tasks", response_model=UavTask)
async def create_uav_task(request: UavTaskCreate) -> UavTask:
    return uav_service.create_task(request)


@router.get("/tasks", response_model=UavTaskListResponse)
async def list_uav_tasks(
    field_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> UavTaskListResponse:
    return uav_service.list_tasks(field_id=field_id, page=page, page_size=page_size)


@router.get("/tasks/{uav_task_id}", response_model=UavTask)
async def get_uav_task(uav_task_id: str) -> UavTask:
    return uav_service.get_task(uav_task_id)


@router.post("/tasks/{uav_task_id}/dry-run", response_model=UavDryRunResponse)
async def uav_dry_run(uav_task_id: str, request: UavDryRunRequest) -> UavDryRunResponse:
    return uav_service.dry_run(uav_task_id, request)


@router.get("/tasks/{uav_task_id}/indices", response_model=UavIndexListResponse)
async def uav_indices(uav_task_id: str) -> UavIndexListResponse:
    return uav_service.list_indices(uav_task_id)


@router.post("/tasks/{uav_task_id}/analyze-indices", response_model=UavIndexAnalysisResponse)
async def analyze_uav_indices(uav_task_id: str) -> UavIndexAnalysisResponse:
    return uav_index_analyzer.analyze_uav_indices(uav_task_id)


@router.get("/tasks/{uav_task_id}/index-analysis", response_model=UavIndexAnalysisResponse)
async def get_uav_index_analysis(uav_task_id: str) -> UavIndexAnalysisResponse:
    return uav_index_analyzer.get_index_analysis(uav_task_id)


@router.get("/tasks/{uav_task_id}/abnormal-regions", response_model=AbnormalRegionListResponse)
async def uav_abnormal_regions(uav_task_id: str) -> AbnormalRegionListResponse:
    return uav_service.list_regions(uav_task_id=uav_task_id)


@router.get("/abnormal-regions/{region_id}", response_model=AbnormalRegion)
async def abnormal_region_detail(region_id: str) -> AbnormalRegion:
    return uav_service.get_region(region_id)


@router.post("/abnormal-regions/{region_id}/phone-followup", response_model=DetectionResult)
async def phone_followup(
    region_id: str,
    file: UploadFile = File(...),
    field_id: str | None = Form(default=None),
    plot_id: str | None = Form(default=None),
    plot_name: str | None = Form(default=None),
    region_name: str | None = Form(default=None),
    lng: float | None = Form(default=None),
    lat: float | None = Form(default=None),
    source_type: str | None = Form(default="phone_followup"),
    model_hint: str | None = Form(default=None),
    target_type: str | None = Form(default="disease"),
    model_stage_hint: str | None = Form(default=None),
) -> DetectionResult:
    metadata = DetectImageMetadata(
        field_id=field_id,
        plot_id=plot_id,
        plot_name=plot_name,
        region_name=region_name,
        lng=lng,
        lat=lat,
        source_type=source_type or settings.default_source_type,
        model_hint=model_hint,
        target_type=target_type,
        model_stage_hint=model_stage_hint,
        abnormal_region_id=region_id,
    )
    return await uav_service.phone_followup(region_id, file, metadata)
