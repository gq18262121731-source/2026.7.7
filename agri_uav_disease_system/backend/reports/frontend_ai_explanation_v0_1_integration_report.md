# Frontend AI Explanation v0.1 Integration Report

完成时间：2026-07-03  
状态命名：`frontend-ai-explanation-v0.1-experimental`

## 1. 本轮目标

在已通过验收的 `kg-rag-agent-v0.1-experimental` 后端实验线基础上，为现有静态 smoke 演示页新增最小 AI 解读入口。用户在上传识别结果或历史记录详情中点击按钮后，可调用：

```text
POST /api/agent/diagnosis-report
```

并展示后端返回的病害知识解释、风险等级、人工复核问题、处置建议、证据来源和不确定性说明。

## 2. 修改文件列表

- `app/static/frontend/smoke-demo.html`
- `app/tests/test_frontend_ai_explanation_static.py`
- `reports/frontend_ai_explanation_v0_1_integration_report.md`

## 3. 每个文件修改原因

| 文件 | 修改原因 |
| --- | --- |
| `app/static/frontend/smoke-demo.html` | 在识别结果/历史记录详情区域新增“AI 智能解读”面板、按钮、状态渲染、API 调用、字段映射和安全边界文案。 |
| `app/tests/test_frontend_ai_explanation_static.py` | 用轻量静态测试确认入口按钮、agent API 路径和三条保护口径不会被后续前端改动移除。 |
| `reports/frontend_ai_explanation_v0_1_integration_report.md` | 记录本轮前端最小入口集成范围、验证结果和 gate。 |

## 4. 新增前端入口说明

入口位置：`app/static/frontend/smoke-demo.html` 的“识别结果与历史记录”详情区域。

交互：

- 初始状态显示“生成 AI 诊断解释”按钮。
- 点击后显示“正在生成 AI 解读...”。
- 成功后展示结构化报告。
- `insufficient_evidence=true` 时展示“当前知识库证据不足，无法生成可靠解释”。
- 请求失败时展示错误提示，并保留重新生成入口。

该入口不做聊天框，不做复杂多轮智能体，不改移动端页面结构。

## 5. API 调用说明

前端调用：

```text
POST /api/agent/diagnosis-report
```

请求体由当前记录构造：

- `record_id`: 当前识别记录 ID。
- `disease_id`: 从 `summary.main_disease`、`model_hint`、`model_name`、`model_display_name`、`detections[].label` 尝试映射到 `bacterial_leaf_blight`、`rice_blast`、`brown_spot`、`tungro`。
- `model_class`: 优先使用 `disease_id`，无法映射时使用检测标签、主病害、model hint 或 model name。
- `confidence`: 当前记录 `summary.max_confidence`。
- `source_type`: `uav`、`phone` 或 `mock`。
- `user_question`: 固定为“请根据当前识别结果生成辅助诊断解释。”

## 6. 展示字段说明

AI 解读面板展示：

1. 疑似病害
2. 风险等级
3. 模型结果摘要
4. 病害知识解释
5. 人工复核问题
6. 处置建议
7. 证据来源
8. 模型边界与不确定性说明
9. `insufficient_evidence` 状态

证据来源展示 `source_title`、`authority_level`、`source_type` 和 `url_or_reference`。

## 7. 安全边界文案说明

页面显式展示：

```text
本 AI 解读基于图像识别结果、知识图谱和本地 RAG 知识库生成，仅用于辅助判断，不替代农业专家现场诊断。
```

页面显式展示：

```text
当前系统处于 mock / smoke / experimental 阶段，结果不应作为正式生产诊断依据。
```

页面显式展示：

```text
具体药剂、浓度和施用时间应以当地农业技术部门建议和产品标签为准。
```

前端没有把 AI 解读表述为正式农学诊断能力，没有隐藏 mock / smoke / experimental 状态，没有展示强制药剂用量。

## 8. 测试结果

执行环境：`backend\.venv\Scripts\python.exe`

| 检查项 | 结果 |
| --- | --- |
| 静态前端入口测试 | PASS，`1 passed` |
| 静态页面通过 FastAPI 挂载加载 | PASS，`/static/frontend/smoke-demo.html` 返回 200 |
| Node 脚本语法检查 | PASS，`node --check` 无错误 |
| 真实 HTTP 页面检查 | PASS，页面包含按钮和 `/api/agent/diagnosis-report` |
| BLB agent HTTP 样例 | PASS，`insufficient_evidence=false`，证据来源 3 条 |
| unknown model_class HTTP 样例 | PASS，`insufficient_evidence=true` |
| tungro HTTP 样例 | PASS，`risk_level=high`，包含“不建议直接进入正式模型声明”保护短语 |
| 全量 pytest | PASS，`47 passed, 15 skipped, 1 warning` |
| compileall | PASS |
| system_smoke_test | PASS |
| `/api/status detector_mode` | PASS，`mock` |
| `/api/models/status detector_mode` | PASS，`mock` |
| `ultralytics` | PASS，`None` |
| `torch` | PASS，`None` |
| `torchvision` | PASS，`None` |

保留的 warning：

- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`。该警告为既有测试依赖生态提示，不影响本轮 gate。

## 9. 是否影响 v0.6 冻结主链路

NO。

`system_smoke_test` 已覆盖并通过：

- FastAPI app import
- SQLite
- static dirs writable
- healthz
- api status
- detect image
- static original/result
- record detail
- dashboard summary
- mobile overview
- alert generated
- alerts
- websocket results/tasks/alerts

## 10. 是否影响检测接口

NO。

未修改检测主逻辑，未修改 `/api/detect/image` 请求或返回结构。

## 11. 是否接真实 LLM

NO。

前端只调用已有 experimental API；后端仍为默认 mock LLM。

## 12. 是否接 YOLO/Torch

NO。

冻结 Mock 环境检查结果：

- `ultralytics`: `None`
- `torch`: `None`
- `torchvision`: `None`

## 13. 当前 Gate

Gate：PASS

结论：

前端最小 AI 解读入口可用于实验演示。该能力基于后端 kg-rag-agent experimental API 展示病害知识解释、风险等级、人工复核问题、处置建议、证据来源和不确定性说明；不改变 v0.6 mock 冻结主链路，不接真实 YOLO，不接真实 LLM，不替代正式农学诊断。
