from __future__ import annotations

import os
from pathlib import Path

from app.core.config import settings


KNOWLEDGE_ROOT: Path = Path(os.getenv("KNOWLEDGE_ROOT", str(settings.backend_dir / "knowledge")))
DISEASES_DIR: Path = KNOWLEDGE_ROOT / "diseases"
KG_ENTITIES_PATH: Path = KNOWLEDGE_ROOT / "graph" / "kg_entities.json"
KG_RELATIONS_PATH: Path = KNOWLEDGE_ROOT / "graph" / "kg_relations.json"
KG_TRIPLES_PATH: Path = KNOWLEDGE_ROOT / "graph" / "kg_triples.json"
RAG_CHUNKS_PATH: Path = KNOWLEDGE_ROOT / "rag" / "rag_chunks.jsonl"
SOURCE_CATALOG_PATH: Path = KNOWLEDGE_ROOT / "rag" / "source_catalog.json"

LLM_MODE: str = os.getenv("LLM_MODE", "api").lower()
ALLOWED_AUTHORITY_LEVELS = {"A", "B", "C"}
ALLOWED_SECTION_TYPES = {
    "symptom",
    "cause",
    "condition",
    "transmission",
    "management",
    "differential_diagnosis",
    "model_boundary",
    "demo_safety",
    "risk_note",
}
