# KG RAG Agent v0.1 API

## GET /api/knowledge/diseases

Returns the four experimental diseases.

Example response:

```json
{
  "items": [
    {
      "disease_id": "bacterial_leaf_blight",
      "zh_name": "水稻白叶枯病",
      "en_name": "Bacterial leaf blight",
      "authority_level": "A",
      "model_supported": true
    }
  ],
  "count": 4
}
```

## GET /api/knowledge/diseases/{disease_id}

Returns one disease detail JSON. Unknown disease IDs return `404` with `DISEASE_NOT_FOUND`.

## POST /api/knowledge/search

Request:

```json
{
  "query": "白叶枯病的典型症状是什么？",
  "disease_id": "bacterial_leaf_blight",
  "section_type": "symptom",
  "top_k": 5
}
```

Response fields include `chunk_id`, `score`, `text`, `source_title`, `source_type`, `authority_level`, `disease_id`, and `section_type`.

## POST /api/agent/diagnosis-report

Request:

```json
{
  "record_id": null,
  "disease_id": "bacterial_leaf_blight",
  "model_class": "uav_blb",
  "confidence": 0.72,
  "source_type": "uav",
  "user_question": "这个结果严重吗？"
}
```

Response fields:

- `suspected_disease`
- `model_result_summary`
- `knowledge_summary`
- `risk_level`
- `manual_check_questions`
- `management_suggestions`
- `uncertainty_notes`
- `evidence_sources`
- `insufficient_evidence`

## Error Codes

- `DISEASE_NOT_FOUND`: unknown disease id.
- `KNOWLEDGE_DATA_ERROR`: local JSON or JSONL knowledge data cannot be read or parsed.
- `VALIDATION_ERROR`: request schema validation failed.
