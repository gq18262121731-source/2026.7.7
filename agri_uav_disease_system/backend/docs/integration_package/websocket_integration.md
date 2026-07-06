# WebSocket 联调说明

WebSocket 只推 JSON 事件，用于提示客户端“有新数据”。它不传图片、不传 base64、不传视频帧，也不保存历史数据。

统一环境变量：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

WebSocket 地址应由 `BASE_URL` 转换协议：

```text
https -> wss
http -> ws
```

## 1. 识别结果推送

### 接口

WS `/ws/results`

### 稳定性

`preview`

### 用途

通知大屏或主系统有新的识别结果。

### 事件示例

```json
{
  "event": "detection_result",
  "record_id": "rec_001",
  "plot_id": "plot_001",
  "risk_level": "medium",
  "timestamp": "2026-07-06T10:30:00"
}
```

### 客户端处理建议

收到事件后调用：

```http
GET /api/dashboard/latest-records
```

不要期待事件中携带完整图片或完整检测框。

## 2. 批处理任务推送

### 接口

WS `/ws/tasks`

### 稳定性

`preview`

### 用途

通知批量检测任务状态变化。

### 事件示例

```json
{
  "event": "task_status",
  "task_id": "batch_001",
  "status": "running",
  "processed_images": 4,
  "total_images": 10,
  "timestamp": "2026-07-06T10:31:00"
}
```

### 客户端处理建议

收到事件后调用：

```http
GET /api/tasks/{task_id}
```

客户端自己维护进度 UI，服务端事件只作为刷新触发器。

## 3. 告警推送

### 接口

WS `/ws/alerts`

### 稳定性

`preview`

### 用途

通知大屏或移动端有新告警。

### 事件示例

```json
{
  "event": "alert_created",
  "alert_id": "alert_001",
  "record_id": "rec_001",
  "risk_level": "high",
  "timestamp": "2026-07-06T10:32:00"
}
```

### 客户端处理建议

收到事件后调用：

```http
GET /api/dashboard/latest-alerts
```

移动端也可以调用：

```http
GET /api/mobile/alerts
```

## 心跳说明

客户端可发送文本心跳，例如：

```text
ping
```

服务端当前主要保持连接和推送事件，不要求客户端依赖心跳响应做业务判断。

## 断线重连

建议策略：

1. 断开后 1 秒重连。
2. 连续失败时指数退避到 30 秒。
3. 重连成功后立即通过 HTTP 补拉：
   - `/api/dashboard/latest-records`
   - `/api/dashboard/latest-alerts`
   - `/api/tasks/{task_id}`，如当前页面正在看某个任务。

## 禁止事项

- 不通过 WebSocket 上传图片。
- 不通过 WebSocket 传 base64。
- 不通过 WebSocket 传视频帧。
- 不依赖 WebSocket 保存历史记录。
- 不把事件内容当作完整业务详情。

## 失败处理建议

| 场景 | 处理 |
|---|---|
| 连接失败 | 显示“实时连接中断”，继续用 HTTP 轮询 |
| 多次重连失败 | 降级为 30 到 60 秒轮询 |
| 收到未知事件 | 忽略并记录日志 |
| 收到事件但补拉失败 | 展示错误态并保留旧数据 |
