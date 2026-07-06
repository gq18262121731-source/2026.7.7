from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.prediction import (
    MobilePredictionListResponse,
    PredictionRiskMapResponse,
    PredictionSummaryResponse,
    RiskPredictionResponse,
)
from app.services.prediction.prediction_service import prediction_service

router = APIRouter(tags=["prediction"])


@router.get("/api/prediction/plots/{plot_id}", response_model=RiskPredictionResponse)
async def predict_plot(
    plot_id: str,
    window_days: int = Query(default=7),
    disease: str | None = None,
    save: bool = True,
    create_alert: bool = True,
) -> RiskPredictionResponse:
    return await prediction_service.predict_plot(
        plot_id=plot_id,
        window_days=window_days,
        disease=disease,
        save=save,
        create_alert=create_alert,
    )


@router.get("/api/prediction/dashboard/summary", response_model=PredictionSummaryResponse)
async def prediction_summary() -> PredictionSummaryResponse:
    return prediction_service.summary()


@router.get("/api/prediction/risk-map", response_model=PredictionRiskMapResponse)
async def prediction_risk_map() -> PredictionRiskMapResponse:
    return prediction_service.risk_map()


@router.get("/api/mobile/predictions", response_model=MobilePredictionListResponse)
async def mobile_predictions(limit: int = Query(default=50, ge=1, le=200)) -> MobilePredictionListResponse:
    items = prediction_service.mobile_predictions(limit=limit)
    return MobilePredictionListResponse(items=items, total=len(items))


@router.get("/api/mobile/plots/{plot_id}/prediction", response_model=RiskPredictionResponse)
async def mobile_plot_prediction(plot_id: str) -> RiskPredictionResponse:
    latest = prediction_service.latest_for_plot(plot_id)
    if latest:
        return latest
    return await prediction_service.predict_plot(plot_id=plot_id, window_days=7, save=True, create_alert=False)
