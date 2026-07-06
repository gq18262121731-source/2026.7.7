# 移动端第一阶段验收清单

## 通用验收

| 项 | 通过标准 |
|---|---|
| 环境变量 | 示例统一使用 `BASE_URL` 和 `TOKEN` |
| 鉴权 | 请求携带 `Authorization: Bearer <TOKEN>` |
| 健康检查 | `GET /healthz` 返回正常 |
| OpenAPI | `openapi_mobile_llm_cn.json` 可被解析 |
| Postman | `postman_mobile_llm_cn.json` 可导入 |
| 错误响应 | 前端能识别统一错误结构 |
| 图片 URL | 相对路径可用 `BASE_URL` 拼接 |
| 安全边界 | `mock` / `smoke` / `experimental` / `real` 均有展示口径 |

## 移动端第一阶段验收

| 场景 | 通过标准 |
|---|---|
| 健康检查 | `GET /healthz` 可确认服务可连通 |
| 模型状态 | `GET /api/models/status` 可展示模型阶段和安全边界 |
| LLM 状态 | `GET /api/agent/llm-status` 可展示 LLM、mock fallback 或未配置状态 |
| 手机上传 | `POST /api/detect/image` 使用 `multipart/form-data` 和 `file` |
| 记录详情 | `GET /api/mobile/records/{record_id}` 可展示图片和结果 |
| 建议 | `GET /api/mobile/suggestions/{record_id}` 展示 `disclaimer` |
| 知识检索 | `POST /api/knowledge/search` 可按问题返回知识片段 |
| 知识上下文 | `POST /api/agent/knowledge-context` 可返回知识片段、图谱实体、关系、三元组和安全提示 |
| 自由问答 | `POST /api/agent/diagnosis-report` 支持 `user_question` 并返回辅助解释 |
| 非预设问题 | 用户输入非快捷问题也能得到回答或明确降级状态 |
| 降级识别 | `fallback_used`、`fallback_level`、`llm_mode`、`api_error_type` 可用于判断某次回答是否降级 |
| 安全边界 | LLM / RAG / KG 结果不作为正式农艺诊断或用药依据 |

## 上传验收

| 项 | 通过标准 |
|---|---|
| 单图字段 | `file` |
| Content-Type | 使用 `multipart/form-data` |
| boundary | 移动端 FormData 上传时由 HTTP 客户端自动生成 |
| 图片展示 | 使用 `image_url` / `result_image_url` |
| 相对路径 | 可用 `BASE_URL` 拼接 |
| 错误处理 | `INVALID_IMAGE`、`FILE_TOO_LARGE`、`STORAGE_ERROR` 有中文提示 |

## 错误响应验收

| 错误码 | 必须覆盖 |
|---|---|
| `INVALID_IMAGE` | 是 |
| `FILE_TOO_LARGE` | 是 |
| `MODEL_ERROR` | 是 |
| `STORAGE_ERROR` | 是 |
| `RECORD_NOT_FOUND` | 是 |
| `DISEASE_NOT_FOUND` | 是 |
| `KNOWLEDGE_CONTEXT_NOT_FOUND` | 是 |
| `KNOWLEDGE_DATA_ERROR` | 是 |
| `LLM_API_ERROR` | 是 |
| `DATABASE_ERROR` | 是 |
| `VALIDATION_ERROR` | 是 |
| `INTERNAL_ERROR` | 是 |

## 安全边界验收

| 状态 | 前端必须展示 |
|---|---|
| `mock` | 模拟结果，仅用于演示 |
| `smoke` | 烟测结果，仅验证链路 |
| `experimental` | 实验能力，不作为正式农艺诊断或用药依据 |
| `real` | 模型推理结果，仍需人工复核 |

## 不属于第一阶段验收

以下内容不作为本包第一阶段验收项：

```text
地块
首页
异常区复查
告警
巡检报告
其他端接口
实时通知接口
```
