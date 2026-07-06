# 联调验收清单

## 通用验收

| 项 | 通过标准 |
|---|---|
| 环境变量 | 示例统一使用 `BASE_URL` 和 `TOKEN` |
| 鉴权 | 请求携带 `Authorization: Bearer <TOKEN>` |
| 健康检查 | `GET /healthz` 返回正常 |
| OpenAPI | `openapi.json` 可被解析 |
| Postman | `postman_collection.json` 可导入 |
| 错误响应 | 前端能识别统一错误结构 |
| 图片 URL | 相对路径可用 `BASE_URL` 拼接 |
| 安全边界 | mock / smoke / experimental / real 均有展示口径 |

## 移动端第一阶段验收

| 场景 | 通过标准 |
|---|---|
| 健康检查 | `GET /healthz` 可确认服务可连通 |
| 模型状态 | `GET /api/models/status` 可展示模型阶段和安全边界 |
| LLM 状态 | `GET /api/agent/llm-status` 可展示 LLM、mock fallback 或未配置状态 |
| 手机上传 | `POST /api/detect/image` 使用 `multipart/form-data` 和 `file` |
| 记录详情 | `GET /api/mobile/records/{record_id}` 可展示图片和结果 |
| 建议 | `GET /api/mobile/suggestions/{record_id}` 展示 disclaimer |
| 知识检索 | `POST /api/knowledge/search` 可按问题返回知识片段 |
| 知识上下文 | `POST /api/agent/knowledge-context` 可返回知识片段、图谱实体、关系、三元组和安全提示 |
| 自由问答 | `POST /api/agent/diagnosis-report` 支持 `user_question` 并返回辅助解释 |
| 非预设问题 | 用户输入非快捷问题也能得到回答或明确降级状态 |
| 安全边界 | LLM / RAG / KG 结果不作为正式农艺诊断或用药依据 |

## 移动端第二阶段可选验收

| 场景 | 通过标准 |
|---|---|
| 首页 | `GET /api/mobile/overview` 可展示摘要 |
| 地块列表 | `GET /api/mobile/plots` 可展示地块 |
| 地块详情 | `GET /api/mobile/plots/{plot_id}` 可展示详情 |
| 异常区复查 | `POST /api/uav/abnormal-regions/{region_id}/phone-followup` 可返回记录 |
| 告警 | `GET /api/mobile/alerts` 可展示风险告警 |

## 大屏验收

| 场景 | 通过标准 |
|---|---|
| 总览数字 | `GET /api/dashboard/summary` 正常 |
| 地块风险 | `GET /api/dashboard/plots` 正常 |
| 地块详情 | `GET /api/dashboard/plots/{plot_id}` 正常 |
| 热力图 | `GET /api/dashboard/heatmap` 正常 |
| 病害统计 | `GET /api/dashboard/disease-statistics` 正常 |
| 最新记录 | `GET /api/dashboard/latest-records` 正常 |
| 最新告警 | `GET /api/dashboard/latest-alerts` 正常 |
| WebSocket 补拉 | 收到事件后能通过 HTTP 补拉 |

## 主系统验收

| 场景 | 通过标准 |
|---|---|
| 创建地块 | `POST /api/fields` 成功 |
| 查询地块 | `GET /api/fields` 和 `GET /api/fields/{field_id}` 成功 |
| 创建 UAV 任务 | `POST /api/uav/tasks` 成功 |
| 查询 UAV 任务 | `GET /api/uav/tasks` 和 `GET /api/uav/tasks/{uav_task_id}` 成功 |
| dry-run | `POST /api/uav/tasks/{uav_task_id}/dry-run` 返回指数和异常区 |
| 异常区 | `GET /api/uav/tasks/{uav_task_id}/abnormal-regions` 正常 |
| 手机复查 | 复查后异常区出现回写字段 |
| 风险融合 | `POST /api/risk/fusion/evaluate` 返回 experimental 规则评分 |
| 报告 | `POST /api/inspection-reports/generate` 成功 |
| 报告历史 | `GET /api/inspection-reports` 和详情接口正常 |

## WebSocket 验收

| 项 | 通过标准 |
|---|---|
| `/ws/results` | 可连接，收到事件后补拉 latest-records |
| `/ws/tasks` | 可连接，收到事件后补拉 task status |
| `/ws/alerts` | 可连接，收到事件后补拉 latest-alerts |
| 断线重连 | 客户端能自动重连 |
| 历史补拉 | 重连后通过 HTTP 补拉 |
| 传输限制 | 不传图片、不传 base64、不传视频帧 |

## 上传验收

| 项 | 通过标准 |
|---|---|
| 单图字段 | `file` |
| 批量字段 | `files` |
| Content-Type | `multipart/form-data` |
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
| `ALERT_NOT_FOUND` | 是 |
| `INTERNAL_ERROR` | 是 |

## 安全边界验收

| 状态 | 前端必须展示 |
|---|---|
| `mock` | 模拟结果，仅用于演示 |
| `smoke` | 烟测结果，仅验证链路 |
| `experimental` | 实验能力，不作为正式农艺诊断或用药依据 |
| `real` | 模型推理结果，仍需人工复核 |
