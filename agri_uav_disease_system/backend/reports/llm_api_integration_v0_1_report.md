# LLM API Integration v0.1 Report

完成时间：2026-07-03  
状态命名：`llm-api-integration-v0.1-formal`

## 1. 本轮目标

在 `kg-rag-agent-v0.1-experimental` 基础上，将 agent 诊断解释模块从纯 mock 模板扩展为真实 LLM API 优先、mock fallback 保留的生成链路。

本轮不接多模态模型，不直接读取图片，不修改检测主逻辑，不修改 `/api/detect/image`，不修改 dashboard 统计口径，不安装 YOLO/Torch/torchvision。

## 2. 修改文件列表

- `.env.example`
- `app/core/knowledge_config.py`
- `app/services/llm_client.py`
- `app/services/agent_service.py`
- `app/api/agent.py`
- `app/schemas/agent_schema.py`
- `app/tests/test_llm_api_integration.py`
- `docs/llm_api_integration_v0_1.md`
- `docs/agent_response_policy.md`
- `reports/llm_api_integration_v0_1_report.md`

## 3. 环境变量说明

新增 LLM 配置示例：

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

安全规则：

- 真实 API key 只写入本地 `.env`。
- `.env.example` 保持空 key。
- 不在代码、日志、报告、API response 中返回 API key。
- 当前仓库下未发现 `.env`，因此未执行真实 provider 手动调用。

## 4. LLM Provider 接入方式

实现方式：OpenAI-compatible Chat Completions。

Endpoint：

```text
{LLM_BASE_URL}/chat/completions
```

实现使用 Python 标准库 `urllib.request`，未新增依赖。

请求结构：

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

## 5. Prompt Version

```text
kg_rag_agent_prompt_v1
```

## 6. Prompt 安全规则

system prompt 约束模型只能基于：

1. 图像模型识别结果字段
2. 结构化病害知识 `disease_profile`
3. 知识图谱摘要 `kg_summary`
4. RAG 检索证据 `rag_evidence`
5. 系统响应安全规则 `response_policy`

禁止：

- 编造未提供事实。
- 将模型识别结果说成最终诊断。
- 输出具体农药剂量、浓度、配比或强制施药方案。
- 绕过 KG/RAG 生成事实。
- 读取图片或调用多模态模型。

必须：

- 输出严格 JSON。
- 说明仅作辅助判断，不替代农业专家现场诊断。
- 说明具体药剂、浓度和施用时间以当地农业技术部门建议和产品标签为准。
- 证据不足时返回 `insufficient_evidence=true`。

## 7. 后处理校验规则

后端对 LLM 输出执行：

- 严格 JSON 解析。
- required fields 补齐。
- `risk_level` 规范化。
- `suspected_disease` 规范化。
- `evidence_sources` 缺失时从 KG summary 回填。
- `uncertainty_notes` 缺失时自动补充保护口径。
- `tungro` 缺少额外风险提示时自动补充。
- “最终诊断”表述替换为“辅助判断”。
- 具体药剂剂量、浓度、配比、每亩/每公顷等表达过滤，并追加当地农业技术部门和产品标签安全提示。

## 8. Fallback 策略

默认：

```env
LLM_MODE=api
LLM_ENABLE_MOCK_FALLBACK=true
```

行为：

- API 成功：返回 `llm_mode=api`、`fallback_used=false`。
- API 失败且 fallback 开启：返回 mock 报告，标记 `fallback_used=true` 和 `api_error_type`。
- API 失败且 fallback 关闭：`POST /api/agent/diagnosis-report` 返回清晰 `502 LLM_API_ERROR`。
- unknown `model_class` 不调用 LLM，直接返回 `insufficient_evidence=true`。

## 9. 测试结果

执行环境：`backend\.venv\Scripts\python.exe`

| 检查项 | 结果 |
| --- | --- |
| 新增 LLM API 集成测试 | PASS，`9 passed, 1 warning` |
| kg-rag-agent 原有测试 | PASS，`7 passed, 1 warning` |
| 无 key api-first fallback 样例 | PASS，`llm_mode=mock`、`fallback_used=true`、`api_error_type=missing_api_key` |
| compileall | PASS |
| 全量 pytest | PASS，`56 passed, 15 skipped, 1 warning` |
| system_smoke_test | PASS |
| `/api/status detector_mode` | PASS，`mock` |
| `/api/models/status detector_mode` | PASS，`mock` |
| `ultralytics` | PASS，`None` |
| `torch` | PASS，`None` |
| `torchvision` | PASS，`None` |

保留 warning：

- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`。该 warning 为既有测试依赖生态提示，不影响本轮功能。

## 10. 真实 API 手动验收结果

当前未执行真实 provider 手动验收。

原因：

- 当前 backend 目录未发现本地 `.env`。
- 未提供 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。
- 按安全要求不能伪造真实 API 调用结果，不能将真实 key 写入报告。

已完成替代验证：

- 使用 monkeypatch fake Chat Completions 响应模拟 API 成功。
- 使用 fake 非法 JSON 响应验证 fallback。
- 使用 fake 缺失 evidence 响应验证自动回填。
- 使用 fake 农药剂量响应验证过滤。
- 使用 fake tungro 响应验证风险保护补充。

## 11. 是否修改 v0.6 检测主链路

NO。

## 12. 是否修改 `/api/detect/image`

NO。

## 13. 是否修改 dashboard

NO。

## 14. 是否安装 YOLO/Torch

NO。

验证：

- `ultralytics`: `None`
- `torch`: `None`
- `torchvision`: `None`

## 15. 是否接入多模态模型

NO。

本轮只接文本 LLM Chat Completions，不读取图片，不调用视觉模型。

## 16. 是否直接读取图片

NO。

Agent 只读取请求字段、disease JSON、KG summary 和 RAG chunks。

## 17. 是否可用于正式农学诊断

NO，仅辅助解释。

报告仍必须说明：

- 当前结果仅作辅助判断，不替代农业专家现场诊断。
- 当前模块处于 experimental 阶段，不应作为正式生产诊断依据。
- 具体药剂、浓度和施用时间应以当地农业技术部门建议和产品标签为准。

## 18. 当前 Gate

Gate：WARNING

原因：

- 真实 LLM API 接入代码、schema、prompt、后处理、fallback 和 fake-provider 测试均已完成。
- v0.6 mock 冻结链路回归通过。
- 但当前未提供真实 `.env` 凭据，真实 provider 手动验收未执行，不能诚实标记为 PASS。

后续在本地配置真实 `.env` 后，如果 BLB、unknown、tungro 三组手动验收均通过，可升级为 PASS。
