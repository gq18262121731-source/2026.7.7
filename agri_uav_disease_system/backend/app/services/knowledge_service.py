from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.core.knowledge_config import (
    DISEASES_DIR,
    KG_ENTITIES_PATH,
    KG_RELATIONS_PATH,
    KG_TRIPLES_PATH,
)
from app.services.rag_service import KnowledgeDataError, load_source_catalog, rag_service


class KnowledgeNotFoundError(LookupError):
    pass


def _read_json(path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise KnowledgeDataError(f"Cannot read knowledge file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise KnowledgeDataError(f"Invalid JSON knowledge file: {path}") from exc


@lru_cache(maxsize=1)
def load_diseases() -> dict[str, dict[str, Any]]:
    diseases: dict[str, dict[str, Any]] = {}
    for path in sorted(DISEASES_DIR.glob("*.json")):
        item = _read_json(path)
        disease_id = item.get("disease_id")
        if not disease_id:
            raise KnowledgeDataError(f"Missing disease_id in {path}")
        diseases[disease_id] = item
    return diseases


@lru_cache(maxsize=1)
def load_kg_entities() -> dict[str, dict[str, Any]]:
    return {item["entity_id"]: item for item in _read_json(KG_ENTITIES_PATH)}


@lru_cache(maxsize=1)
def load_kg_relations() -> dict[str, dict[str, Any]]:
    return {item["relation_id"]: item for item in _read_json(KG_RELATIONS_PATH)}


@lru_cache(maxsize=1)
def load_kg_triples() -> list[dict[str, Any]]:
    return _read_json(KG_TRIPLES_PATH)


class KnowledgeService:
    def list_diseases(self) -> list[dict[str, Any]]:
        items = []
        for disease in load_diseases().values():
            items.append(
                {
                    "disease_id": disease["disease_id"],
                    "zh_name": disease["zh_name"],
                    "en_name": disease["en_name"],
                    "authority_level": disease["authority_level"],
                    "model_supported": bool(disease.get("model_class_mapping")),
                }
            )
        return sorted(items, key=lambda item: item["disease_id"])

    def get_disease(self, disease_id: str) -> dict[str, Any]:
        disease = load_diseases().get(disease_id)
        if not disease:
            raise KnowledgeNotFoundError(f"Unknown disease_id: {disease_id}")
        return disease

    def search_knowledge(
        self,
        query: str,
        disease_id: str | None = None,
        section_type: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if disease_id:
            self.get_disease(disease_id)
        return rag_service.search(query, disease_id, section_type, top_k, load_diseases())

    def get_kg_summary(self, disease_id: str) -> dict[str, Any]:
        disease = self.get_disease(disease_id)
        disease_entity_id = f"disease:{disease_id}"
        entities = load_kg_entities()
        source_catalog = load_source_catalog()
        summary = {
            "disease_id": disease_id,
            "symptoms": [],
            "conditions": [],
            "transmission": [],
            "management": [],
            "confused_with": [],
            "evidence_sources": [],
        }
        source_ids: set[str] = set(disease.get("evidence_sources", []))
        predicate_targets = {
            "has_symptom": "symptoms",
            "favored_by": "conditions",
            "transmitted_by": "transmission",
            "managed_by": "management",
            "confused_with": "confused_with",
        }
        for triple in load_kg_triples():
            if triple.get("subject") != disease_entity_id:
                continue
            key = predicate_targets.get(triple.get("predicate"))
            if key:
                obj = entities.get(triple.get("object"), {})
                label = obj.get("label") or triple.get("object")
                if label not in summary[key]:
                    summary[key].append(label)
            source_ids.update(triple.get("evidence_source_ids", []))

        summary["evidence_sources"] = [
            source_catalog[source_id]
            for source_id in sorted(source_ids)
            if source_id in source_catalog and source_catalog[source_id].get("authority_level") in {"A", "B"}
        ]
        return summary

    def get_kg_context(self, disease_id: str, include_graph: bool = True, include_relations: bool = True) -> dict[str, Any]:
        self.get_disease(disease_id)
        if not include_graph:
            return {"entities": [], "relations": [], "triples": []}

        disease_entity_id = f"disease:{disease_id}"
        entities = load_kg_entities()
        relation_lookup = load_kg_relations()
        selected_triples = [
            triple
            for triple in load_kg_triples()
            if triple.get("subject") == disease_entity_id or triple.get("object") == disease_entity_id
        ]

        selected_entity_ids: set[str] = {disease_entity_id}
        for triple in selected_triples:
            selected_entity_ids.add(str(triple.get("subject")))
            selected_entity_ids.add(str(triple.get("object")))

        context_entities = []
        for entity_id in sorted(selected_entity_ids):
            entity = entities.get(entity_id)
            if not entity:
                continue
            context_entities.append(
                {
                    "entity_id": entity_id,
                    "entity_type": entity.get("type", "unknown"),
                    "name": entity.get("label", entity_id),
                }
            )

        context_relations = []
        context_triples = []
        if include_relations:
            for triple in selected_triples:
                subject = entities.get(triple.get("subject"), {})
                obj = entities.get(triple.get("object"), {})
                predicate = str(triple.get("predicate"))
                relation = relation_lookup.get(predicate, {})
                subject_label = subject.get("label", triple.get("subject"))
                object_label = obj.get("label", triple.get("object"))
                relation_label = relation.get("label", predicate)
                context_relations.append(
                    {
                        "source": subject_label,
                        "relation": relation_label,
                        "target": object_label,
                    }
                )
                context_triples.append([subject_label, relation_label, object_label])

        return {
            "entities": context_entities,
            "relations": context_relations,
            "triples": context_triples,
        }

    def map_model_class_to_disease(self, model_class: str | None) -> dict[str, Any]:
        if not model_class:
            return {"status": "unknown_mapping", "disease_id": None}
        normalized = model_class.strip().lower()
        for disease in load_diseases().values():
            mappings = [str(item).lower() for item in disease.get("model_class_mapping", [])]
            if normalized in mappings:
                return {"status": "mapped", "disease_id": disease["disease_id"]}
        return {"status": "unknown_mapping", "disease_id": None}


knowledge_service = KnowledgeService()
