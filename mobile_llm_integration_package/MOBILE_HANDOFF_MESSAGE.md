# 可发送给移动端团队的对接说明

移动端第一阶段接口联调包已整理完成，结论为：

```text
Mobile LLM Integration Package: RC
```

本阶段移动端先不接地块、首页、异常区复查、告警和巡检报告，优先完成以下最小闭环：

```text
拍照识别 -> 识别详情 -> LLM 状态 -> 知识检索 -> 知识上下文 -> 自由问答
```

请优先阅读：

```text
mobile_api_integration.md
```

第二阶段可选接口已单独放入：

```text
mobile_api_phase2_optional.md
```

快速跑通流程请看：

```text
api_quick_start.md
```

Postman 可直接导入：

```text
postman_mobile_llm_cn.json
```

机器可读接口：

```text
openapi_mobile_llm_cn.json
```

核心响应样例：

```text
sample_responses.md
```

错误码说明：

```text
error_codes.md
```

验收清单：

```text
integration_acceptance_checklist.md
```

本阶段重点接口如下：

```http
GET  /healthz
GET  /api/models/status
GET  /api/agent/llm-status
POST /api/detect/image
GET  /api/mobile/records/{record_id}
GET  /api/mobile/suggestions/{record_id}
POST /api/knowledge/search
POST /api/agent/knowledge-context
POST /api/agent/diagnosis-report
```

其中：

- `/api/detect/image` 用于手机拍照识别；
- `/api/mobile/records/{record_id}` 用于查看识别详情；
- `/api/agent/llm-status` 用于检查 LLM 问答能力状态，不是问答接口；
- `/api/knowledge/search` 用于知识库检索；
- `/api/agent/knowledge-context` 用于读取知识库和知识图谱上下文；
- `/api/agent/diagnosis-report` 用于自由问答。

说明：

- 图片上传统一使用 `multipart/form-data`。
- 图片字段名为 `file`。
- 不通过任何实时通道上传图片、base64 或视频帧。
- LLM 和知识图谱回答仅用于辅助解释，不作为正式农艺诊断或用药依据。
- 快捷问题可以作为输入辅助，但移动端应支持用户自由输入真实问题。
- LLM 状态不影响图片识别结果展示。即使 LLM 不可用，移动端仍应展示识别图片、识别结果、风险等级、建议和免责声明。
- `mock_fallback_enabled=true` 只表示允许降级，不表示当前回答已经降级；某次回答是否降级，要看 `diagnosis-report` 响应里的 `fallback_used`、`fallback_level`、`llm_mode`、`api_error_type`。
- 单图识别成功后，请把响应中的 `record_id` 写入 Postman 变量或移动端状态，再请求记录详情、记录建议、知识上下文和自由问答接口。
- `model_class` 不要写死为 UAV 类别；移动端应优先使用识别结果中的 `class_code` / `class_name` / `label`，或使用后端返回的 `disease_id` 映射结果。

LLM 状态显示建议：

| 后端状态 | 移动端显示建议 |
|---|---|
| `llm_mode=openai` 且 `api_key_configured=true` | AI 辅助问答可用 |
| `llm_mode=mock` | 当前为模拟回答，仅用于联调演示 |
| `api_key_configured=false` | AI 服务未配置，暂不可用 |
| 接口请求失败或后续出现 `LLM_API_ERROR` | AI 问答服务异常，请稍后重试 |

当前已完成验证：

```text
pytest app\tests\test_kg_rag_agent.py
8 passed
openapi_mobile_llm_cn.json parse OK
postman_mobile_llm_cn.json parse OK
```

正式联调前，我们会单独提供真实 `BASE_URL` 和 `TOKEN`。请不要使用文档中的占位地址直接联调。当前包为 RC 版，可用于对齐接口和开发准备；正式联调以 `openapi_mobile_llm_cn.json` 和真实环境返回为准。

## 真实地址和 Token 单独发送模板

```text
移动端联调环境：

BASE_URL = <这里填写真实测试环境地址>
TOKEN = <单独提供>

请先用 Postman 按以下顺序验证：

1. GET /healthz
2. GET /api/agent/llm-status
3. POST /api/detect/image
4. GET /api/mobile/records/{record_id}
5. POST /api/agent/knowledge-context
6. POST /api/agent/diagnosis-report

这 6 个接口跑通后，再开始移动端页面接入。
```
