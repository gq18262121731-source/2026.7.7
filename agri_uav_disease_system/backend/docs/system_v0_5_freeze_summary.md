# System v0.5 Freeze Summary

建议冻结版本名：

```text
system-v0.5-mock-integration-baseline
```

本文档用于冻结当前系统分支的 Mock 可运行、可联调、可演示、可验收基线，方便大屏、移动端和模型训练分支对接。后续真实模型接入建议另开独立分支，不在当前基线上直接大改主链路。

## 1. 当前系统定位

当前系统是“三下乡无人机水稻病虫害识别系统”的后端工程基线。

- 默认使用 `mock_disease_detector mock-v1`。
- 支持单图识别、批量任务、大屏接口、移动端接口、alert 治理、WebSocket JSON 推送。
- 可通过 SQLite 保存识别记录、批量任务和 alert 处理动作。
- 可通过静态 URL 访问原图和结果图。
- 未接真实 YOLO。
- 未接真实无人机 SDK。
- 未接真实地图服务。
- 未做完整大屏前端。
- 未做完整移动端前端。

## 2. 已完成阶段

### Stage 1：单图 MVP

核心能力：

- 单张图片上传。
- Mock 病虫害识别。
- 结果图生成。
- SQLite 保存识别记录。
- 静态资源访问。
- 统一错误结构。
- `/ws/results` 推送识别结果 JSON。

主要接口：

- `POST /api/detect/image`
- `GET /api/records`
- `GET /api/records/{record_id}`
- `GET /api/dashboard/summary`
- `GET /healthz`
- `GET /api/status`
- `WS /ws/results`

### Stage 2：批量任务

核心能力：

- 多图批量识别任务。
- 任务状态保存。
- 任务进度查询。
- `/ws/tasks` 推送任务进度 JSON。
- 失败图片明细保留。

主要接口：

- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`
- `WS /ws/tasks`

### Stage 3：大屏联动

核心能力：

- 大屏汇总统计。
- 地块聚合。
- 热力图点位。
- 病害统计。
- 最新记录和最新预警列表。
- 经纬度优先来自识别记录，缺失时使用 `app/mocks/mock_plots.json`。

主要接口：

- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`

### Stage 4：移动端与预警治理

核心能力：

- 移动端首页概览。
- 移动端地块列表、地块详情、记录详情。
- 地块详情和地块历史记录。
- `alerts` 表和 cooldown 机制。
- alert resolve 骨架。
- `/ws/alerts` 推送 alert JSON。
- 农事建议结构增强。

主要接口：

- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/plots/{plot_id}/records`
- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- `GET /api/mobile/alerts`
- `GET /api/mobile/suggestions/{record_id}`
- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `WS /ws/alerts`

### Stage 5：联调与工程验收包

核心能力：

- `/api/status` 增强能力、模型、存储状态。
- `/api/models/status` 真实模型接入前置检查。
- `alert_actions` 处理审计链骨架。
- `user_id` 移动端预留参数。
- seed 演示数据脚本。
- 一键 smoke 自检脚本。
- 联调 HTTP、curl、Postman、WebSocket 示例。
- 演示流程和验收文档。

主要接口：

- `GET /api/models/status`
- `GET /api/alerts/{alert_id}/actions`
- 增强 `GET /api/status`
- 增强 `POST /api/alerts/{alert_id}/resolve`
- 增强 `GET /api/mobile/overview?user_id=demo_user`
- 增强 `GET /api/mobile/plots?user_id=demo_user`

## 3. 当前接口总表

### 基础状态

- `GET /healthz`
- `GET /api/status`
- `GET /api/models/status`

### 识别与记录

- `POST /api/detect/image`
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`
- `GET /api/records`
- `GET /api/records/{record_id}`

### 大屏

- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/plots/{plot_id}/records`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`

### 移动端

- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- `GET /api/mobile/alerts`
- `GET /api/mobile/suggestions/{record_id}`

### Alert

- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `GET /api/alerts/{alert_id}/actions`

### WebSocket

- `WS /ws/results`
- `WS /ws/tasks`
- `WS /ws/alerts`

接口统计：

- HTTP 接口：24 个。
- WebSocket 通道：3 个。
- 总接口/通道：27 个。

## 4. 大屏联调说明

大屏同学建议优先接：

1. `GET /api/dashboard/summary`
2. `GET /api/dashboard/plots`
3. `GET /api/dashboard/heatmap`
4. `GET /api/dashboard/disease-statistics`
5. `GET /api/dashboard/latest-records`
6. `GET /api/dashboard/latest-alerts`
7. `WS /ws/results`
8. `WS /ws/tasks`
9. `WS /ws/alerts`

联调说明：

