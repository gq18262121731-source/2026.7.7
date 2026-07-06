# KG RAG Agent v0.1 Design

## Module Position

KG RAG Agent v0.1 is an experimental knowledge-enhancement module for the rice disease recognition system. It adds structured disease knowledge, lightweight JSON knowledge graph data, local RAG chunks, and a mock LLM diagnosis-report generator.

## Relationship With v0.6 Frozen System

This module does not modify detector logic, `/api/detect/image`, dashboard statistics, mock default mode, YOLO/Torch dependencies, UAV SDK, weather API, map service, or model routing. It is mounted only through experimental endpoints:

- `GET /api/knowledge/diseases`
- `GET /api/knowledge/diseases/{disease_id}`
- `POST /api/knowledge/search`
- `POST /api/agent/diagnosis-report`

## Knowledge Graph Design

The graph is stored as JSON files under `knowledge/graph`. Entities include crop, disease, pest, pathogen, symptom, plant part, environment, transmission, management measure, model class, and evidence source. Relations include `affects`, `caused_by`, `has_symptom`, `occurs_on`, `favored_by`, `transmitted_by`, `managed_by`, `confused_with`, `maps_to`, `supported_by`, and `vector_of`.

## RAG Design

The local RAG store uses `knowledge/rag/rag_chunks.jsonl`. v0.1 uses weighted keyword retrieval, not a vector database. Scores favor exact `disease_id`, disease names, aliases, section type, A/B authority level, and keyword hits.

## Agent Design

The agent resolves `disease_id` first, then falls back to `model_class_mapping`. It reads disease JSON, KG summary, and RAG chunks, then calls the mock LLM client to produce a structured report.

## Model Boundary

Reports are auxiliary explanations only. The agent must not state final diagnosis, formal model performance, or absolute pesticide dosage. Tungro is marked as high-risk and not recommended for formal model statements or backend demo conclusions in v0.1.

## Risk Control

Every successful report includes evidence sources and uncertainty notes. Unknown mappings return `insufficient_evidence=true`. `LLM_MODE=mock` is the default and requires no network or API key.
