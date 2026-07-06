from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.knowledge_schema import (
    DiseaseDetail,
    DiseaseListItem,
    DiseaseListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
)
from app.services.knowledge_service import KnowledgeNotFoundError, knowledge_service
from app.services.rag_service import KnowledgeDataError

router = APIRouter(prefix="/api/knowledge", tags=["experimental-knowledge"])


@router.get("/diseases", response_model=DiseaseListResponse)
async def list_diseases() -> DiseaseListResponse:
    items = [DiseaseListItem(**item) for item in knowledge_service.list_diseases()]
    return DiseaseListResponse(items=items, count=len(items))


@router.get("/diseases/{disease_id}", response_model=DiseaseDetail)
async def get_disease(disease_id: str) -> DiseaseDetail:
    try:
        return DiseaseDetail(**knowledge_service.get_disease(disease_id))
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "DISEASE_NOT_FOUND", "message": str(exc)}) from exc
    except KnowledgeDataError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "KNOWLEDGE_DATA_ERROR", "message": str(exc)}) from exc


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(payload: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    try:
        results = knowledge_service.search_knowledge(
            query=payload.query,
            disease_id=payload.disease_id,
            section_type=payload.section_type,
            top_k=payload.top_k,
        )
    except KnowledgeNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "DISEASE_NOT_FOUND", "message": str(exc)}) from exc
    except KnowledgeDataError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "KNOWLEDGE_DATA_ERROR", "message": str(exc)}) from exc
    return KnowledgeSearchResponse(
        query=payload.query,
        results=[KnowledgeSearchResult(**item) for item in results],
    )
