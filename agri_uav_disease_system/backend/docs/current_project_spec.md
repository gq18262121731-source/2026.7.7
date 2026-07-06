# 农业无人机水稻病虫害识别系统后端项目说明书

更新时间：2026-06-30

## 1. 项目定位

本项目当前实现的是“农业无人机/移动端水稻病虫害识别系统”的后端最小可运行闭环。系统以 FastAPI + SQLite 为基础，已经覆盖图片识别、批量任务、结果存储、大屏查询、移动端查询、预警治理、模型状态展示、WebSocket JSON 推送，以及 Stage 6.1 的规则化病虫害风险预测。

当前系统仍以 Mock、smoke、experimental 接入验证为主，不宣称具备正式生产模型能力。所有 smoke/experimental 模型状态和规则预测结果都必须按辅助演示或工程联调能力展示。

## 2. 已完成功能总览

### 2.1 单图识别主链路

已完成：
- 图片上传接口。
- 图片格式校验、文件保存。
- Mock/可选 smoke/experimental 检测路由。
- 统一 `detection_result` 返回结构。
- 原图与结果图静态访问。
- SQLite 保存识别记录。
- 识别完成后通过 `/ws/results` 推送 JSON。
- medium/high 病虫害识别结果可生成 detection alert。

接口：
- `POST /api/detect/image`
- `GET /api/records`
- `GET /api/records/{record_id}`
- `GET /api/upload/capabilities`

### 2.2 批量识别任务

已完成：
- 多图批量上传。
- 本地后台任务处理。
- 任务状态、进度、成功记录、失败项保存。
- 任务进度通过 `/ws/tasks` 推送 JSON。

