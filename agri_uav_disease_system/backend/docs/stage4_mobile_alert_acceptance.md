# Stage 4 Mobile And Alert Acceptance

本文档记录第四阶段“移动端联动、地块详情和预警治理补强”的后端验收状态。当前系统仍使用 `mock_disease_detector mock-v1`，不训练模型，不接真实 YOLO，不接真实无人机 SDK，不接真实地图服务。

## 新增和增强接口

地块详情与历史记录：

- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/plots/{plot_id}/records`

移动端联动：

- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- 保留 `GET /api/mobile/alerts`
- 保留 `GET /api/mobile/suggestions/{record_id}`

预警治理：

- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `WS /ws/alerts`

已有接口保持兼容：

- `POST /api/detect/image`
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`
- `GET /api/records`
- `GET /api/records/{record_id}`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`
- `WS /ws/results`
- `WS /ws/tasks`

## Alert 表字段

SQLite `alerts` 表字段：

- `alert_id`
- `plot_id`
- `plot_name`
- `region_name`
- `main_disease`
- `severity`
- `risk_level`
- `status`
- `message`
- `suggestion_json`
- `record_ids_json`
- `first_record_id`
- `latest_record_id`
- `first_seen_at`
- `latest_seen_at`
- `cooldown_until`
- `created_at`
- `updated_at`

`status` 当前预留：

- `active`
- `muted`
- `resolved`

## Alert Cooldown 规则

- `normal` 和 `low` 识别记录默认不生成预警。
- `medium` 和 `high` 识别记录会进入预警服务。
- cooldown 内同一 `plot_id + main_disease` 聚合到同一个 active alert。
- cooldown 内重复出现时更新 `latest_record_id`、`latest_seen_at`、`record_ids_json`、`severity`、`risk_level`、`suggestion_json`。
- 如果后续记录风险更高，会升级原 alert，不重复新建。
- cooldown 过期后再次出现同地块同病害，可新建 alert。
- 如果记录缺少 `plot_id`，当前使用 `unknown_plot` 作为兜底。
- cooldown 时长由 `ALERT_COOLDOWN_SECONDS` 配置，默认 `3600` 秒。

## WebSocket Alert Event

`WS /ws/alerts` 只推送 JSON：

```json
{
  "type": "alert_event",
  "alert_id": "alert_20260622_103000_ab12cd34",
  "plot_id": "plot_B_01",
  "plot_name": "B-01 地块",
  "region_name": "未指定乡镇",
  "main_disease": "稻瘟病",
  "severity": "重度",
  "risk_level": "high",
  "status": "active",
  "message": "B-01 地块检测到高风险病虫害，请及时复核。",
  "latest_record_id": "rec_001",
  "timestamp": "2026-06-22T10:30:00.000Z"
}
```

约束：

- 不通过 WebSocket 推送图片、base64 或视频帧。
- 推送失败只记录日志，不影响单图识别、批量任务和 SQLite 保存。
- 客户端断开后会从连接池移除。
- HTTP 查询接口仍是兜底方式。

## 农事建议结构

`suggestion` 保留旧字段：

- `title`
- `content`
- `need_expert_confirm`

新增可选字段：

- `actions`
- `knowledge_tags`
- `disclaimer`

农事建议仅作为辅助参考，不输出具体农药剂量，不输出未经确认的强执行处置指令。

## 已验证内容

本阶段已通过自动化测试验证：

- 地块详情接口可返回聚合状态。
- 地块历史记录接口可分页返回记录。
- 移动端 overview 无数据或有数据时均可返回。
- 移动端地块列表、地块详情、记录详情可返回。
- medium 风险会生成 alert。
- high 风险会生成 alert。
- cooldown 内同一地块同一病害不重复生成 alert。
- 风险升级会更新原 alert。
- `/api/alerts` 可分页查询。
- `/api/alerts/{alert_id}` 可返回详情。
- `/api/alerts/{alert_id}/resolve` 可把状态改为 `resolved`。
- `/ws/alerts` 可收到 `alert_event`。
- 新增资源不存在时返回统一错误结构。
- 原有单图、批量、大屏和记录接口未被破坏。

## Pytest 结果

执行命令：

```bash
python -m compileall app
python -m pytest app/tests -q
```

当前结果：

```text
24 passed
```

## 明确未做事项

- 未训练模型。
- 未接真实 YOLO 权重。
- 未生成或伪造 Precision、Recall、mAP 等模型指标。
- 未接真实无人机 SDK。
- 未接真实地图服务。
- 未做完整大屏页面。
- 未做完整移动端页面。
- 未接真实用户登录、鉴权和告警处理审计链。
- 未通过 WebSocket 传输图片、base64 或视频帧。
- 未输出具体农药剂量或强执行用药指令。

## 下一阶段建议

- 增加真实用户、地块归属和角色权限。
- 为 alert 增加处理人、处理备注、处理时间和审计日志。
- 把批量任务迁移到可恢复队列，例如 Celery 或 RQ。
- 接入训练分支交付的真实 YOLO 适配器，但保留 Mock 回退。
- 增加地图服务适配层，把 mock geo 数据替换为真实 GIS 数据。
- 增加接口级 OpenAPI 示例和联调用 Postman/HTTP 文件。

## 第五阶段补充状态

第五阶段已在 Stage 4 基础上补齐联调和验收包：

- `/api/status` 增加能力、模型、存储状态结构。
- `/api/models/status` 增加真实模型接入前置检查，但不加载真实 YOLO。
- `alert_actions` 表和 `/api/alerts/{alert_id}/actions` 已作为处理审计链骨架落地。
- `resolve alert` 支持 `operator_id`、`operator_name`、`note`。
- 移动端 `overview` 和 `plots` 支持预留 `user_id` 参数，当前不做登录鉴权。
- 已新增 seed 和 smoke 脚本，以及 `docs/integration_examples/` 联调示例包。

第五阶段完整验收见 `docs/stage5_integration_acceptance.md`。
