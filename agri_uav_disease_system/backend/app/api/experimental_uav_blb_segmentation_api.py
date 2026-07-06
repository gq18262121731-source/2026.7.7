from __future__ import annotations

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse, Response

from app.schemas.experimental_uav_blb_segmentation import (
    UavBlbSegmentationDryRunResponse,
    UavBlbSegmentationFieldTrialRecordsResponse,
    UavBlbSegmentationFieldTrialResponse,
)
from app.services.experimental.uav_blb_segmentation_dry_run_service import (
    DryRunError,
    uav_blb_segmentation_dry_run_service,
)


router = APIRouter(prefix="/api/experimental/uav-blb-segmentation", tags=["experimental-uav-blb-segmentation"])


@router.post("/dry-run", response_model=UavBlbSegmentationDryRunResponse)
async def uav_blb_segmentation_dry_run(
    file: UploadFile = File(...),
    mode: str = Form(...),
    return_probability_map: bool = Form(default=True),
    return_overlay: bool = Form(default=True),
) -> UavBlbSegmentationDryRunResponse | JSONResponse:
    try:
        return await uav_blb_segmentation_dry_run_service.dry_run_upload(
            file=file,
            mode=mode,
            return_probability_map=return_probability_map,
            return_overlay=return_overlay,
        )
    except DryRunError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.post("/field-trial", response_model=UavBlbSegmentationFieldTrialResponse)
async def uav_blb_segmentation_field_trial(
    file: UploadFile = File(...),
    mode: str = Form(...),
    plot_id: str | None = Form(default=None),
    plot_name: str | None = Form(default=None),
    operator_note: str | None = Form(default=None),
    human_review_status: str = Form(default="pending"),
    human_review_label: str | None = Form(default=None),
    issue_tags: str | None = Form(default=None),
    return_probability_map: bool = Form(default=True),
    return_overlay: bool = Form(default=True),
) -> UavBlbSegmentationFieldTrialResponse | JSONResponse:
    try:
        return await uav_blb_segmentation_dry_run_service.field_trial_upload(
            file=file,
            mode=mode,
            plot_id=plot_id,
            plot_name=plot_name,
            operator_note=operator_note,
            human_review_status=human_review_status,
            human_review_label=human_review_label,
            issue_tags=issue_tags,
            return_probability_map=return_probability_map,
            return_overlay=return_overlay,
        )
    except DryRunError as exc:
        return JSONResponse(status_code=exc.status_code, content=exc.payload)


@router.get("/field-trial/records", response_model=UavBlbSegmentationFieldTrialRecordsResponse)
async def uav_blb_segmentation_field_trial_records(
    limit: int = Query(default=100, ge=1, le=1000),
) -> UavBlbSegmentationFieldTrialRecordsResponse:
    records = uav_blb_segmentation_dry_run_service.list_field_trial_records(limit=limit)
    return UavBlbSegmentationFieldTrialRecordsResponse(records=records, total=len(records))


@router.get("/field-trial/export.csv")
async def uav_blb_segmentation_field_trial_export_csv() -> Response:
    csv_text = uav_blb_segmentation_dry_run_service.export_field_trial_records_csv()
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="field_trial_records.csv"'},
    )


@router.get("/field-trial/export.json")
async def uav_blb_segmentation_field_trial_export_json() -> JSONResponse:
    return JSONResponse(content=uav_blb_segmentation_dry_run_service.export_field_trial_records_json())
