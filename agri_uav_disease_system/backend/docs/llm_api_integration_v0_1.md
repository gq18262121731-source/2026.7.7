# LLM API Integration v0.1

## Position

`llm-api-integration-v0.1-formal` adds a real OpenAI-compatible Chat Completions client to the experimental kg-rag-agent diagnosis explanation module.

This integration does not modify v0.6 detection logic, `/api/detect/image`, dashboard statistics, YOLO/Torch dependencies, multimodal models, or image reading behavior.

## Environment Variables

Set local `.env` values from `.env.example`:

```env
LLM_MODE=api
LLM_PROVIDER=custom_openai_compatible
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=30
LLM_MAX_TOKENS=1200
LLM_TEMPERATURE=0.2
LLM_ENABLE_MOCK_FALLBACK=true
LLM_PROMPT_VERSION=kg_rag_agent_prompt_v1
```

Rules:

- Never commit a real API key.
- Never log `LLM_API_KEY`.
- `.env.example` keeps credential values empty.
- If API mode fails and `LLM_ENABLE_MOCK_FALLBACK=true`, the agent returns a mock fallback report with `fallback_used=true`.

## Provider Style

The client supports OpenAI-compatible Chat Completions:

```text
POST {LLM_BASE_URL}/chat/completions
```

Request body:

```json
{
  "model": "LLM_MODEL",
  "messages": [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "structured context"}
  ],
  "temperature": 0.2,
  "max_tokens": 1200
}
```

No new dependency is required; the implementation uses Python standard library `urllib.request`.

## Prompt Version

`kg_rag_agent_prompt_v1`

The system prompt instructs the model to generate only from:

- image model result fields
- disease profile JSON
- KG summary
- RAG evidence chunks
- response policy

It forbids unsupported facts, final diagnosis wording, pesticide dosage, concentration, mixture ratios, and forced treatment plans.

## User Context

The user message is strict JSON:

```json
{
  "model_result": {
    "disease_id": "",
    "model_class": "",
    "confidence": null,
    "source_type": "",
    "is_mock_or_smoke_or_experimental": true
  },
  "disease_profile": {},
  "kg_summary": {},
  "rag_evidence": [],
  "response_policy": {
    "not_final_diagnosis": true,
    "no_pesticide_dosage": true,
    "must_include_uncertainty_notes": true,
    "must_include_evidence_sources": true,
    "tungro_extra_warning": true
  }
}
```

## Output Contract

The LLM must return strict JSON. The API response adds:

- `llm_mode`
- `llm_provider`
- `llm_model`
- `prompt_version`
- `fallback_used`
- `api_error_type`

The response never returns the API key, Authorization header, or raw request.

## Postprocessing

The backend validates and normalizes:

- JSON parse success.
- Required report fields.
- `uncertainty_notes`.
- `evidence_sources`.
- risk level.
- no final diagnosis wording.
- no pesticide dose/concentration/ratio text.
- experimental boundary notes.
- tungro extra risk warning.

If protection text is missing, the backend appends it. If dosage-like text appears, it is sanitized and replaced with a local-authority/product-label safety statement.

## Manual Real API Validation

To run a real-provider smoke check, create local `.env` values:

```env
LLM_MODE=api
LLM_PROVIDER=custom_openai_compatible
LLM_API_KEY=your-local-key
LLM_BASE_URL=https://provider.example/v1
LLM_MODEL=provider-model
LLM_ENABLE_MOCK_FALLBACK=true
```

Then call:

```json
{
  "disease_id": "bacterial_leaf_blight",
  "model_class": "uav_blb",
  "confidence": 0.72,
  "source_type": "uav",
  "user_question": "请根据当前识别结果生成辅助诊断解释。"
}
```

Expected:

- `llm_mode=api`
- `fallback_used=false`
- non-empty `evidence_sources`
- non-empty `uncertainty_notes`
- no API key in response
- no pesticide dosage
- no final diagnosis wording
