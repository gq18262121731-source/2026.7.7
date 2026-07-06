# WebSocket Examples

Base URLs:

```text
wss://test-api.example.com
本机开发说明：ws://127.0.0.1:8000
```

## `/ws/results`

Receives `detection_result` JSON after `POST /api/detect/image` finishes.

```json
{
  "type": "detection_result",
  "record_id": "rec_001",
  "image_url": "/static/original/xxx.jpg",
  "result_image_url": "/static/result/xxx_result.jpg",
  "detections": [],
  "summary": {},
  "suggestion": {}
}
```

## `/ws/tasks`

Receives batch task progress JSON.

```json
{
  "type": "task_status",
  "task_id": "batch_001",
  "status": "processing",
  "total_images": 20,
  "processed_images": 5,
  "failed_images": 0,
  "progress": 0.25,
  "updated_at": "2026-06-22T10:05:00.000Z"
}
```

## `/ws/alerts`

Receives alert events when medium/high risk records create or update alerts.

```json
{
  "type": "alert_event",
  "alert_id": "alert_001",
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

## Rules

- WebSocket only pushes structured JSON.
- WebSocket does not push images, base64 strings, or video frames.
- Clients should fetch images through `image_url` and `result_image_url`.
- Clients should reconnect automatically after disconnection.
- Suggested reconnect backoff: 3s, 5s, 10s, then 30s.
- After reconnecting, clients should pull the latest data through HTTP because WebSocket events are not replayed.
- HTTP APIs are the fallback query path:
  - `GET /api/records/{record_id}`
  - `GET /api/tasks/{task_id}`
  - `GET /api/alerts/{alert_id}`
  - `GET /api/dashboard/latest-records?limit=10`
  - `GET /api/dashboard/latest-alerts?limit=10`

## Auth

If the deployment requires token auth, connect with the token using the channel supported by the WebSocket client and gateway, for example:

```text
wss://test-api.example.com/ws/results?token=<TOKEN>
```

or through an `Authorization: Bearer <TOKEN>` header if the client library supports custom headers. The exact production policy should be confirmed by the gateway/backend owner.
