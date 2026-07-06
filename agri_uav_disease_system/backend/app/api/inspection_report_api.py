from __future__ import annotations

from fastapi import APIRouter

from app.schemas.inspection_report import (
    InspectionReport,
    InspectionReportGenerateRequest,
    InspectionReportListResponse,
)
from app.services.inspection_report_service import inspection_report_service

router = APIRouter(prefix="/api/inspection-reports", tags=["inspection-reports"])


@router.post("/generate", response_model=InspectionReport)
async def generate_report(request: InspectionReportGenerateRequest) -> InspectionReport:
    return await inspection_report_service.generate(request)


@router.get("", response_model=InspectionReportListResponse)
async def list_reports(field_id: str | None = None) -> InspectionReportListResponse:
    return inspection_report_service.list_reports(field_id=field_id)


@router.get("/{report_id}", response_model=InspectionReport)
async def get_report(report_id: str) -> InspectionReport:
    return inspection_report_service.get(report_id)