- 地图点位来自识别记录中的 `lng/lat`，缺失时使用 `app/mocks/mock_plots.json`。
- `heatmap` 的 `color` 和 `intensity` 是展示建议，不是模型指标。
- 原图和结果图通过 `image_url`、`result_image_url` 拉取。
- WebSocket 只推 JSON。
- WebSocket 不推图片、base64 或视频帧。
- HTTP 查询接口是 WebSocket 失败时的兜底。

## 5. 移动端联调说明

移动端同学建议优先接：

1. `GET /api/mobile/overview`
2. `GET /api/mobile/plots`
3. `GET /api/mobile/plots/{plot_id}`
4. `GET /api/mobile/records/{record_id}`
5. `GET /api/mobile/alerts`
6. `GET /api/mobile/suggestions/{record_id}`
7. `POST /api/alerts/{alert_id}/resolve`
8. `WS /ws/alerts`
9. `WS /ws/results`

联调说明：

- 当前无真实用户登录。
- `user_id` 是预留参数。
- `my_plot_count` 暂按系统全部地块统计。
- 当前不做 JWT/RBAC 或真实权限过滤。
- 农事建议仅作为辅助参考。
- 不输出具体农药剂量。
- 图片仍通过 URL 拉取，不走 WebSocket。

## 6. 模型分支接入说明

模型训练分支后续需要交付：

- `uav_rice_disease_yolo` 权重路径。
- `phone_rice_disease_yolo` 权重路径。
- 类别映射 class map。
- 输入尺寸。
- 置信度阈值建议。
- 推理依赖说明。
- 验证指标报告。
- 典型成功/失败样例。

系统侧接入步骤：

1. 查看 `GET /api/models/status`。
2. 配置 UAV 模型路径和 Phone 模型路径。
3. 设置 `DETECTOR_MODE=real` 或 smoke 模式。
4. 确认路径存在。
5. 运行真实模型 smoke test。
6. 上传 `source_type=uav_rgb/uav_multispectral/phone_rgb` 图片。
7. 检查返回 `model_name/model_version/detector_mode`。
8. 检查 Mock 回退是否仍可用。

注意：

- v0.5 冻结基线只写接入说明，不实际接权重。
- `/api/models/status` 只做路径和配置检查。
- 当前默认仍是 Mock。
- 模型指标由模型训练分支提供，系统分支不伪造指标。

## 7. 演示启动步骤

```bash
cd agri_uav_disease_system/backend
python -m app.scripts.seed_demo_data --reset-demo-data
python -m app.scripts.system_smoke_test
python -m app.scripts.run_dev
```

启动后访问：

- `GET /healthz`
- `GET /api/status`
- `GET /api/dashboard/summary`
- `GET /api/mobile/overview`
- `GET /api/alerts`

可继续参考：

- `docs/demo_script.md`
- `docs/integration_examples/dashboard.http`
- `docs/integration_examples/mobile.http`
- `docs/integration_examples/websocket_examples.md`
- `docs/integration_examples/curl_examples.md`
- `docs/integration_examples/postman_collection.json`

## 8. 验收命令

```bash
python -m compileall app
python -m pytest app/tests -q
python -m app.scripts.system_smoke_test
```

当前已知结果：

```text
28 passed, 4 skipped
```

说明：

- skipped 是 smoke YOLO 条件测试。
- 默认 Mock 基线不受 skipped 影响。
- v0.5 冻结基线不要求真实 YOLO 权重可用。

## 9. 明确未做事项

- 未训练模型。
- 未接真实 YOLO。
- 未接真实无人机 SDK。
- 未接真实地图服务。
- 未做完整大屏。
- 未做完整移动端。
- 未接真实用户/JWT/RBAC。
- 未迁移 Celery/RQ。
- 未伪造 Precision/Recall/mAP。
- 未通过 WebSocket 传图片、base64 或视频帧。

## 10. 真实 YOLO 接入前检查清单

接入真实 YOLO 前，请确认：

- 已有明确模型类型：UAV 模型或 Phone 模型。
- 已有权重文件路径。
- 已有 class map。
- 已有输入尺寸和预处理要求。
- 已有置信度阈值建议。
- 已有推理依赖版本说明。
- 已有验证指标报告，且指标来自模型训练分支。
- 已有典型成功样例。
- 已有典型失败样例。
- 已确认 `source_type` 到模型的路由规则。
- 已确认真实模型失败时仍可回退 Mock。
- 已确认 WebSocket 仍只推 JSON。
- 已确认图片仍通过静态 URL 拉取。

## 11. 冻结建议

- 当前可以作为 `system-v0.5-mock-integration-baseline`。
- 后续新增真实模型接入应开独立分支。
- 大屏/移动端联调优先基于当前 API Contract。
- 不要在当前分支直接大改主链路。
- 大屏、移动端、模型训练分支可以基于此文档并行对接。
