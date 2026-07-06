# Tenth Round Backend UAV BLB Smoke Integration Report

Generated at: 2026-06-23 Asia/Shanghai

## 1. Scope

This round integrated the true UAV BLB smoke weight into the backend as an optional smoke detector route.

No training was started. No new weights were generated. No Precision, Recall, mAP, or F1 metrics were generated.

## 2. Modified Files

| File | Change |
|---|---|
| `app/core/config.py` | Added UAV BLB smoke settings: `UAV_BLB_MODEL_PATH`, `UAV_BLB_MODEL_NAME`, `UAV_BLB_MODEL_VERSION`, `ENABLE_UAV_BLB_SMOKE`, `UAV_BLB_SMOKE_CONFIDENCE`. |
| `app/api/detection_api.py` | Added optional form fields `model_hint` and `target_type`. |
| `app/schemas/upload.py` | Added request metadata fields `model_hint` and `target_type`. |
| `app/services/detection_service.py` | Passes `model_hint` and `target_type` into model routing and detector mode reporting. |
| `app/services/inference/model_manager.py` | Added three smoke route support: phone disease, UAV crop_object, UAV BLB disease, plus Mock fallback. |
| `app/services/inference/smoke_yolo_detector.py` | Added per-model version, confidence, category type, class code, and class metadata output. |
| `app/services/inference/mock_disease_detector.py` | Added route-aware Mock fallback metadata. |
| `app/schemas/detection_result.py` | Added optional detection item fields `class_name`, `category_type`, and `class_code`. |
| `app/schemas/status.py` | Extended model status schema with `uav_crop_model`, `uav_blb_model`, route metadata, and `active_routing`. |
| `app/api/status_api.py` | Extended `/api/models/status` to report phone, UAV crop, UAV BLB, and routing state. |
| `app/tests/test_smoke_yolo_backend_integration.py` | Added BLB explicit route, fallback, old UAV route, phone route, SQLite/result image, and WebSocket checks. |
| `.env.example` | Added BLB smoke environment variables. |
| `README.md` | Added Stage 10 BLB smoke route and boundary notes. |
| `docs/api_contract.md` | Documented `model_hint`, `target_type`, BLB response fields, and smoke boundaries. |

## 3. Weight Check

| Item | Result |
|---|---|
| BLB smoke weight path | `F:\学校\病虫害识别\ai_model_training\experiments\uav_blb_yolo\runs\smoke_uav_blb_baseline_v0_1\weights\best.pt` |
| Weight exists | yes |
| Backend loaded BLB smoke | yes |
| Model name | `uav_blb_disease_yolo` |
| Model version | `smoke_epoch1_blb_20260623` |
| Model stage | `smoke` |
| Formal metric available | `false` |

Loaded smoke status:

```json
{
  "phone_smoke_loaded": true,
  "uav_smoke_loaded": true,
  "uav_blb_smoke_loaded": true,
  "phone_fallback_to_mock": false,
  "uav_fallback_to_mock": false,
  "uav_blb_fallback_to_mock": false
}
```

## 4. API Routing Strategy

| Request | Selected detector | Target type |
|---|---|---|
| `source_type=phone_rgb` | `phone_rice_disease_yolo` | `disease` |
| `source_type=manual_upload` | `phone_rice_disease_yolo` | `disease` |
| UAV source without `model_hint` / `target_type` | `uav_rice_disease_yolo` | `crop_object` |
| UAV source with `model_hint=uav_blb` | `uav_blb_disease_yolo` | `disease` |
| UAV source with `target_type=disease` | `uav_blb_disease_yolo` | `disease` |
| Unknown source | `mock_disease_detector` | Mock fallback |

The old UAV `rice_panicle` crop-object route remains the default for UAV requests without explicit BLB hints.

## 5. `/api/models/status` Result

The status API returned HTTP 200 and included:

- `phone_model`: ready, smoke disease route.
- `uav_crop_model`: ready, smoke crop_object route.
- `uav_blb_model`: ready, smoke disease route.
- `active_routing`: explicit route map.
- `fallback_to_mock`: `false`.

The legacy `uav_model` field remains present as an alias of the UAV crop-object route for backward compatibility.

## 6. BLB Upload Self-Check

TestClient uploaded one BLB preview image with:

```text
source_type=uav_multispectral
model_hint=uav_blb
target_type=disease
```

Result:

| Item | Result |
|---|---|
| HTTP status | 200 |
| `model_name` | `uav_blb_disease_yolo` |
| `model_version` | `smoke_epoch1_blb_20260623` |
| `detector_mode` | `smoke` |
| `is_smoke` | `true` |
| `model_stage` | `smoke` |
| `formal_metric_available` | `false` |
| `current_target_type` | `disease` |
| `fallback_to_mock` | `false` |
| result image saved | yes |
| detections at standard threshold | 0 |

The 0-detection result is expected from the ninth-round smoke boundary and does not represent formal model quality.

## 7. Mock Fallback Test

The test suite temporarily pointed `UAV_BLB_MODEL_PATH` to a missing path and rebuilt the BLB detector.

Result:

- API still returned HTTP 200.
- `model_name` became `mock_disease_detector`.
- `fallback_to_mock` was `true`.
- `current_target_type` remained `disease`.
- Service startup was not blocked by the missing BLB smoke weight.

## 8. Compatibility Checks

| Check | Result |
|---|---|
| Old UAV crop_object route preserved | yes |
| `source_type=uav_rgb` without hints remains `uav_rice_disease_yolo` | yes |
| Phone route unaffected | yes |
| SQLite record query works | yes |
| Result image URL returns 200 | yes |
| WebSocket result event structure preserved | yes |
| Detection JSON includes optional class metadata when detections exist | yes |

## 9. Test Commands

Targeted smoke integration tests:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m pytest app/tests/test_smoke_yolo_backend_integration.py app/tests/test_status_api.py app/tests/test_detect_image.py app/tests/test_websocket_results.py -q
```

Result:

```text
15 passed in 16.47s
```

Full backend tests:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m pytest app/tests -q
```

Result:

```text
36 passed in 16.35s
```

Note: the default shell `python` pointed to an Anaconda base environment without FastAPI, so verification used the project virtual environment at `F:\学校\病虫害识别\.venv\Scripts\python.exe`.

## 10. Boundaries

| Item | Result |
|---|---|
| Started training | no |
| Generated new weights | no |
| Generated formal metrics | no |
| Replaced backend UAV crop_object weight | no |
| Connected real UAV SDK | no |
| Modified full frontend | no |

## 11. Current Limitations

- BLB smoke is a 1 epoch wiring artifact.
- BLB smoke used only 50 preview images in the previous training round.
- The image input is RGB JPG preview rendered from multispectral TIF data.
- This is not a formal multispectral multi-channel model.
- Standard-threshold inference may return 0 detections.
- Smoke metrics and smoke predictions must not be presented as formal disease recognition performance.

## 12. Next Round Suggestions

- Add frontend or API client controls for `model_hint` / `target_type`.
- Add an obvious smoke banner wherever BLB smoke output is displayed.
- Expand the BLB preview subset before any stronger smoke or pilot training.
- Research a formal multispectral multi-channel training and inference path.
- Keep `uav_rice_disease_yolo` crop_object and `uav_blb_disease_yolo` disease routes separate until formal model promotion.
