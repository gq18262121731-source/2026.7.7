# P-LLM-1 Free Question Agent Report

## 1. Current Problem Diagnosis

Before P-LLM-1, the frontend AI entry behaved like a preset diagnosis template:

- `smoke-demo.html` always sent a fixed `user_question`.
- Quick interaction centered on generating an AI diagnosis explanation, not asking a real user question.
- Backend RAG did use `user_question` as the query, but the agent always entered the diagnosis-report flow and required a resolvable disease mapping.
- Unknown mapping or missing disease context could block useful inspection Q&A even when the user question was about field/UAV/risk context rather than a specific disease.

## 2. Modified Files

- `app/schemas/agent_schema.py`
  - Extended request context fields: `field_id`, `plot_id`, `uav_task_id`, `abnormal_region_id`, `risk_level`, `severity`.
  - Extended response with compatible free-QA fields: `mode`, `question`, `answer`, `basis`, `uncertainty`, `next_steps`, `safety_notice`, `used_context`, `retrieved_knowledge`, `llm_status`.
- `app/api/agent.py`
  - Passes new context fields into `AgentService`.
- `app/services/agent_service.py`
  - Adds `free_qa` mode when `user_question` is non-empty.
  - Builds inspection context from request fields, detection record, UAV task, abnormal region, risk/severity, detector mode, smoke/experimental state, and suggestion.
  - Uses the real user question as the RAG query.
- `app/services/llm_client.py`
  - Adds free-QA LLM prompt, schema normalization, safe fallback, and compatible response assembly.
  - LLM unavailable fallback explicitly says no real LLM answer was generated.
- `app/static/frontend/smoke-demo.html`
  - Adds AI inspection Q&A input and send flow.
  - Preset questions are retained as quick chips that fill/send `user_question`; they do not map to fixed answers.
- `app/tests/test_llm_api_integration.py`
  - Adds free-QA tests for routing, RAG query usage, and LLM failure fallback.

## 3. Frontend Free Question Entry

The static demo frontend now exposes an `AI 巡检问答` area near the existing AI explanation panel.

It includes:

- A free text input box.
- A send button.
- Quick question chips.
- Friendly error when no question is entered.

Quick chips call the same `generateAiReport(record)` function and send the same `POST /api/agent/diagnosis-report` request with `user_question`.

## 4. Backend User Question Flow

`AgentService.generate_diagnosis_report()` now checks:

```text
if user_question.strip():
    mode = free_qa
else:
    mode = diagnosis_report
```

Free-QA mode does not require disease mapping. If disease context exists, it is used; if not, the response must expose missing context rather than inventing it.

## 5. RAG Query Behavior

PASS. Free-QA RAG retrieval uses the real user question:

```text
knowledge_service.search_knowledge(question, resolved_disease_id, None, 5)
```

This was covered by `test_free_qa_uses_real_user_question_for_rag`.

## 6. Context Fields Included

The free-QA context can include:

- `record_id`
- `field_id`
- `plot_id`
- `uav_task_id`
- `abnormal_region_id`
- `disease_id`
- `model_class`
- `confidence`
- `source_type`
- `risk_level`
- `severity`
- `detector_mode`
- `is_smoke`
- `model_stage`
- `record_summary`
- `suggestion`
- `uav_task`
- `abnormal_region`
- `missing_context`

Missing fields are included in `missing_context`.

## 7. Preset Question Status

Preset questions are retained only as quick-entry chips. They are not mapped to fixed answers. Clicking a chip fills/sends the same `user_question` path used by the free text input.

## 8. Safety Boundaries

The free-QA prompt and post-processing require:

- No automatic diagnosis claim.
- No accuracy guarantee.
- No pesticide prescription.
- No replacement of field inspection or agricultural experts.
- Manual review recommendation.
- Explicit missing-context or insufficient-knowledge statements when applicable.

The response includes:

- `safety_notice`
- `uncertainty`
- `next_steps`
- existing `uncertainty_notes`

## 9. LLM Unavailable Fallback

If LLM API fails and mock fallback is enabled, free-QA does not fake a real AI answer.

It returns:

- `mode=free_qa`
- `fallback_used=true`
- `api_error_type=<error>`
- an answer stating real LLM Q&A is temporarily unavailable
- context and missing-context summary

## 10. Free Question Test Summary

The following 10 real free questions were tested through the agent service with real LLM enabled:

1. `为什么这个异常区 UAV 显示中风险，但手机近景识别置信度不高？`
2. `这个识别结果可靠吗，哪些因素可能导致误判？`
3. `如果我今天只能复查一个区域，应该优先看哪里？`
4. `这个结果和历史记录相比有没有变严重？`
5. `当前知识库能不能支持判断这是白叶枯？`
6. `我需要补拍什么样的图片才能提高复核可信度？`
7. `这个建议能不能直接作为用药依据？`
8. `为什么模型说是病害，但风险融合结果不是高风险？`
9. `如果 UAV 图像异常但手机图像正常，可能是什么原因？`
10. `当前回答用了哪些数据作为依据？`

Result summary:

```text
1 free_qa True False None True 5
2 free_qa True False None True 5
3 free_qa True False None True 5
4 free_qa True False None True 5
5 free_qa True False None True 5
6 free_qa True False None True 5
7 free_qa True False None True 5
8 free_qa True False None True 5
9 free_qa True False None True 5
10 free_qa True False None True 5
```

Meaning:

- `mode=free_qa`
- answer exists
- no fallback
- no API error
- schema valid
- 5 retrieved knowledge items

## 11. Backend Verification

- `python -m compileall app`: PASS
- `pytest`: PASS, `78 passed, 16 skipped, 1 warning`
- `system_smoke_test`: PASS
- `/api/status detector_mode`: `mock`
- `/api/models/status detector_mode`: `mock`
- `ultralytics`: `None`
- `torch`: `None`
- `torchvision`: `None`

Known warning:

- Existing `StarletteDeprecationWarning` from FastAPI TestClient/httpx compatibility.

## 12. Frontend Build Result

No frontend `package.json` exists in `agri_uav_disease_system`, so `npm.cmd run build` is not applicable.

Recorded result:

```text
npm build: SKIPPED_NO_PACKAGE_JSON
```

Additional static check:

```text
static-js-syntax PASS
```

## 13. Unfinished Items

- The current frontend is a static smoke/demo HTML, not a full componentized frontend with a production build pipeline.
- The dynamic Q&A panel was added to the existing smoke demo AI panel. A future frontend app can move the same interaction into a dedicated `InspectionContextPanel`.
- Historical comparison answers depend on available record history; missing context is reported rather than invented.

## 14. Next Steps

- Add a dedicated frontend component when the project moves beyond static smoke demo HTML.
- Add optional richer context adapters for risk fusion history and inspection reports.
- Keep free-QA output audited with `mode`, `question`, `used_context`, `retrieved_knowledge`, and fallback metadata.

## Final Gate

P-LLM-1: PASS
