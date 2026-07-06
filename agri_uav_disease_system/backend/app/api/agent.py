from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.agent_schema import (
    DiagnosisReportRequest,
    DiagnosisReportResponse,
    KnowledgeContextRequest,
    KnowledgeContextResponse,
    LLMStatusResponse,
)
from app.services.agent_service import agent_service
from app.services.llm_client import LLMClientError, get_llm_status
from app.services.rag_service import KnowledgeDataError

router = APIRouter(prefix="/api/agent", tags=["experimental-agent"])


@router.post("/knowledge-context", response_model=KnowledgeContextResponse)
async def knowledge_context(payload: KnowledgeContextRequest) -> KnowledgeContextResponse:
    try:
        context = agent_service.build_knowledge_context(
            question=payload.question,
            record_id=payload.record_id,
            disease_id=payload.disease_id,
            model_class=payload.model_class,
            confidence=payload.confidence,
            source_type=payload.source_type,
            top_k=payload.top_k,
            include_knowledge_chunks=payload.include_knowledge_chunks,
            include_graph=payload.include_graph,
            include_relations=payload.include_relations,
        )
    except KnowledgeDataError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "KNOWLEDGE_DATA_ERROR", "message": str(exc)}) from exc
    return KnowledgeContextResponse(**context)


@router.post("/diagnosis-report", response_model=DiagnosisReportResponse)
async def diagnosis_report(payload: DiagnosisReportRequest) -> DiagnosisReportResponse:
    try:
        report = agent_service.generate_diagnosis_report(
            record_id=payload.record_id,
            disease_id=payload.disease_id,
            model_class=payload.model_class,
            confidence=payload.confidence,
            source_type=payload.source_type,
            field_id=payload.field_id,
            plot_id=payload.plot_id,
            uav_task_id=payload.uav_task_id,
            abnormal_region_id=payload.abnormal_region_id,
            risk_level=payload.risk_level,
            severity=payload.severity,
            user_question=payload.user_question,
        )
    except KnowledgeDataError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "KNOWLEDGE_DATA_ERROR", "message": str(exc)}) from exc
    except LLMClientError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error_code": "LLM_API_ERROR", "error_type": exc.error_type, "message": str(exc)},
        ) from exc
    return DiagnosisReportResponse(**report)


@router.get("/llm-status", response_model=LLMStatusResponse)
async def llm_status() -> LLMStatusResponse:
    return LLMStatusResponse(**get_llm_status())
