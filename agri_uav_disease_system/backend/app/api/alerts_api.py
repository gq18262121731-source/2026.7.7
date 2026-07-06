from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.constants import ERROR_ALERT_NOT_FOUND
from app.core.exceptions import AppException
from app.schemas.alert import AlertActionListResponse, AlertDetail, AlertPageResponse, AlertResolveRequest
from app.services.alert_service import alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=AlertPageResponse)
async def list_alerts(
    status: str | None = None,
    risk_level: str | None = None,
    plot_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> AlertPageResponse:
    items, total = alert_service.list_alerts(status=status, risk_level=risk_level, plot_id=plot_id, page=page, page_size=page_size)
    return AlertPageResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{alert_id}", response_model=AlertDetail)
async def get_alert(alert_id: str) -> AlertDetail:
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise AppException(ERROR_ALERT_NOT_FOUND, "\u9884\u8b66\u4e0d\u5b58\u5728", {"alert_id": alert_id})
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertDetail)
async def resolve_alert(alert_id: str, request: AlertResolveRequest | None = None) -> AlertDetail:
    request = request or AlertResolveRequest()
    alert = alert_service.resolve(
        alert_id,
        operator_id=request.operator_id,
        operator_name=request.operator_name,
        note=request.note,
    )
    if not alert:
        raise AppException(ERROR_ALERT_NOT_FOUND, "\u9884\u8b66\u4e0d\u5b58\u5728", {"alert_id": alert_id})
    return alert


@router.get("/{alert_id}/actions", response_model=AlertActionListResponse)
async def alert_actions(alert_id: str) -> AlertActionListResponse:
    actions = alert_service.list_actions(alert_id)
    if actions is None:
        raise AppException(ERROR_ALERT_NOT_FOUND, "\u9884\u8b66\u4e0d\u5b58\u5728", {"alert_id": alert_id})
    return AlertActionListResponse(items=actions, total=len(actions))
