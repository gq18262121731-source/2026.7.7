# 对外接口联调包发布检查报告

生成日期：2026-07-06  
检查目录：`backend/docs/integration_package/`

## 1. 本轮目标

将已有接口底稿整理为移动端、大屏、主系统可直接阅读、调试、验收的对外联调文档。

本轮在既有知识库、知识图谱和 Agent 能力基础上新增 `POST /api/agent/knowledge-context` 聚合接口，并同步更新移动端联调文档、响应样例、错误码、Postman 集合和验收清单。

## 2. 新增/更新文件列表

新增或重写：

- `README.md`
- `api_quick_start.md`
- `mobile_api_integration.md`
- `dashboard_api_integration.md`
- `main_system_api_integration.md`
- `websocket_integration.md`
- `sample_responses.md`
- `error_codes.md`
- `integration_acceptance_checklist.md`
- `api_contract_full.md`
- `openapi.json`
- `postman_collection.json`
- `changelog.md`
- `integration_package_release_check_report.md`

保留作为全量或历史参考：

- `curl_examples.md`
- `mobile_integration_guide.md`
- `dashboard_integration_guide.md`
- `main_system_integration_guide.md`
- `websocket_examples.md`

## 3. openapi.json 检查结果

检查命令：

```bash
python -c "import json; json.load(open('openapi.json', encoding='utf-8'))"
```

结果：

```text
json parse OK
```

结论：`openapi.json` 可解析，并已包含 `POST /api/agent/knowledge-context`。

## 4. postman_collection.json 检查结果

检查命令：

```bash
python -c "import json; json.load(open('postman_collection.json', encoding='utf-8'))"
```

结果：

```text
json parse OK
```

结论：`postman_collection.json` 可解析。

## 4.1 后端专项测试结果

检查命令：

```bash
.\.venv\Scripts\python.exe -m pytest app\tests\test_kg_rag_agent.py
```

结果：

```text
8 passed, 1 warning
```

结论：`POST /api/agent/knowledge-context`、知识库检索、知识图谱上下文和 Agent 报告相关专项测试通过。

## 5. 必需文件检查结果

必需文件均存在且非空：

- `README.md`
- `api_quick_start.md`
- `mobile_api_integration.md`
- `dashboard_api_integration.md`
- `main_system_api_integration.md`
- `websocket_integration.md`
- `sample_responses.md`
- `error_codes.md`
- `openapi.json`
- `postman_collection.json`
- `integration_acceptance_checklist.md`
- `changelog.md`

结论：`PASS`

## 6. BASE_URL / TOKEN 检查结果

本轮新增文档和 Postman 集合已统一使用：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

请求示例统一使用：

```http
Authorization: Bearer <TOKEN>
```

旧文档中的演示 token、小写 token 占位和旧 base URL 变量口径已清理或替换。Postman 集合中 Bearer auth 的内部字段名仍为 Postman schema 所需字段，但变量值引用 `{{TOKEN}}`。

结论：`PASS`

## 7. 127.0.0.1 检查结果

`127.0.0.1` 仅保留在本机开发说明中：

- `README.md`
- `api_quick_start.md`
- `api_contract_full.md`
- `curl_examples.md`
- `websocket_examples.md`

这些位置均明确标注为本机开发或后端本机调试，不作为正式联调地址。

结论：`PASS`

## 8. 移动端接口覆盖情况

`mobile_api_integration.md` 第一阶段已覆盖：

- `GET /healthz`
- `GET /api/models/status`
- `GET /api/agent/llm-status`
- `POST /api/detect/image`
- `GET /api/mobile/records/{record_id}`
- `GET /api/mobile/suggestions/{record_id}`
- `POST /api/knowledge/search`
- `POST /api/agent/knowledge-context`
- `POST /api/agent/diagnosis-report`

第二阶段可选覆盖：

- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `POST /api/uav/abnormal-regions/{region_id}/phone-followup`
- `GET /api/mobile/alerts`

每个接口包含用途、方法、路径、参数、成功响应示例、失败响应示例和前端处理建议。

结论：`PASS`

## 9. 大屏接口覆盖情况

`dashboard_api_integration.md` 已覆盖：

- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`
- `WS /ws/results`
- `WS /ws/alerts`

并明确 WebSocket 收到事件后通过 HTTP 补拉 latest records / latest alerts。

结论：`PASS`

## 10. 主系统接口覆盖情况

`main_system_api_integration.md` 已按业务流程覆盖：

- `POST /api/fields`
- `GET /api/fields`
- `GET /api/fields/{field_id}`
- `POST /api/uav/tasks`
- `GET /api/uav/tasks`
- `GET /api/uav/tasks/{uav_task_id}`
- `POST /api/uav/tasks/{uav_task_id}/dry-run`
- `GET /api/uav/tasks/{uav_task_id}/abnormal-regions`
- `GET /api/uav/abnormal-regions/{region_id}`
- `POST /api/uav/abnormal-regions/{region_id}/phone-followup`
- `POST /api/risk/fusion/evaluate`
- `POST /api/inspection-reports/generate`
- `GET /api/inspection-reports`
- `GET /api/inspection-reports/{report_id}`

结论：`PASS`

## 11. WebSocket 文档覆盖情况

`websocket_integration.md` 已覆盖：

- `/ws/results`
- `/ws/tasks`
- `/ws/alerts`
- 事件格式示例
- 心跳说明
- 断线重连说明
- WebSocket 只推 JSON
- 不推图片
- 不推 base64
- 不推视频帧
- 重连后通过 HTTP 补拉最新数据

结论：`PASS`

## 12. 安全边界说明覆盖情况

以下文档均覆盖 mock / smoke / experimental / real 能力边界：

- `README.md`
- `mobile_api_integration.md`
- `dashboard_api_integration.md`
- `main_system_api_integration.md`
- `integration_acceptance_checklist.md`

LLM / RAG / KG 相关文档额外覆盖：

- `GET /api/agent/llm-status`
- `POST /api/knowledge/search`
- `POST /api/agent/knowledge-context`
- `POST /api/agent/diagnosis-report`
- 快捷问题不得写死答案；
- 知识上下文和自由问答不作为正式农艺诊断或用药依据。

统一口径：

- `mock`：模拟结果，仅用于界面演示和流程联调；
- `smoke`：烟测能力，仅验证链路，不代表正式识别效果；
- `experimental`：实验能力，结果需人工复核，不作为正式农艺诊断或用药依据；
- `real`：模型推理结果，仍建议结合人工巡检和田间情况复核。

结论：`PASS`

## 13. 上传说明覆盖情况

文档已明确：

- 图片上传使用 `multipart/form-data`；
- 单图字段名为 `file`；
- 批量上传字段名为 `files`；
- WebSocket 不传图片、不传 base64、不传视频帧；
- `image_url` 和 `result_image_url` 用于前端展示；
- 相对路径用 `BASE_URL` 拼接；
- 正式部署建议返回绝对 URL。

结论：`PASS`

## 14. 未完成项

- 当前文档假设正式联调统一使用 Bearer Token，但演示环境可能尚未强制鉴权。
- 当前部分 FastAPI 默认错误可能仍返回 `detail`，正式部署建议统一转换为 `success/error_code/message/detail` 结构。
- `openapi.json` 已随本轮后端接口变更重新导出；后续接口变更后仍需重新导出。
- Postman 集合覆盖最小联调接口，不等同于全量接口集合。

## 15. 最终结论

`External API Integration Package: READY`
