# System Demo Runbook

## Before Demo

1. Confirm Python environment is the same one used for backend tests.
2. Start the backend service with the normal dev launch command.
3. Keep `.env.example` separate from the real `.env`.
4. Check model paths in `/api/models/status` rather than assuming a weight is loaded.
5. Confirm the static result directory is writable.
6. Keep a sample image ready for each route you want to show.

## Health Checks

Run these first:

- `GET /healthz`
- `GET /api/status`
- `GET /api/models/status`
- `GET /api/models/demo-safety`

Expected:

- HTTP 200 on all four endpoints.
- Status payload shows smoke/experimental/model path fields.
- Demo safety payload shows warning text and display rules.

## Upload API

Use `POST /api/detect/image` with:

- `file`
- `source_type`
- `model_hint`
- `model_stage_hint`
- `target_type`
- `plot_id`
- `plot_name`

## Recommended Demo Order

1. Show `/api/models/status`.
2. Show `/api/models/demo-safety`.
3. Show phone default smoke.
4. Show phone experimental.
5. Show UAV default crop_object smoke.
6. Show UAV BLB smoke.
7. Show UAV BLB experimental.
8. Show one historical record from SQLite.
9. Show WebSocket result events.
10. Show Mock fallback by temporarily hiding a weight path only in a test or dry environment.

## Expected Route Behavior

### Phone default

- `source_type=phone_rgb`
- `model_hint` omitted
- `model_stage_hint` omitted
- Model: phone smoke
- Stage: smoke
- target_type: disease
- formal_metric_available: false
- warning: smoke-only wiring verification

### Phone experimental

- `source_type=phone_rgb` or `manual_upload`
- `model_hint=phone_exp` or `model_stage_hint=experimental`
- Model: phone RiceLeafDiseaseBD 3 epoch experimental
- Stage: experimental
- target_type: disease
- formal_metric_available: false
- warning: experimental-only, Healthy excluded, source_directory_based_remap risk note

### UAV default

- `source_type=uav_rgb` / `uav_ms` / `uav_multispectral` / `uav_video_frame`
- Model: rice_panicle crop_object smoke
- Stage: smoke
- target_type: crop_object
- formal_metric_available: false
- warning: crop_object only, not disease detection

### UAV BLB smoke

- `model_hint=uav_blb` or `target_type=disease`
- Model: UAV BLB smoke
- Stage: smoke
- target_type: disease
- formal_metric_available: false
- warning: smoke-only, not formal

### UAV BLB experimental

- `model_hint=uav_blb_exp` or `model_stage_hint=experimental`
- Model: UAV BLB 408 experimental
- Stage: experimental
- target_type: disease
- formal_metric_available: false
- warning: experimental-only, RGB preview render derived from multispectral TIF, not true multispectral formal model

## How To Explain Smoke / Experimental / Formal

- Smoke: engineering chain verification, small sample, not formal.
- Experimental: explicit verification path, not formal, metrics are reference only.
- Formal: not available yet; do not claim it.

## How To Explain Crop Object

- `crop_object` means an agricultural object class such as `rice_panicle`.
- It is not disease detection.
- Do not include it in disease statistics or disease warnings.

## How To Explain Mock Fallback

- Mock fallback is a safety route when weights or dependencies are unavailable.
- It protects API availability and keeps the demo runnable.
- It is not a real model prediction.

## Closing Line For Demo

The system now demonstrates image upload, route selection, inference adapter wiring, result rendering, SQLite persistence, dashboard/mobile/status APIs, WebSocket push, smoke routes, experimental routes, and safe Mock fallback, but it still does not provide formal agricultural diagnosis.