接口：
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`

### 2.3 大屏数据接口

已完成：
- 首页汇总统计。
- 地块聚合。
- 地块详情。
- 地块记录分页。
- 风险热力图。
- 病虫害类型统计。
- 最新记录。
- 最新预警。

接口：
- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/plots/{plot_id}/records`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`

说明：
- 地块按 `plot_id` 聚合。
- 经纬度优先来自识别记录，缺失时使用 `app/mocks/mock_plots.json` 兜底。
- heatmap 的颜色和 intensity 只是展示建议，不是模型指标。

### 2.4 移动端接口

已完成：
- 移动端概览。
- 地块列表。
- 地块详情。
- 识别记录详情。
- 移动端预警列表。
- 农事建议查询。
- `user_id` 预留参数。

接口：
- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- `GET /api/mobile/alerts`
- `GET /api/mobile/suggestions/{record_id}`

说明：
- 当前未接真实用户、登录、鉴权、地块权限系统。
- `user_id` 当前只作为前向兼容参数，不做过滤。

### 2.5 预警治理

已完成：
- medium/high detection 结果生成 detection alert。
- cooldown 内同一 `plot_id + main_disease` 聚合更新同一个 active alert。
- 风险升级时更新原 alert。
- alert 列表、详情、处理、处理动作查询。
- `/ws/alerts` 推送 alert JSON。
- Stage 6.1 已扩展 prediction alert。

接口：
- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `GET /api/alerts/{alert_id}/actions`
- `WS /ws/alerts`

alert 来源：
- `alert_source=detection`：来自已识别到的 medium/high 记录。
- `alert_source=prediction`：来自未来风险预测的 medium/high 结果。

### 2.6 WebSocket 实时推送

已完成 3 个通道：
- `WS /ws/results`：识别结果事件。
- `WS /ws/tasks`：批量任务进度事件。
- `WS /ws/alerts`：预警事件。

边界：
- 只推送结构化 JSON。
- 不推送图片。
- 不推送 base64。
- 不推送视频帧。
- 推送失败不影响接口返回和数据库保存。

### 2.7 模型状态、演示安全与可选模型路由

已完成：
- 系统状态接口。
- 模型状态接口。
- demo safety 展示规则。
- Mock fallback 状态展示。
- phone smoke、UAV crop-object smoke、UAV BLB smoke、UAV BLB experimental、phone experimental 的状态结构和路由说明。

接口：
- `GET /healthz`
- `GET /api/status`
- `GET /api/models/status`
- `GET /api/models/demo-safety`

当前模型边界：
- Mock 是默认稳定联调链路。
- smoke 权重只用于工程接线验证，不是正式模型。
- experimental 权重只用于实验性验证，不是正式模型。
- UAV crop route 当前是 `crop_object`，不能展示为病害识别。
- 所有 smoke/experimental 均不得展示正式 Precision、Recall、mAP、F1。
- 若依赖或权重不可用，接口走 Mock fallback，保证后端主链路可用。

### 2.8 Stage 6.1 病虫害风险预测

已完成：
- 天气记录手工录入和查询。
- 生育期记录录入、人工修正和基础日期推断。
- 管护记录录入和查询。
- 从历史识别、天气、生育期、管护、active alert 提取规则特征。
- 未来 3/7/14 天规则化风险预测。
- 预测结果保存到 `risk_predictions`。
- 大屏预测汇总。
- 大屏预测风险地图。
- 移动端预测列表。
- 移动端地块预测详情。
- medium/high 预测结果可生成 prediction alert。
- prediction alert 通过 `/ws/alerts` 推送 JSON。

接口：
- `GET /api/prediction/plots/{plot_id}`
- `GET /api/prediction/dashboard/summary`
- `GET /api/prediction/risk-map`
- `GET /api/mobile/predictions`
- `GET /api/mobile/plots/{plot_id}/prediction`
- `POST /api/weather/observations`
- `GET /api/weather/observations`
- `POST /api/growth-stages`
- `GET /api/growth-stages/plots/{plot_id}`
- `POST /api/farm-operations`
- `GET /api/farm-operations`
- `GET /api/farm-operations/plots/{plot_id}`

预测模型：
- 类型：`rule_based`
- 版本：`risk-rule-v0.1`
- 评分范围：`0-100`
- 风险等级：`normal`、`low`、`medium`、`high`
- `risk_probability = risk_score / 100`

重要说明：
- `risk_probability` 只是规则分数归一化值，不是真实统计概率。
- 当前不提供真实预测准确率、AUC、F1。
- 农事建议只是辅助参考。
- 不输出具体农药剂量。
- 具体防治方案和用药剂量需由农技人员确认。

## 3. 数据库表

当前 SQLite 主要表：
- `detection_records`：识别记录。
- `batch_tasks`：批量任务。
- `alerts`：预警事件。
- `alert_actions`：预警处理动作。
- `weather_observations`：天气手工记录。
- `plot_growth_stages`：地块生育期记录。
- `farm_operations`：农事/管护操作记录。
- `risk_predictions`：风险预测结果。

`alerts` 已扩展字段：
- `alert_source TEXT DEFAULT 'detection'`
- `prediction_id TEXT`
- `prediction_window_days INTEGER`

## 4. 当前验收状态

最近一次完整验收命令：

```bash
python -m compileall app
python -m pytest app/tests -q
python -m app.scripts.system_smoke_test
```

最近一次结果：
- `compileall`：通过。
- `pytest`：`54 passed`。
- `system_smoke_test`：全部 PASS。

system smoke 覆盖：
- FastAPI app import。
- SQLite。
- 静态目录可写。
- `healthz`。
- `api status`。
- 单图识别。
- 静态原图/结果图访问。
- 记录详情。
- 大屏汇总。
- 移动端概览。
- alert 生成。
- alerts 查询。
- `/ws/results`。
- `/ws/tasks`。
- `/ws/alerts`。

## 5. 已有文档

核心文档：
- `docs/api_contract.md`
- `docs/system_v0_5_freeze_summary.md`
- `docs/system_model_route_matrix.md`
- `docs/system_demo_runbook.md`
- `docs/system_acceptance_summary.md`
- `docs/stage6_prediction_design.md`
- `docs/prediction_api_contract.md`
- `docs/risk_rule_model.md`
- `docs/farm_operation_recording.md`
- `docs/weather_growth_stage_data.md`
- `docs/stage6_prediction_acceptance.md`

联调示例：
- `docs/integration_examples/curl_examples.md`
- `docs/integration_examples/dashboard.http`
- `docs/integration_examples/mobile.http`
- `docs/integration_examples/model_status.http`
- `docs/integration_examples/postman_collection.json`
- `docs/integration_examples/websocket_examples.md`

## 6. 当前未完成或不属于当前阶段的内容

尚未实现：
- 真实生产级 YOLO 病虫害模型接入。
- 后端模型训练。
- 正式 Precision、Recall、mAP、F1、AUC、预测准确率。
- 真实天气 API。
- 真实传感器接入。
- 真实无人机 SDK。
- 真实地图服务。
- 完整前端大屏页面。
- 完整移动端 App。
- 用户登录、鉴权、地块权限。
- 告警处理完整审计工作流。
- 生产级任务队列，如 Celery/RQ。
- 生产级部署、监控、SLA。

明确禁止展示为已完成：
- 把 Mock/smoke/experimental 结果说成正式模型结果。
- 把 `risk_probability` 说成真实概率。
- 把规则预测说成训练模型预测。
- 输出具体农药剂量。
- 通过 WebSocket 传图片、base64 或视频帧。

## 7. 推荐下一阶段

建议下一阶段优先做 Stage 6.2 或 Stage 7：

1. 补齐预测模块的前端展示：大屏预测 summary、risk-map、移动端预测详情。
2. 为天气、生育期、管护记录增加更完整的编辑和删除接口。
3. 增加预测结果去重和同一地块预测 alert cooldown 策略。
4. 引入真实用户和地块权限。
5. 准备正式模型接入规范：类别体系、权重路径、模型评估报告、输入输出协议。
6. 在模型训练分支具备正式指标后，再替换后端推理适配器。
