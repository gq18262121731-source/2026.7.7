from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DiseaseListItem(BaseModel):
    disease_id: str
    zh_name: str
    en_name: str
    authority_level: str
    model_supported: bool


class DiseaseListResponse(BaseModel):
    items: list[DiseaseListItem]
    count: int


class DiseaseDetail(BaseModel):
    disease_id: str
    zh_name: str
    en_name: str
    aliases: list[str]
    pathogen_type: str
    pathogen_name: str
    affected_crop: list[str]
    affected_parts: list[str]
    typical_symptoms: list[str]
    early_symptoms: list[str]
    late_symptoms: list[str]
    similar_diseases: list[str]
    favorable_conditions: list[str]
    transmission: list[str]
    risk_notes: list[str]
    management_suggestions: list[str]
    model_class_mapping: list[str]
    evidence_sources: list[str]
    authority_level: str
    last_updated: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(default="", max_length=500)
    disease_id: str | None = Field(default=None, max_length=80)
    section_type: str | None = Field(default=None, max_length=80)
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    chunk_id: str
    score: float
    text: str
    source_id: str
    source_title: str
    source_type: str
    authority_level: str
    disease_id: str
    section_type: str


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: list[KnowledgeSearchResult]


class KGSummaryResponse(BaseModel):
    disease_id: str
    symptoms: list[str]
    conditions: list[str]
    transmission: list[str]
    management: list[str]
    confused_with: list[str]
    evidence_sources: list[dict[str, Any]]
