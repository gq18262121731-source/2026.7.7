from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DiagnosisReportRequest(BaseModel):
    record_id: str | None = None
    disease_id: str | None = Field(default=None, max_length=80)
    model_class: str | None = Field(default=None, max_length=120)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_type: str | None = Field(default=None, max_length=80)
    user_question: str | None = Field(default=None, max_length=500)
    field_id: str | None = Field(default=None, max_length=120)
    plot_id: str | None = Field(default=None, max_length=120)
    uav_task_id: str | None = Field(default=None, max_length=120)
    abnormal_region_id: str | None = Field(default=None, max_length=120)
    risk_level: str | None = Field(default=None, max_length=40)
    severity: str | None = Field(default=None, max_length=80)


class KnowledgeContextRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    record_id: str | None = Field(default=None, max_length=120)
    disease_id: str | None = Field(default=None, max_length=80)
    model_class: str | None = Field(default=None, max_length=120)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_type: str | None = Field(default=None, max_length=80)
    top_k: int = Field(default=5, ge=1, le=20)
    include_knowledge_chunks: bool = True
    include_graph: bool = True
    include_relations: bool = True


class KnowledgeContextDisease(BaseModel):
    disease_id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class KnowledgeContextChunk(BaseModel):
    chunk_id: str
    title: str
    section_type: str
    content: str
    source: str
    score: float
    disease_id: str
    authority_level: str


class KnowledgeContextEntity(BaseModel):
    entity_id: str
    entity_type: str
    name: str


class KnowledgeContextRelation(BaseModel):
    source: str
    relation: str
    target: str


class KnowledgeContextGraph(BaseModel):
    entities: list[KnowledgeContextEntity] = Field(default_factory=list)
    relations: list[KnowledgeContextRelation] = Field(default_factory=list)
    triples: list[list[str]] = Field(default_factory=list)


class KnowledgeContextResponse(BaseModel):
    success: bool = True
    mode: str = "knowledge_context"
    question: str
    matched_disease: KnowledgeContextDisease | None = None
    knowledge_chunks: list[KnowledgeContextChunk] = Field(default_factory=list)
    graph: KnowledgeContextGraph = Field(default_factory=KnowledgeContextGraph)
    context_summary: str
    safety_notice: str
    insufficient_evidence: bool = False
    missing_context: list[str] = Field(default_factory=list)


class SuspectedDisease(BaseModel):
    disease_id: str
    zh_name: str
    en_name: str


class EvidenceSource(BaseModel):
    source_id: str
    source_title: str
    source_type: str
    authority_level: str
    url_or_reference: str
    language: str
    notes: str | None = None


class DiagnosisReportResponse(BaseModel):
    mode: str = "diagnosis_report"
    question: str | None = None
    answer: str | None = None
    basis: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    safety_notice: str | None = None
    used_context: dict[str, Any] = Field(default_factory=dict)
    retrieved_knowledge: list[dict[str, Any]] = Field(default_factory=list)
    llm_status: dict[str, Any] = Field(default_factory=dict)
    suspected_disease: SuspectedDisease | dict[str, Any]
    model_result_summary: str
    knowledge_summary: str
    risk_level: Literal["low", "medium", "high", "unknown"]
    manual_check_questions: list[str]
    management_suggestions: list[str]
    uncertainty_notes: list[str]
    evidence_sources: list[EvidenceSource]
    insufficient_evidence: bool = False
    llm_mode: str = "mock"
    llm_provider: str = ""
    llm_model: str = ""
    prompt_version: str = "kg_rag_agent_prompt_v1"
    fallback_used: bool = False
    fallback_level: str = "none"
    api_error_type: str | None = None
    repair_attempted: bool = False
    schema_valid: bool = True
    safety_passed: bool = True


class LLMReportSchema(DiagnosisReportResponse):
    pass


class LLMStatusResponse(BaseModel):
    llm_mode: str
    llm_provider: str
    llm_model: str
    json_response_format_enabled: bool
    mock_fallback_enabled: bool
    api_key_configured: bool
    prompt_version: str
