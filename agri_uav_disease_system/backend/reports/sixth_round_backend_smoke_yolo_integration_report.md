# Sixth Round Backend Smoke YOLO Integration Report

Date: 2026-06-23  
Scope: backend smoke integration only. No training, no new weights, no formal metrics.

## Modified Files

| File | Change |
| --- | --- |
| `app/core/config.py` | Added default smoke weight paths and `SMOKE_YOLO_CONFIDENCE`. |
| `app/core/constants.py` | Added `uav_ms` source type. |
| `app/schemas/detection_result.py` | Added smoke metadata fields while preserving existing `detection_result` structure. |
| `app/database/database.py` | Added SQLite columns for smoke metadata with migration-safe `_ensure_column`. |
| `app/database/repositories.py` | Persisted and restored smoke metadata. |
| `app/services/inference/disease_detector.py` | Added common detector metadata attributes. |
| `app/services/inference/smoke_yolo_detector.py` | Added Ultralytics smoke YOLO adapter. |
| `app/services/inference/model_manager.py` | Added source_type routing and Mock fallback. |
| `app/services/detection_service.py` | Included detector smoke metadata in API, SQLite, and WebSocket result payloads. |
| `app/tests/test_detect_image.py` | Relaxed old Mock-only assertions to support smoke-or-Mock mode. |
| `app/tests/test_smoke_yolo_backend_integration.py` | Added Stage 6 TestClient end-to-end checks. |
| `.env.example` | Documented smoke detector environment variables. |
| `README.md` | Added Stage 6 smoke boundary notes. |
| `docs/api_contract.md` | Added Stage 6 smoke response fields and source routing notes. |

## Smoke Weights

| Model | Path | Exists | Loaded |
| --- | --- | --- | --- |
| `phone_rice_disease_yolo` | `F:/学校/病虫害识别/ai_model_training/experiments/phone_rgb_yolo/runs/smoke_phone_rgb_baseline_v0_1/weights/best.pt` | yes | yes |
| `uav_rice_disease_yolo` | `F:/学校/病虫害识别/ai_model_training/experiments/uav_ms_yolo/runs/smoke_uav_ms_baseline_v0_1/weights/best.pt` | yes | yes |

Runtime smoke status:

```text
phone_smoke_loaded=True
uav_smoke_loaded=True
phone_fallback_to_mock=False
uav_fallback_to_mock=False
```

## Routing

| source_type | Detector |
| --- | --- |
| `phone_rgb` | `phone_rice_disease_yolo` smoke adapter |
| `manual_upload` | `phone_rice_disease_yolo` smoke adapter |
| `uav_rgb` | `uav_rice_disease_yolo` smoke adapter |
| `uav_ms` | `uav_rice_disease_yolo` smoke adapter |
| `uav_multispectral` | `uav_rice_disease_yolo` smoke adapter |
| `uav_video_frame` | `uav_rice_disease_yolo` smoke adapter |
| unknown/default | Mock/default detector |

If Ultralytics or a selected smoke weight is unavailable, `ModelManager` falls back to `MockDiseaseDetector`.

## API Self Check

Command:

```powershell
..\..\.venv\Scripts\python.exe -m pytest app\tests\test_smoke_yolo_backend_integration.py app\tests\test_detect_image.py app\tests\test_websocket_results.py app\tests\test_status_api.py -q
```

Result:

```text
11 passed in 14.52s
```

Covered checks:

- Phone image upload returned HTTP 200.
- UAV image upload returned HTTP 200.
- SQLite record query by `record_id` returned the saved detection result.
- Result image URL was generated and served successfully.
- WebSocket `/ws/results` event kept the existing structure and included smoke fields.
- Missing smoke weight path falls back to Mock.

## Response Fields

The existing `detection_result` response is preserved and now includes:

```json
{
  "is_smoke": true,
  "model_stage": "smoke",
  "model_version": "smoke_epoch1_20260623",
  "formal_metric_available": false,
  "current_target_type": "disease",
  "fallback_to_mock": false
}
```

For UAV smoke responses, `current_target_type` is `crop_object`. The UAV smoke adapter must not be described as a disease detector.

## Boundary

| Item | Result |
| --- | --- |
| Started training | no |
| Generated new weights | no |
| Generated formal metrics | no |
| Connected real UAV SDK | no |
| Built full frontend | no |
| Kept Mock detector | yes |
| Added smoke YOLO adapter | yes |
| Mock fallback available | yes |

## Current Risks

- Phone smoke weight is trained for only 1 epoch on a tiny sample and is not a formal model.
- UAV smoke weight detects `rice_panicle` crop objects only, not UAV disease or pest targets.
- Smoke metrics from the training project must not be shown as formal model performance.
- Backend smoke inference depends on Ultralytics and CPU inference latency can be slow.

## Next Round Suggestions

1. Add a backend-visible smoke banner or API field mapping on the frontend/API client side.
2. Keep production/demo environments defaulting to Mock unless smoke dependencies are explicitly installed.
3. Acquire real UAV disease data before any UAV disease model integration claim.
4. Add a formal model registry/version file before replacing smoke weights with formal weights.
5. Add API-level safeguards that prevent smoke models from being selected in production mode.

