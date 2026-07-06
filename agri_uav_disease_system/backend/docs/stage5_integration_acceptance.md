# Stage 5 Integration Acceptance

第五阶段目标是把后端从“功能可用”推进到“可联调、可演示、可验收、可接真实模型”的工程状态。当前仍使用 `mock_disease_detector mock-v1`，不训练模型，不加载真实 YOLO，不接真实无人机 SDK，不接真实地图服务。

## 新增脚本

- `app/scripts/seed_demo_data.py`
- `app/scripts/system_smoke_test.py`

`seed_demo_data.py` 生成第五阶段演示数据：

- 至少 5 个 mock 地块。
- 至少 20 条识别记录。
- 覆盖 `normal`、`low`、`medium`、`high`。
- 覆盖至少 3 类病虫害。
- 生成原图和结果图占位图片。
- 生成或更新至少 3 条 alert。
- 数据带 `demo_stage5_` 前缀。
- 默认不覆盖用户已有 SQLite；只有 `--reset-demo-data` 会清理第五阶段演示数据。

`system_smoke_test.py` 验证：

- FastAPI app 可导入。
- SQLite 可连接。
- 静态目录可写。
- `/healthz`、`/api/status` 正常。
- 单图上传成功。
- 原图和结果图 URL 可访问。
- 记录详情、大屏 summary、移动端 overview 可查询。
- high 风险记录可生成 alert。
- `/api/alerts` 可查询。
- `/ws/results`、`/ws/tasks`、`/ws/alerts` 可连接。

## 新增和增强接口

新增：

- `GET /api/models/status`
- `GET /api/alerts/{alert_id}/actions`

增强：

- `GET /api/status` 增加 `capabilities`、`models`、`storage`。
- `POST /api/alerts/{alert_id}/resolve` 支持 `operator_id`、`operator_name`、`note`。
- `GET /api/mobile/overview` 支持预留参数 `user_id`。
- `GET /api/mobile/plots` 支持预留参数 `user_id`。

## `/api/status` 能力结构

示例：

```json
{
  "capabilities": {
    "single_image_detection": true,
    "batch_detection": true,
    "dashboard_api": true,
    "mobile_api": true,
    "alert_governance": true,
    "ws_results": true,
    "ws_tasks": true,
    "ws_alerts": true,
    "real_model_ready": false,
    "mock_mode": true
  },
  "models": {
    "detector_mode": "mock",
    "current_model": "mock_disease_detector",
    "uav_model_path_configured": false,
    "phone_model_path_configured": false
  },
  "storage": {
    "database_status": "ok",
    "static_original_writable": true,
    "static_result_writable": true
  }
}
```

## `/api/models/status`

只检查配置和路径，不加载真实 YOLO。

```json
{
  "detector_mode": "mock",
  "active_model_name": "mock_disease_detector",
  "active_model_version": "mock-v1",
  "uav_model": {
    "name": "uav_rice_disease_yolo",
    "path": null,
    "path_exists": false,
    "ready": false
  },
  "phone_model": {
    "name": "phone_rice_disease_yolo",
    "path": null,
    "path_exists": false,
    "ready": false
  },
  "fallback_to_mock": true
}
```

## Alert Actions

新增 `alert_actions` 表字段：

- `action_id`
- `alert_id`
- `action_type`
- `operator_id`
- `operator_name`
- `note`
- `created_at`

`action_type` 当前包括：

- `created`
- `updated`
- `upgraded`
- `resolved`
- 预留 `muted`

当前没有真实用户系统，`operator_id` 和 `operator_name` 由调用方传入，后续可接登录鉴权和审计链。

## 联调示例包

目录：

```text
docs/integration_examples/
```

包含：

- `dashboard.http`
- `mobile.http`
- `websocket_examples.md`
- `curl_examples.md`
- `postman_collection.json`

## 验证结果

当前自动化测试：

```text
python -m compileall app
python -m pytest app/tests -q
```

结果：

```text
28 passed
```

## 明确未做事项

- 未训练模型。
- 未安装或接入真实 YOLO。
- 未加载真实权重。
- 未接真实无人机 SDK。
- 未接真实地图服务。
- 未做完整大屏页面。
- 未做完整移动端页面。
- 未伪造 Precision、Recall、mAP。
- 未通过 WebSocket 传图片、base64 或视频帧。
- 未引入 JWT/RBAC。
- 未引入 Celery/RQ。

## 下一阶段建议

- 接入真实模型分支交付的权重，并通过 `/api/models/status` 做路径检查。
- 为地块归属接入真实用户体系和权限过滤。
- 将 `alert_actions` 扩展为完整处理闭环和审计链。
- 将批量任务从 `BackgroundTasks` 升级到持久化任务队列。
- 增加部署脚本、环境变量模板和生产日志策略。
