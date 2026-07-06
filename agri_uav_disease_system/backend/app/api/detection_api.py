from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.schemas.detection_result import DetectionResult
from app.schemas.upload import DetectImageMetadata
from app.services.detection_service import detection_service
from app.services.uav_blb_segmentation_v1_release_service import (
    UavBlbSegmentationV1ReleaseError,
    uav_blb_segmentation_v1_release_service,
)

router = APIRouter(prefix="/api/detect", tags=["detection"])


@router.post("/image", response_model=DetectionResult)
async def detect_image(
    file: UploadFile = File(...),
    field_id: str | None = Form(default=None),
    plot_id: str | None = Form(default=None),
    plot_name: str | None = Form(default=None),
    region_name: str | None = Form(default=None),
    lng: float | None = Form(default=None),
    lat: float | None = Form(default=None),
    source: str | None = Form(default=None),
    source_type: str | None = Form(default=None),
    model_hint: str | None = Form(default=None),
    target_type: str | None = Form(default=None),
    model_stage_hint: str | None = Form(default=None),
    uav_task_id: str | None = Form(default=None),
    abnormal_region_id: str | None = Form(default=None),
) -> DetectionResult:
    metadata = DetectImageMetadata(
        field_id=field_id,
        plot_id=plot_id,
        plot_name=plot_name,
        region_name=region_name,
        lng=lng,
        lat=lat,
        source=source,
        source_type=source_type or source or settings.default_source_type,
        model_hint=model_hint,
        target_type=target_type,
        model_stage_hint=model_stage_hint,
        uav_task_id=uav_task_id,
        abnormal_region_id=abnormal_region_id,
    )
    return await detection_service.detect_upload(file, metadata)


@router.post("/uav-blb-segmentation", response_model=DetectionResult)
async def detect_uav_blb_segmentation_v1(
    file: UploadFile = File(...),
    field_id: str | None = Form(default=None),
    plot_id: str | None = Form(default=None),
    plot_name: str | None = Form(default=None),
    region_name: str | None = Form(default=None),
    lng: float | None = Form(default=None),
    lat: float | None = Form(default=None),
    human_review_status: str = Form(default="pending"),
    human_review_label: str | None = Form(default=None),
    issue_tags: str | None = Form(default=None),
    reviewer_note: str | None = Form(default=None),
) -> DetectionResult | JSONResponse:
    try:
        return await uav_blb_segmentation_v1_release_service.detect_upload(
            file=file,
            field_id=field_id,
            plot_id=plot_id,
            plot_name=plot_name,
            region_name=region_name,
            lng=lng,
            lat=lat,
            human_review_status=human_review_status,
            human_review_label=human_review_label,
            issue_tags=issue_tags,
            reviewer_note=reviewer_note,
        )
    except UavBlbSegmentationV1ReleaseError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)
