from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas.farm_analysis_report import (
    FarmAnalysisReportHistoryItem,
    FarmAnalysisReportHistoryResponse,
    FarmAnalysisReportRequest,
    FarmAnalysisReportResponse,
)
from app.services.farm_analysis_report_service import farm_analysis_report_service
from app.services.report_storage_service import report_storage_service

router = APIRouter(prefix="/api", tags=["farm-analysis-reports"])


@router.post("/agent/farm-analysis-report", response_model=FarmAnalysisReportResponse)
async def farm_analysis_report(payload: FarmAnalysisReportRequest) -> FarmAnalysisReportResponse:
    return farm_analysis_report_service.generate_report(payload)


@router.get("/reports", response_model=FarmAnalysisReportHistoryResponse)
async def report_history(plot_id: str | None = None) -> FarmAnalysisReportHistoryResponse:
    items = [
        FarmAnalysisReportHistoryItem(
            report_id=item.report_id,
            plot_id=item.plot_id,
            record_id=item.record_id,
            report_type=item.report_type,
            crop=item.crop,
            summary=item.summary,
            pdf_url=item.pdf_url,
            preview_url=item.preview_url,
            fallback_used=item.fallback_used,
            weather_available=item.weather_available,
            rag_available=item.rag_available,
            pdf_fallback_used=item.pdf_fallback_used,
            created_at=item.created_at,
        )
        for item in report_storage_service.list(plot_id=plot_id)
    ]
    return FarmAnalysisReportHistoryResponse(items=items, total=len(items))


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str) -> FileResponse:
    return _report_file(report_id, "attachment")


@router.get("/reports/{report_id}/preview")
async def preview_report(report_id: str) -> FileResponse:
    return _report_file(report_id, "inline")


def _report_file(report_id: str, disposition: str) -> FileResponse:
    pdf_path = report_storage_service.pdf_path(report_id)
    if not pdf_path:
        raise HTTPException(status_code=404, detail={"error_code": "REPORT_NOT_FOUND", "message": report_id})
    path = Path(pdf_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error_code": "REPORT_FILE_NOT_FOUND", "message": report_id})
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{report_id}.pdf",
        content_disposition_type=disposition,
    )
