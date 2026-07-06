# MVP Stage 1 Acceptance Report

## Implemented Interfaces

- `GET /healthz`
- `GET /api/status`
- `POST /api/detect/image`
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`
- `GET /api/records`
- `GET /api/records/{record_id}`
- `GET /api/dashboard/summary`
- `GET /api/mobile/alerts`
- `GET /api/mobile/suggestions/{record_id}`
- `WS /ws/results`
- `GET /static/original/{filename}`
- `GET /static/result/{filename}`

## Verified Interfaces

Verified by pytest and TestClient:

- Single image upload and detection.
- Record detail query.
- Paginated record list.
- Dashboard summary.
- Static original image access.
- Static result image access.
- WebSocket realtime `detection_result` push.
- `/api/status` model and service status.
- Invalid image, empty file, and unsupported extension return unified errors.
- Batch image task creation, progress query, success record ids, and failed image items.

## Mock Inference Chain

The system currently uses `MockDiseaseDetector` by default. It does not require real model weights.

Flow:

1. Save uploaded original image.
2. Verify image with Pillow.
3. Generate 0 to 2 mock detections from stable seed and image path.
4. Post-process detections.
5. Classify severity.
6. Evaluate risk level.
7. Generate agriculture suggestion.
8. Draw result image.
9. Save SQLite record.
10. Return unified `detection_result`.
11. Broadcast JSON to `/ws/results`.

No accuracy, recall, mAP, or latency target is fabricated in Stage 1.

## SQLite Fields

`detection_records` stores:

- `record_id`
- `image_id`
- `plot_id`
- `plot_name`
- `region_name`
- `timestamp`
- `image_url`
- `result_image_url`
- `image_width`
- `image_height`
- `source_type`
- `model_name`
- `model_version`
- `detector_mode`
- `lng`
- `lat`
- `detections_json`
- `severity`
- `risk_level`
- `main_disease`
- `suggestion_json`
- `created_at`

Existing MVP databases are upgraded by adding the new model metadata columns at startup.

## Static Resource Locations

Original images:

```text
app/static/original/
```

Result images:

```text
app/static/result/
```

Client-visible URLs:

```text
/static/original/{filename}
/static/result/{filename}
```

## WebSocket Test Result

The WebSocket test connects to `/ws/results`, uploads an image through `/api/detect/image`, receives a `detection_result`, checks required fields, and verifies that the connection pool is cleaned after disconnect.

## Pytest Result

Latest result:

```text
13 passed
```

## Explicitly Not Done

- No YOLO training.
- No real model weight loading is required.
- No real UAV SDK integration.
- No complete dashboard frontend.
- No complete mobile or HarmonyOS app.
- No base64 image/video transfer through WebSocket.
- No fabricated model metrics.

## Stage 2 Suggestions

1. Replace local `BackgroundTasks` with a queue abstraction if batch volume grows.
2. Add resumable batch task state and retry failed images.
3. Add batch-level plot aggregation and alert cooldown.
4. Implement real YOLO adapter behind `RealDiseaseDetector`.
5. Add separate model config for `uav_rice_disease_yolo` and `phone_rice_disease_yolo`.
6. Add dashboard heatmap and plot summary APIs.

## Later Stage Documents

The backend has progressed beyond the first-stage MVP:

- Stage 2 batch task acceptance details are covered by the batch API and tests.
- Stage 3 dashboard linkage details are documented in `docs/stage3_dashboard_acceptance.md`.

The system still does not train models, connect real YOLO weights, connect a real UAV SDK, or integrate a real GIS provider.
