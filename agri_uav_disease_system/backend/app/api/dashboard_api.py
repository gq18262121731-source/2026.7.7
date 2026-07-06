from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.dashboard import (
    DashboardSummary,
    DiseaseStatisticsResponse,
    HeatmapResponse,
    LatestAlertsResponse,
    LatestRecordsResponse,
    PlotDetailResponse,
    PlotStatisticsResponse,
)
from app.core.constants import ERROR_RECORD_NOT_FOUND
from app.core.exceptions import AppException
from app.schemas.record import RecordListResponse
from app.services.storage.result_store import result_store
from app.services.dashboard.dashboard_service import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary() -> DashboardSummary:
    return dashboard_service.summary()


@router.get("/plots", response_model=PlotStatisticsResponse)
async def dashboard_plots(
    region_name: str | None = None,
    risk_level: str | None = None,
    disease: str | None = None,
) -> PlotStatisticsResponse:
    return dashboard_service.plot_statistics(region_name=region_name, risk_level=risk_level, disease=disease)


@router.get("/plots/{plot_id}", response_model=PlotDetailResponse)
async def dashboard_plot_detail(plot_id: str) -> PlotDetailResponse:
    detail = dashboard_service.plot_detail(plot_id)
    if not detail:
        raise AppException(ERROR_RECORD_NOT_FOUND, "\u5730\u5757\u8bb0\u5f55\u4e0d\u5b58\u5728", {"plot_id": plot_id})
    return detail


@router.get("/plots/{plot_id}/records", response_model=RecordListResponse)
async def dashboard_plot_records(
    plot_id: str,
    risk_level: str | None = None,
    severity: str | None = None,
    disease: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> RecordListResponse:
    records = result_store.list_records(
        plot_id=plot_id,
        risk_level=risk_level,
        severity=severity,
        disease=disease,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )
    total = result_store.count_records(
        plot_id=plot_id,
        risk_level=risk_level,
        severity=severity,
        disease=disease,
        start_time=start_time,
        end_time=end_time,
    )
    return RecordListResponse(items=records, total=total, page=page, page_size=page_size)


@router.get("/heatmap", response_model=HeatmapResponse)
async def dashboard_heatmap(
    region_name: str | None = None,
    disease: str | None = None,
    risk_level: str | None = None,
) -> HeatmapResponse:
    return dashboard_service.heatmap(region_name=region_name, disease=disease, risk_level=risk_level)


@router.get("/disease-statistics", response_model=DiseaseStatisticsResponse)
async def dashboard_disease_statistics() -> DiseaseStatisticsResponse:
    return dashboard_service.disease_statistics()


@router.get("/latest-records", response_model=LatestRecordsResponse)
async def dashboard_latest_records(limit: int = Query(default=10, ge=1, le=50)) -> LatestRecordsResponse:
    return dashboard_service.latest_records(limit=limit)


@router.get("/latest-alerts", response_model=LatestAlertsResponse)
async def dashboard_latest_alerts(limit: int = Query(default=10, ge=1, le=50)) -> LatestAlertsResponse:
    return dashboard_service.latest_alerts(limit=limit)
