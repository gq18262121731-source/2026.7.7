from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from app.core.knowledge_config import RAG_CHUNKS_PATH, SOURCE_CATALOG_PATH


class KnowledgeDataError(RuntimeError):
    pass


def _read_json(path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise KnowledgeDataError(f"Cannot read knowledge file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise KnowledgeDataError(f"Invalid JSON knowledge file: {path}") from exc


@lru_cache(maxsize=1)
def load_source_catalog() -> dict[str, dict[str, Any]]:
    items = _read_json(SOURCE_CATALOG_PATH)
    return {item["source_id"]: item for item in items}


@lru_cache(maxsize=1)
def load_rag_chunks() -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    try:
        with RAG_CHUNKS_PATH.open("r", encoding="utf-8") as file:
            for line_no, line in enumerate(file, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    chunks.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    raise KnowledgeDataError(f"Invalid JSONL at {RAG_CHUNKS_PATH}:{line_no}") from exc
    except OSError as exc:
        raise KnowledgeDataError(f"Cannot read RAG file: {RAG_CHUNKS_PATH}") from exc
    return chunks


def _tokens(query: str) -> list[str]:
    normalized = query.lower().strip()
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", normalized)
    cjk_terms = [char for char in normalized if "\u4e00" <= char <= "\u9fff"]
    tokens = [normalized] if normalized else []
    tokens.extend(words)
    tokens.extend(cjk_terms)
    seen: set[str] = set()
    return [token for token in tokens if token and not (token in seen or seen.add(token))]


class RagService:
    def search(
        self,
        query: str,
        disease_id: str | None = None,
        section_type: str | None = None,
        top_k: int = 5,
        disease_lookup: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        tokens = _tokens(query)
        results: list[dict[str, Any]] = []
        for chunk in load_rag_chunks():
            score = 0.0
            chunk_text = " ".join(
                [
                    str(chunk.get("text", "")),
                    str(chunk.get("source_title", "")),
                    str(chunk.get("disease_id", "")),
                    str(chunk.get("section_type", "")),
                ]
            ).lower()
            chunk_disease_id = chunk.get("disease_id")
            disease = (disease_lookup or {}).get(chunk_disease_id, {})

            if disease_id and chunk_disease_id == disease_id:
                score += 5
            elif disease_id:
                score -= 2

            names = [disease.get("zh_name", ""), disease.get("en_name", "")]
            if any(name and name.lower() in chunk_text for name in names):
                score += 4
            aliases = [str(item).lower() for item in disease.get("aliases", [])]
            if any(alias and alias in chunk_text for alias in aliases):
                score += 3
            if section_type and chunk.get("section_type") == section_type:
                score += 2
            if chunk.get("authority_level") == "A":
                score += 2
            elif chunk.get("authority_level") == "B":
                score += 1
            score += sum(1 for token in tokens if token.lower() in chunk_text)

            if score <= 0 and (disease_id or section_type or query):
                continue
            enriched = dict(chunk)
            enriched["score"] = round(score, 2)
            results.append(enriched)

        results.sort(key=lambda item: item["score"], reverse=True)
        return results[: max(1, min(top_k, 20))]


rag_service = RagService()
