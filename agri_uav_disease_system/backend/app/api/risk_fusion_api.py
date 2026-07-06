from __future__ import annotations

from fastapi import APIRouter

from app.schemas.risk_fusion import RiskFusionEvaluateRequest, RiskFusionListResponse, RiskFusionResponse
from app.services.risk_fusion_scorer import risk_fusion_scorer

router = APIRouter(prefix="/api/risk/fusion", tags=["risk-fusion"])


@router.post("/evaluate", response_model=RiskFusionResponse)
async def evaluate_risk_fusion(request: RiskFusionEvaluateRequest) -> RiskFusionResponse:
    return risk_fusion_scorer.evaluate(request)


@router.get("/field/{field_id}", response_model=RiskFusionListResponse)
async def field_risk_fusion_history(field_id: str) -> RiskFusionListResponse:
    items = risk_fusion_scorer.list_for_field(field_id)
    return RiskFusionListResponse(items=items, total=len(items))


@router.get("/{prediction_id}", response_model=RiskFusionResponse)
async def get_risk_fusion(prediction_id: str) -> RiskFusionResponse:
    return risk_fusion_scorer.get(prediction_id)
