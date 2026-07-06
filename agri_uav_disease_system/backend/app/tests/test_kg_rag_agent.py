from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.knowledge_config import (
    DISEASES_DIR,
    KG_ENTITIES_PATH,
    KG_RELATIONS_PATH,
    KG_TRIPLES_PATH,
    RAG_CHUNKS_PATH,
    SOURCE_CATALOG_PATH,
)
from app.main import app
from app.services.knowledge_service import knowledge_service


client = TestClient(app)

REQUIRED_DISEASE_FIELDS = {
    "disease_id",
    "zh_name",
    "en_name",
    "aliases",
    "pathogen_type",
    "pathogen_name",
    "affected_crop",
    "affected_parts",
    "typical_symptoms",
    "early_symptoms",
    "late_symptoms",
    "similar_diseases",
    "favorable_conditions",
    "transmission",
    "risk_notes",
    "management_suggestions",
    "model_class_mapping",
    "evidence_sources",
    "authority_level",
    "last_updated",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_disease_json_files_exist_and_have_required_fields():
    expected = {"bacterial_leaf_blight", "rice_blast", "brown_spot", "tungro"}
    paths = {path.stem: path for path in DISEASES_DIR.glob("*.json")}
    assert expected.issubset(paths.keys())

    disease_ids: set[str] = set()
    for disease_id in expected:
        payload = read_json(paths[disease_id])
        assert REQUIRED_DISEASE_FIELDS.issubset(payload.keys())
        assert payload["disease_id"] not in disease_ids
        disease_ids.add(payload["disease_id"])
        assert payload["authority_level"] in {"A", "B", "C"}
        assert len(payload["evidence_sources"]) >= 2
        assert payload["management_suggestions"]


def test_source_catalog_kg_and_rag_are_consistent():
    source_catalog = {item["source_id"]: item for item in read_json(SOURCE_CATALOG_PATH)}
    assert source_catalog
    assert all(item["authority_level"] in {"A", "B"} for item in source_catalog.values())

    entities = read_json(KG_ENTITIES_PATH)
    entity_ids = [item["entity_id"] for item in entities]
    assert len(entity_ids) == len(set(entity_ids))
    relation_ids = {item["relation_id"] for item in read_json(KG_RELATIONS_PATH)}
    triples = read_json(KG_TRIPLES_PATH)
    for triple in triples:
        assert triple["subject"] in entity_ids
        assert triple["object"] in entity_ids
        assert triple["predicate"] in relation_ids
        assert triple["evidence_source_ids"]
        assert set(triple["evidence_source_ids"]).issubset(source_catalog.keys())

    disease_counts = {"bacterial_leaf_blight": 0, "rice_blast": 0, "brown_spot": 0, "tungro": 0}
    for triple in triples:
        for disease_id in disease_counts:
            if f"disease:{disease_id}" in {triple["subject"], triple["object"]}:
                disease_counts[disease_id] += 1
    assert all(count >= 8 for count in disease_counts.values())

    chunks = read_jsonl(RAG_CHUNKS_PATH)
    assert chunks
    chunk_counts = {disease_id: 0 for disease_id in disease_counts}
    for chunk in chunks:
        assert chunk["source_id"] in source_catalog
        assert chunk["chunk_id"]
        assert chunk["text"]
        chunk_counts[chunk["disease_id"]] += 1
    assert all(count >= 5 for count in chunk_counts.values())


def test_knowledge_api_list_detail_and_404():
    response = client.get("/api/knowledge/diseases")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 4
    assert {item["disease_id"] for item in payload["items"]} == {
        "bacterial_leaf_blight",
        "rice_blast",
        "brown_spot",
        "tungro",
    }

    detail = client.get("/api/knowledge/diseases/bacterial_leaf_blight")
    assert detail.status_code == 200
    assert detail.json()["zh_name"] == "水稻白叶枯病"

    missing = client.get("/api/knowledge/diseases/not_exist")
    assert missing.status_code == 404


def test_knowledge_search_returns_scored_source_metadata():
    response = client.post(
        "/api/knowledge/search",
        json={
            "query": "白叶枯病的典型症状是什么？",
            "disease_id": "bacterial_leaf_blight",
            "section_type": "symptom",
            "top_k": 5,
        },
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert results
    assert results[0]["chunk_id"]
    assert results[0]["score"] > 0
    assert results[0]["source_title"]
    assert results[0]["authority_level"] in {"A", "B"}


def test_agent_knowledge_context_returns_rag_and_graph_context():
    response = client.post(
        "/api/agent/knowledge-context",
        json={
            "question": "为什么识别结果提示可能是白叶枯？",
            "model_class": "uav_blb",
            "confidence": 0.78,
            "source_type": "phone_rgb",
            "top_k": 3,
            "include_knowledge_chunks": True,
            "include_graph": True,
            "include_relations": True,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["mode"] == "knowledge_context"
    assert payload["matched_disease"]["disease_id"] == "bacterial_leaf_blight"
    assert payload["knowledge_chunks"]
    assert payload["knowledge_chunks"][0]["content"]
    assert payload["graph"]["entities"]
    assert payload["graph"]["relations"]
    assert payload["graph"]["triples"]
    assert "正式农艺诊断" in payload["safety_notice"]


def test_agent_report_from_disease_id_and_model_class_contains_safety_fields():
    response = client.post(
        "/api/agent/diagnosis-report",
        json={
            "record_id": None,
            "disease_id": "bacterial_leaf_blight",
            "model_class": "uav_blb",
            "confidence": 0.72,
            "source_type": "uav",
            "user_question": "这个结果严重吗？",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["suspected_disease"]["disease_id"] == "bacterial_leaf_blight"
    assert payload["insufficient_evidence"] is False
    assert payload["risk_level"] in {"medium", "high"}
    assert payload["manual_check_questions"]
    assert payload["management_suggestions"]
    assert payload["uncertainty_notes"]
    assert payload["evidence_sources"]
    joined = json.dumps(payload, ensure_ascii=False)
    assert "最终诊断" not in joined
    assert "每亩" not in joined
    assert "仅作辅助判断" in joined
    assert "产品标签" in joined

    mapped = client.post("/api/agent/diagnosis-report", json={"model_class": "phone_brown_spot", "confidence": 0.66})
    assert mapped.status_code == 200
    assert mapped.json()["suspected_disease"]["disease_id"] == "brown_spot"


def test_agent_unknown_mapping_and_tungro_boundary():
    unknown = client.post("/api/agent/diagnosis-report", json={"model_class": "unknown_class"})
    assert unknown.status_code == 200
    unknown_payload = unknown.json()
    assert unknown_payload["insufficient_evidence"] is True
    assert unknown_payload["evidence_sources"] == []

    tungro = client.post(
        "/api/agent/diagnosis-report",
        json={"disease_id": "tungro", "model_class": "phone_tungro", "confidence": 0.61},
    )
    assert tungro.status_code == 200
    joined = json.dumps(tungro.json(), ensure_ascii=False)
    assert "不建议直接进入正式模型声明" in joined
    assert "高风险" in joined or "风险较高" in joined


def test_model_class_mapping_unknown_is_explicit():
    assert knowledge_service.map_model_class_to_disease("not_a_class") == {
        "status": "unknown_mapping",
        "disease_id": None,
    }
