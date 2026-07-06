# Stage 3 Dashboard Linkage Acceptance

## Scope

This stage adds backend-only dashboard linkage APIs and minimal mock GIS data. It does not implement a full frontend, train models, connect real YOLO weights, connect real UAV SDKs, or use external map services.

## New / Enhanced Interfaces

- Enhanced `GET /api/dashboard/summary`
- New `GET /api/dashboard/plots`
- New `GET /api/dashboard/heatmap`
- New `GET /api/dashboard/disease-statistics`
- New `GET /api/dashboard/latest-records`
- New `GET /api/dashboard/latest-alerts`
- New `WS /ws/tasks`

Existing interfaces remain available:

- `POST /api/detect/image`
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`
- `GET /api/records`
- `WS /ws/results`

## Aggregation Rules

Plot aggregation:

- Group by `plot_id`.
- Missing `plot_id` is grouped as `unknown_plot`.
- Plot `risk_level` is the highest risk among records.
- `max_severity` is the highest severity among records.
- `main_disease` is the most frequent disease.
- Coordinates use latest record `lng/lat` first, then `app/mocks/mock_plots.json`.
- If no coordinates exist, heatmap skips that point.

Disease statistics:

- Aggregates by `summary.main_disease`.
- No-disease records are excluded from disease statistics.
- `ratio` is the disease count divided by disease-record count in this endpoint.

Heatmap:

- `normal`: intensity `0.1`, color `#22c55e`
- `low`: intensity `0.3`, color `#eab308`
- `medium`: intensity `0.6`, color `#f59e0b`
- `high`: intensity `1.0`, color `#ef4444`

These heatmap values are dashboard display suggestions, not model metrics.

## Mock GIS

Mock plot coordinates are stored in:

```text
app/mocks/mock_plots.json
```

The system does not depend on an external map API in this stage.

## WebSocket Task Progress

`/ws/tasks` broadcasts task progress events:

```json
{
  "type": "task_status",
  "task_id": "batch_20260622_001",
  "status": "processing",
  "total_images": 100,
  "processed_images": 12,
  "failed_images": 1,
  "progress": 0.12,
  "updated_at": "2026-06-22T10:05:00.000Z"
}
```

WebSocket pushes JSON only. It does not transmit images, base64 payloads, or video frames.

## Tests

Latest pytest result:

```text
19 passed
```

Covered:

- Dashboard summary empty shape.
- Dashboard summary with records.
- Plot aggregation.
- Heatmap points and mock coordinate fallback.
- Disease statistics.
- Latest records.
- Latest alerts.
- Batch task progress over `/ws/tasks`.

## Explicitly Not Done

- No model training.
- No real YOLO integration.
- No real UAV SDK integration.
- No real map service integration.
- No complete dashboard frontend.
- No model accuracy, recall, mAP, or latency claims.

## Next Stage Suggestions

1. Add plot detail API: `/api/dashboard/plots/{plot_id}`.
2. Add time-range filters for dashboard endpoints.
3. Add dashboard trend API by day/hour.
4. Add alert cooldown and batch-level plot risk aggregation.
5. Integrate real YOLO adapter when the model branch delivers weights and class mapping.
