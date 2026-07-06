# KG RAG Agent v0.1 Status Report

## Freeze Boundary

- 本轮是否修改业务检测逻辑：NO
- 本轮是否修改 `/api/detect/image`：NO
- 本轮是否修改 dashboard 原统计逻辑：NO
- 本轮是否安装 YOLO/Torch/torchvision：NO
- 本轮是否改变 mock 默认模式：NO
- 本轮新增接口：YES，仅 experimental knowledge/agent
- 本轮是否接真实大模型：NO，默认 mock LLM
- 本轮是否可用于正式农学诊断：NO，仅辅助解释

## Delivered Artifacts

- `knowledge/diseases/*.json`: four disease knowledge files.
- `knowledge/graph/*.json`: lightweight KG entities, relations, and triples.
- `knowledge/rag/source_catalog.json` and `rag_chunks.jsonl`: local RAG store.
- `app/services/*knowledge*`, `rag_service.py`, `agent_service.py`, and `llm_client.py`.
- `app/api/knowledge.py` and `app/api/agent.py`.
- `app/tests/test_kg_rag_agent.py`.
- Design, API, schema, and response policy documents.

## Execution Notes

The requested experimental branch could not be created because local Git did not recognize `F:\学校\病虫害识别` as a repository even though a `.git` directory is visible. Work was kept file-scoped and isolated from detector/dashboard logic.

## Test Results

Executed with `backend\.venv\Scripts\python.exe`, the v0.6 Mock baseline environment:

- compileall: PASS
- pytest: PASS, `46 passed, 15 skipped, 1 warning`
- system_smoke_test: PASS
- `/api/status` detector_mode: `mock`
- `/api/models/status` detector_mode: `mock`
- ultralytics: `None`
- torch: `None`
- torchvision: `None`

Note: the workspace root `.venv` already contains YOLO/Torch packages from older work, but the backend frozen Mock environment `backend\.venv` remains clean and was used for final verification.

## Known Limits

- Retrieval is keyword-based, not vector retrieval.
- Source content is curated local summaries, not live web ingestion.
- `LLM_MODE=api` is only a placeholder and is not enabled.
- The agent does not replace agricultural expert diagnosis.

## Next Steps

- Add a vector retrieval backend only after v0.1 APIs stabilize.
- Add frontend display after backend report format is accepted.
- Add more diseases and pest entries with A/B-grade evidence.
