# 接口包变更记录

## v0.8-mobile-llm-context - 2026-07-06

本轮目标：将移动端第一阶段范围从“地块首页优先”调整为“拍照识别 + LLM 知识问答优先”，并补齐 LLM 可用的知识库与知识图谱上下文接口。

### 新增

- 后端新增 `POST /api/agent/knowledge-context`，用于聚合知识库片段、知识图谱实体、关系、三元组和安全边界。
- `sample_responses.md` 新增 `LLMStatusResponse`、`KnowledgeSearchResponse`、`KnowledgeContextResponse`、`DiagnosisReportFreeQA` 样例。
- `postman_collection.json` 新增 `Agent LLM Status`、`Knowledge Search`、`Knowledge Context`、`Diagnosis Report Free QA` 请求。

### 调整

- `mobile_api_integration.md` 第一阶段接口调整为 `healthz`、模型状态、LLM 状态、拍照识别、记录详情、记录建议、知识检索、知识上下文、自由问答。
- `GET /api/mobile/overview`、`GET /api/mobile/plots`、`GET /api/mobile/plots/{plot_id}`、`POST /api/uav/abnormal-regions/{region_id}/phone-followup`、`GET /api/mobile/alerts` 调整为移动端第二阶段可选。
- `api_quick_start.md` 增加 LLM 状态、知识检索、知识上下文和自由问答快速联调步骤。
- `integration_acceptance_checklist.md` 拆分移动端第一阶段验收与第二阶段可选验收。
- `error_codes.md` 补充 `DISEASE_NOT_FOUND`、`KNOWLEDGE_CONTEXT_NOT_FOUND`、`KNOWLEDGE_DATA_ERROR`、`LLM_API_ERROR`。

### 安全口径

- LLM / RAG / KG 结果仅用于辅助解释，不作为正式农艺诊断或用药依据。
- 快捷问题只能作为输入辅助，不允许前端写死答案。

## v0.7-integration - 2026-07-06

本轮目标：将原有接口底稿整理为移动端、大屏、主系统可直接使用的对外联调文档。

### 新增或重写

- `README.md`：重写为对外联调入口，补充适用对象、环境地址、鉴权、阅读顺序、稳定性和安全边界。
- `api_quick_start.md`：新增 5 分钟快速联调流程。
- `mobile_api_integration.md`：新增移动端最小闭环接口说明。
- `dashboard_api_integration.md`：新增大屏接口与 WebSocket 补拉策略说明。
- `main_system_api_integration.md`：新增主系统业务流程接口说明。
- `websocket_integration.md`：新增 WebSocket 事件、心跳、重连和补拉说明。
- `sample_responses.md`：重写核心响应样例。
- `error_codes.md`：新增统一错误结构和错误码说明。
- `integration_acceptance_checklist.md`：重写联调验收清单。
- `postman_collection.json`：更新为 `BASE_URL` / `TOKEN` 变量口径，并覆盖移动端、大屏、主系统最小接口。

### 保留

- `openapi.json`：保留当前 FastAPI OpenAPI 导出。
- `api_contract_full.md`：保留全量接口底稿。
- 旧版 `mobile_integration_guide.md`、`dashboard_integration_guide.md`、`main_system_integration_guide.md`、`websocket_examples.md`、`curl_examples.md` 作为历史参考保留。

### 统一口径

- 正式联调示例使用 `BASE_URL="https://test-api.example.com"`。
- 请求示例使用 `Authorization: Bearer <TOKEN>`。
- 图片上传使用 `multipart/form-data`。
- 单图字段名为 `file`。
- 批量字段名为 `files`。
- WebSocket 只推 JSON 事件，不传图片、base64 或视频帧。
- `mock`、`smoke`、`experimental` 均不作为正式农艺诊断或用药依据。
