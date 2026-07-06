# 农业无人机病虫害识别系统对外接口联调包

生成日期：2026-07-06  
接口包版本：v0.8-mobile-llm-context

本目录是给移动端、大屏、主系统团队使用的对外联调说明书。它不是后端内部接口大全，而是回答“怎么连、先调哪个、字段怎么传、失败怎么处理、哪些能力不能正式依赖”。

## 适用对象

| 对接方 | 推荐入口 | 目标 |
|---|---|---|
| 移动端 | `mobile_api_integration.md` | 第一阶段先接拍照识别、识别详情、LLM 状态、知识检索、知识上下文和自由问答；地块与告警为第二阶段可选 |
| 大屏 | `dashboard_api_integration.md` | 态势总览、地图/热力图、最新记录、最新告警、WebSocket 通知 |
| 主系统 | `main_system_api_integration.md` | 田块、UAV 任务、dry-run、异常区、手机复查、风险融合、巡检报告 |

## 环境地址

正式联调示例统一使用：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

生产环境地址待部署后替换：

```bash
BASE_URL="https://api.example.com"
TOKEN="replace-with-your-token"
```

本机开发说明：

```bash
BASE_URL="http://127.0.0.1:8000"
TOKEN="replace-with-your-token"
```

本机地址只用于后端开发者本地调试，不作为移动端、大屏或主系统正式联调地址。

## 鉴权方式

所有对外联调示例统一使用 Bearer Token：

```http
Authorization: Bearer <TOKEN>
```

当前演示环境可能未强制鉴权，但对外联调和正式部署建议统一使用 Bearer Token 口径。若启用鉴权，未授权建议返回：

```json
{
  "success": false,
  "error_code": "UNAUTHORIZED",
  "message": "未授权或 token 无效",
  "detail": {}
}
```

## 推荐阅读顺序

1. 先看 `api_quick_start.md`，5 分钟确认服务可连通。
2. 移动端看 `mobile_api_integration.md`。
3. 大屏看 `dashboard_api_integration.md` 和 `websocket_integration.md`。
4. 主系统看 `main_system_api_integration.md`。
5. 调响应字段看 `sample_responses.md`。
6. 调错误处理看 `error_codes.md`。
7. 验收前看 `integration_acceptance_checklist.md`。
8. 机器可读接口看 `openapi.json`，Postman 调试看 `postman_collection.json`。

## 文件说明

| 文件 | 用途 |
|---|---|
| `README.md` | 对外联调入口 |
| `api_quick_start.md` | 5 分钟快速联调 |
| `mobile_api_integration.md` | 移动端最小闭环接口 |
| `dashboard_api_integration.md` | 大屏只读接口和实时通知策略 |
| `main_system_api_integration.md` | 主系统业务流程接口 |
| `websocket_integration.md` | WebSocket 连接、事件、重连、补拉 |
| `sample_responses.md` | 核心响应样例 |
| `error_codes.md` | 统一错误结构与错误码 |
| `openapi.json` | FastAPI OpenAPI 导出 |
| `postman_collection.json` | Postman 联调集合 |
| `integration_acceptance_checklist.md` | 联调验收清单 |
| `api_contract_full.md` | 全量接口底稿 |
| `changelog.md` | 接口包变更记录 |

## 接口稳定性

| 标记 | 含义 | 对接建议 |
|---|---|---|
| `stable` | 可用于正式联调 | 移动端、大屏、主系统可依赖 |
| `preview` | 可联调，字段可能调整 | 需容忍字段新增、空值 |
| `experimental` | 实验能力 | 不建议正式依赖，不作为农艺诊断或用药依据 |
| `internal` | 内部诊断接口 | 不建议对外使用 |

特别说明：

| 状态 | 含义 |
|---|---|
| `mock` | 模拟结果，仅用于界面演示和流程联调 |
| `smoke` | 烟测能力，仅验证链路，不代表正式识别效果 |
| `experimental` | 实验能力，结果需人工复核，不作为正式农艺诊断或用药依据 |
| `real` | 模型推理结果，仍建议结合人工巡检和田间情况复核 |

`/api/experimental/*` 均属于 `experimental`。返回 `model_stage=experimental`、`detector_mode=smoke`、`is_smoke=true`、`fallback_to_mock=true` 时，前端必须显示能力边界。

## 上传与图片 URL 规则

- 图片上传使用 `multipart/form-data`。
- 单图上传字段名为 `file`。
- 批量上传字段名为 `files`。
- 图片不通过 WebSocket 传输。
- WebSocket 不传 base64，不传视频帧。
- `image_url` 和 `result_image_url` 用于前端展示图片。
- 若返回相对路径，前端用 `BASE_URL` 拼接。
- 正式部署建议后端返回绝对 URL。

## WebSocket 总原则

WebSocket 只推 JSON 事件，用于通知“有新结果/新任务状态/新告警”。客户端收到事件后应通过 HTTP 接口补拉详情：

- 新识别记录：`GET /api/dashboard/latest-records`
- 新告警：`GET /api/dashboard/latest-alerts`
- 批处理任务：`GET /api/tasks/{task_id}`

不要依赖 WebSocket 保存历史数据。
