from __future__ import annotations

from fastapi import APIRouter

from app.schemas.alert import AlertListResponse
from app.schemas.detection_result import Suggestion
from app.schemas.mobile import MobileOverview, MobilePlotDetail, MobilePlotListResponse, MobileRecordDetail
from app.services.mobile.mobile_service import mobile_service

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


@router.get("/overview", response_model=MobileOverview)
async def mobile_overview(user_id: str | None = None) -> MobileOverview:
    return mobile_service.overview(user_id=user_id)


@router.get("/plots", response_model=MobilePlotListResponse)
async def mobile_plots(
    risk_level: str | None = None,
    region_name: str | None = None,
    keyword: str | None = None,
    user_id: str | None = None,
) -> MobilePlotListResponse:
    return mobile_service.plots(risk_level=risk_level, region_name=region_name, keyword=keyword, user_id=user_id)


@router.get("/plots/{plot_id}", response_model=MobilePlotDetail)
async def mobile_plot_detail(plot_id: str) -> MobilePlotDetail:
    return mobile_service.plot_detail(plot_id)


@router.get("/records/{record_id}", response_model=MobileRecordDetail)
async def mobile_record_detail(record_id: str) -> MobileRecordDetail:
    return mobile_service.record_detail(record_id)


@router.get("/alerts", response_model=AlertListResponse)
async def mobile_alerts() -> AlertListResponse:
    return mobile_service.alerts()


@router.get("/suggestions/{record_id}", response_model=Suggestion)
async def mobile_suggestion(record_id: str) -> Suggestion:
    return mobile_service.suggestion(record_id)
