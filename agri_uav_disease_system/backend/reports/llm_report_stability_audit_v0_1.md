# LLM Report Stability Audit v0.1

## Audit Scope

This audit covers the `kg-rag-agent-v0.1-experimental` LLM report path only:

- `POST /api/agent/diagnosis-report`
- `GET /api/agent/llm-status`
- LLM client configuration, JSON parsing, schema validation, repair retry, and fallback metadata

The frozen v0.6 detection mainline, `/api/detect/image`, and dashboard statistics logic were not modified.

## Implementation Summary

### Model Configuration

- Real LLM integration: YES
- Report model migrated to `deepseek-v4-flash`: YES
- `.env.example` now recommends:
  - `LLM_BASE_URL=https://api.deepseek.com`
  - `LLM_MODEL=deepseek-v4-flash`
  - `LLM_ENABLE_JSON_RESPONSE_FORMAT=true`
  - `LLM_ENABLE_MOCK_FALLBACK=true`
- Local `.env` was updated only for `LLM_MODEL=deepseek-v4-flash`; no API key was printed or committed.
- No API key is hardcoded.

### Schema Validation

Added Pydantic validation for the final LLM report shape. The validated report includes:

- `suspected_disease`
- `model_result_summary`
- `knowledge_summary`
- `risk_level`
- `manual_check_questions`
- `management_suggestions`
- `uncertainty_notes`
- `evidence_sources`
- `insufficient_evidence`
- `llm_mode`
- `llm_provider`
- `llm_model`
- `prompt_version`
- `fallback_used`
- `fallback_level`
- `api_error_type`
- `repair_attempted`
- `schema_valid`
- `safety_passed`

`risk_level` is restricted to:

- `low`
- `medium`
- `high`
- `unknown`

### Repair Retry

If a real LLM response is valid JSON but misses required report fields or uses an invalid `risk_level`, the client performs one repair request.

The repair request includes:

- the validation error
- the target schema fields
- allowed `risk_level` values
- the previous model output
- the same bounded KG/RAG source context

The repair prompt requires strict JSON only and forbids adding facts outside the provided evidence.

### Fallback Metadata

Responses now include explicit audit fields:

- `fallback_used`
- `fallback_level`
- `api_error_type`
- `repair_attempted`
- `schema_valid`
- `safety_passed`

Fallback levels used in this version:

- `none`: no fallback used
- `mock_template`: real API path failed and mock fallback generated a safe local report
- `insufficient_evidence`: no reliable disease mapping or evidence path exists, so LLM is not called

### LLM Status Endpoint

Added:

```text
GET /api/agent/llm-status
```

Returns:

- `llm_mode`
- `llm_provider`
- `llm_model`
- `json_response_format_enabled`
- `mock_fallback_enabled`
- `api_key_configured`
- `prompt_version`

Does not return:

- API key
- Authorization header
- full prompt
- full request body

## Safety and Boundary Statement

- Whether real LLM is connected: YES
- Whether mock fallback is still retained: YES
- Whether multimodal model is connected: NO
- Whether images are directly read by the LLM: NO
- Whether YOLO/Torch/torchvision were installed: NO
- Whether v0.6 frozen mainline was modified: NO
- Whether `/api/detect/image` was modified: NO
- Whether dashboard statistics were modified: NO
- Whether this can be used as formal agricultural diagnosis: NO. It is auxiliary explanation only and does not replace agricultural expert field diagnosis.

## Test Results

- `compileall`: PASS
- `pytest`: PASS, `75 passed, 16 skipped, 1 warning`
- LLM integration tests: PASS, `14 passed, 1 warning`
- `system_smoke_test`: PASS
- `/api/status detector_mode`: `mock`
- `/api/models/status detector_mode`: `mock`
- `ultralytics`: `None`
- `torch`: `None`
- `torchvision`: `None`
- Live `deepseek-v4-flash` smoke call: `api False None False True none`

Known non-blocking warning:

- Existing `StarletteDeprecationWarning` from FastAPI TestClient/httpx compatibility.

## Final Gate

PASS

The report-type LLM path is more stable and auditable, with schema validation, one repair retry, fallback classification, and a safe status endpoint. The v0.6 mock frozen detection chain remains unchanged.
