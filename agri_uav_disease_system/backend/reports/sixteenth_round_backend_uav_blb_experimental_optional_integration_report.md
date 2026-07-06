# Sixteenth Round B - Backend Optional UAV BLB 408 Experimental Integration Report

Generated: 2026-06-23

## Objective

Add an optional backend route for the UAV BLB constrained-408 experimental YOLO weight without replacing existing smoke, crop_object, phone, or Mock fallback behavior.

## Modified Files

- app/core/config.py
- app/services/inference/smoke_yolo_detector.py
- app/services/inference/model_display.py
- app/services/inference/model_manager.py
- app/schemas/upload.py
- app/api/detection_api.py
- app/schemas/detection_result.py
- app/services/detection_service.py
- app/schemas/status.py
- app/api/status_api.py
- .env.example
- app/tests/test_smoke_yolo_backend_integration.py
- app/tests/test_demo_safety_and_model_status.py
- README.md
- docs/api_contract.md
- docs/demo_model_status_guide.md
- docs/uav_blb_experimental_integration_guide.md
- reports/sixteenth_round_backend_uav_blb_experimental_optional_integration_report.md

## Experimental Weight

Path:
`F:/学校/病虫害识别/ai_model_training/experiments/uav_blb_yolo/runs/exp_uav_blb_preview408_v0_1_5epoch/weights/best.pt`

Exists: true.

Loaded successfully in smoke/auto backend mode when ultralytics is available: covered by pytest status and explicit detection tests.

## Routing Strategy

- `phone_rgb` and `manual_upload`: keep `phone_rice_disease_yolo` smoke route.
- UAV source without hints: keep `uav_rice_disease_yolo` crop_object smoke route.
- UAV source with `model_hint=uav_blb` or `target_type=disease`: keep UAV BLB smoke route.
- UAV source with `model_hint=uav_blb_exp` or `model_stage_hint=experimental`: use UAV BLB 408 experimental route.
- If the experimental route is unavailable, fallback is Mock with `fallback_to_mock=true`; it does not silently downgrade to smoke.

## API Status Summary

`/api/models/status` now exposes `uav_blb_experimental_model` with:

- `model_stage=experimental`
- `is_smoke=false`
- `formal_metric_available=false`
- `current_target_type=disease`
- `capability_level=experimental_only`
- `dataset_actual_images=408`
- `dataset_target_name=preview_1000`
- `is_true_multichannel_model=false`

## Demo Safety Summary

`/api/models/demo-safety` includes display rules for experimental-only wording, actual sample count, RGB preview boundary, crop_object protection, Mock fallback, and no formal metrics.

## Self-check Targets

- `detect/image` experimental explicit request returns 200 and experimental fields.
- Missing experimental weight request returns 200 through Mock fallback.
- Smoke BLB route remains smoke.
- UAV default crop_object route remains crop_object.
- Phone route remains phone smoke.
- WebSocket result event preserves experimental fields.

## Boundaries

- Training: no.
- Validation: no.
- Inference script execution: no.
- New weights generated: no.
- Formal metrics generated: no.
- Real `.env` modified: no.
- Smoke BLB weight overwritten: no.
- 300/408 experimental weights overwritten: no.
- Backend default UAV route changed: no.
- Git add/commit: no.

## Current Limitations

- The 408 model is experimental only.
- It is an RGB preview render model, not a true multi-channel multispectral model.
- It is single-class `bacterial_leaf_blight` only.
- Formal metrics are unavailable.
- Frontend must display experimental warning if it exposes the route.

## Next Round Suggestions

- Run a frontend smoke display update only if explicitly requested.
- Add a UI selector for `model_hint=uav_blb_exp` with an experimental warning.
- Continue data expansion and true multi-channel multispectral research before formal training.

## Executed Self-check Result

`python -m pytest app/tests -q` was attempted with base Python, but collection failed because that environment lacks `fastapi` and `pydantic`.

Existing conda environments were checked without installing new packages:

- `torchgpu`: has FastAPI/Pydantic/Pillow/Ultralytics, but lacks pytest and httpx.
- `vision311`: has FastAPI/Pydantic/Pillow/Ultralytics, but lacks pytest and httpx.
- `base`: has pytest, but lacks FastAPI/Pydantic/Ultralytics.

Because no existing environment contains both pytest/TestClient dependencies and backend runtime dependencies, full pytest could not complete without installing packages.

Direct backend service self-check was executed with `torchgpu` and passed:

- Explicit experimental request selected `uav_blb_disease_yolo`.
- `model_version=experimental_preview408_epoch5_20260623`.
- `detector_mode=experimental`.
- `model_stage=experimental`.
- `is_smoke=false`.
- `formal_metric_available=false`.
- `current_target_type=disease`.
- `category_type=disease`.
- `model_capability_level=experimental_only`.
- `fallback_to_mock=false`.
- Result image was generated.
- `/api/models/status` builder includes `uav_blb_experimental_model` and marks it ready.
- `/api/models/demo-safety` builder includes experimental display rules.
- Phone smoke route remained phone smoke.
- Default UAV route remained crop_object smoke.
- UAV BLB smoke route remained smoke.
- Missing experimental weight fell back to Mock with `fallback_to_mock=true`.

## Sixteenth Round B-Fix Pytest Completion Update

The previous blocker was the backend pytest environment, not a business assertion failure.

Selected environment:
`C:\Users\13010\anaconda3\envs\torchgpu\python.exe`

Installed/filled test dependencies in `torchgpu`:

- pytest
- httpx
- sqlalchemy

Dependency check after fix:

- fastapi 0.136.1
- pydantic 2.13.4
- pytest 9.1.1
- httpx 0.28.1
- ultralytics 8.4.52
- pillow 12.2.0
- numpy 2.4.4
- opencv-python/cv2 4.13.0
- sqlalchemy 2.0.51

Full pytest command:

```powershell
& 'C:\Users\13010\anaconda3\envs\torchgpu\python.exe' -m pytest app/tests -q
```

Final pytest result:

```text
42 passed in 9.19s
```

Status: completed.

Boundary confirmation:

- Training: no.
- Validation: no.
- infer_demo: no.
- New weights generated: no.
- Formal metrics generated: no.
- Real `.env` modified: no.
- Default UAV route changed: no.
- Experimental route remains explicit only.
- Mock fallback remains available.
