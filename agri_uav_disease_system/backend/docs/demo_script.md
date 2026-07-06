# Demo Script

本文档用于给老师、队友或联调同学演示第五阶段后端能力。当前系统仍使用 `mock_disease_detector mock-v1`，不展示训练过程，不声明真实准确率、召回率或 mAP。

## 1. 启动后端

```bash
cd agri_uav_disease_system/backend
python -m app.scripts.run_dev
```

默认地址：

```text
http://127.0.0.1:8000
```

## 2. 准备演示数据

如果现场没有历史数据，可以生成演示数据：

```bash
python -m app.scripts.seed_demo_data
```

只清理第五阶段演示数据并重新生成：

```bash
python -m app.scripts.seed_demo_data --reset-demo-data
```

说明：seed 数据带 `demo_stage5_` 前缀，是演示数据，不代表真实模型指标。

## 3. 查看系统状态

打开：

```text
GET /api/status
GET /api/models/status
```

讲解点：

- 单图、批量、大屏、移动端、alert、WebSocket 能力均已暴露在 `capabilities` 中。
- `real_model_ready=false` 不代表系统异常，只代表尚未配置真实权重。
- `/api/models/status` 只检查配置和路径，不加载真实 YOLO。

## 4. 连接 WebSocket

可用 WebSocket 客户端分别连接：

```text
ws://127.0.0.1:8000/ws/results
ws://127.0.0.1:8000/ws/tasks
ws://127.0.0.1:8000/ws/alerts
```

讲解点：

- WebSocket 只推 JSON。
- 不通过 WebSocket 传图片、base64 或视频帧。
- 图片通过 `image_url` 和 `result_image_url` 访问。
- 客户端断线后应自动重连；HTTP 查询接口是兜底方式。

## 5. 上传单张图片

使用 `docs/integration_examples/mobile.http` 或 curl：

```bash
curl -X POST "http://127.0.0.1:8000/api/detect/image" \
  -F "file=@sample.jpg" \
  -F "plot_id=demo_plot" \
  -F "source_type=manual_upload"
```

查看返回的 `detection_result`：

- `record_id`
- `image_url`
- `result_image_url`
- `detections`
- `summary`
- `suggestion`
- `source_type`
- `model_name`
- `model_version`
- `detector_mode`

## 6. 查看结果图

复制返回中的：

```text
/static/original/xxx.jpg
/static/result/xxx_result.jpg
```

在浏览器中访问完整 URL：

```text
http://127.0.0.1:8000/static/original/xxx.jpg
http://127.0.0.1:8000/static/result/xxx_result.jpg
```

## 7. 查看大屏接口

依次打开：

```text
GET /api/dashboard/summary
GET /api/dashboard/plots
GET /api/dashboard/heatmap
GET /api/dashboard/disease-statistics
GET /api/dashboard/latest-records
GET /api/dashboard/latest-alerts
```

讲解点：

- 地块聚合按 SQLite 记录计算。
- 热力图颜色和强度只是展示建议，不是模型指标。
- 经纬度优先来自记录，缺失时使用 mock 地块数据。

## 8. 创建批量任务

使用 `POST /api/detect/batch` 上传多张图片。

随后查看：

```text
GET /api/tasks/{task_id}
```

并观察：

```text
ws://127.0.0.1:8000/ws/tasks
```

讲解点：

- 当前批量任务使用 FastAPI `BackgroundTasks`。
- 演示可用，但服务重启后任务恢复需要后续升级到持久化队列。

## 9. 查看移动端接口

```text
GET /api/mobile/overview?user_id=demo_user
GET /api/mobile/plots?user_id=demo_user
GET /api/mobile/plots/{plot_id}
GET /api/mobile/records/{record_id}
```

讲解点：

- 当前没有真实登录鉴权。
- `user_id` 是预留参数，目前不做权限过滤。

## 10. 查看和处理 Alert

```text
GET /api/alerts
GET /api/alerts/{alert_id}
POST /api/alerts/{alert_id}/resolve
GET /api/alerts/{alert_id}/actions
```

resolve body 示例：

```json
{
  "operator_id": "demo_user",
  "operator_name": "演示用户",
  "note": "已通知农技人员复核"
}
```

讲解点：

- `alert_actions` 是处理审计链骨架。
- 当前没有真实用户体系，operator 字段由调用方传入。
- 农事建议只做辅助参考，不输出具体农药剂量或强执行指令。

## 11. 收尾说明

当前系统分支负责接口、任务、存储、预警治理、大屏和移动端联动。模型训练分支独立负责真实权重和模型指标。后续接入真实 YOLO 时，可先通过 `/api/models/status` 检查权重路径，再替换 `RealDiseaseDetector` 适配逻辑。
