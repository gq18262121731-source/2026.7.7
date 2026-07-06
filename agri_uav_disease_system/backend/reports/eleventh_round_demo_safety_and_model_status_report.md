# Eleventh Round Demo Safety and Model Status Report

Generated at: 2026-06-23 Asia/Shanghai

## 1. Modified Files

| File | Change |
|---|---|
| `app/schemas/detection_result.py` | Added `model_hint`, `target_type`, `model_display_name`, `model_warning`, `model_usage_scope`, and `model_capability_level`. |
| `app/services/inference/model_display.py` | Added centralized smoke/mock display registry and target-type helpers. |
| `app/services/detection_service.py` | Adds model display wording to every detection result. |
| `app/database/database.py` | Added SQLite columns for demo/model display fields. |
| `app/database/repositories.py` | Persists and restores demo/model display fields, with fallback wording for older records. |
| `app/schemas/status.py` | Expanded model status and added demo-safety schemas. |
| `app/api/status_api.py` | Expanded `/api/models/status` and added `/api/models/demo-safety`. |
| `app/schemas/dashboard.py` | Added smoke/model fields to latest record and alert items. |
| `app/services/dashboard/dashboard_service.py` | Excludes crop_object records from disease statistics and latest disease alerts. |
| `app/schemas/mobile.py` | Added smoke/model fields to mobile record detail. |
| `app/services/mobile/mobile_service.py` | Filters mobile alert records to disease-like targets only. |
| `app/services/alert_service.py` | Prevents crop_object records from generating pest/disease alerts. |
| `app/scripts/seed_demo_data.py` | Marks seeded disease demo records as `current_target_type=disease`. |
| `app/scripts/system_smoke_test.py` | Marks high-risk smoke alert fixture as `current_target_type=disease`. |
| `app/tests/test_demo_safety_and_model_status.py` | Added demo-safety, model status, warning, fallback, crop_object protection tests. |
| Existing tests | Updated hand-built disease fixtures with explicit `current_target_type=disease`. |
| `README.md` | Added Stage 11 demo-safety wording. |
| `docs/api_contract.md` | Documented demo-safety and model display fields. |
| `docs/demo_model_status_guide.md` | Added frontend/demo wording guide. |
| `docs/integration_examples/model_status.http` | Added status and smoke-route API examples. |

## 2. Current Model Routes

| Route | Selection | Target type | Capability level | Formal metric available |
|---|---|---|---|---|
| `phone_rice_disease_yolo` | `phone_rgb` / `manual_upload` | `disease` | `smoke_only` | false |
| `uav_rice_disease_yolo` | UAV source without BLB hint | `crop_object` | `auxiliary_smoke_only` | false |
| `uav_blb_disease_yolo` | UAV source with `model_hint=uav_blb` or `target_type=disease` | `disease` | `smoke_only` | false |
| `mock_disease_detector` | fallback/default | none | `mock_only` | false |

## 3. `/api/models/status` Summary

The endpoint now returns:

- `detector_mode`
- `active_routing`
- `fallback_to_mock`
- legacy `phone_model`, `uav_model`, `uav_crop_model`, `uav_blb_model`
- `mock_model`
- nested `models.phone_model`, `models.uav_crop_model`, `models.uav_blb_model`, `models.mock_model`
- `demo_safety`

Each model includes:

- `name`
- `display_name`
- `path`
- `path_exists`
- `ready`
- `loaded`
- `model_stage`
- `is_smoke`
- `formal_metric_available`
- `current_target_type`
- `class_codes`
- `source_types`
- `route_condition`
- `warning`
- `usage_scope`
- `capability_level`

## 4. Demo Safety API

Added:

```text
GET /api/models/demo-safety
```

It returns:

- `demo_safe: true`
- `has_smoke_models: true`
- `has_formal_models: false`
- `formal_metric_available: false`
- warnings explaining smoke/mock/crop_object limits
- display rules for frontend/demo pages

## 5. Detection Result Field Stability

`detection_result` now preserves:

- `is_smoke`
- `model_stage`
- `formal_metric_available`
- `current_target_type`
- `fallback_to_mock`
- `model_name`
- `model_version`
- `detector_mode`
- `source_type`
- `model_hint`
- `target_type`
- `model_display_name`
- `model_warning`
- `model_usage_scope`
- `model_capability_level`

These fields are preserved through:

- `POST /api/detect/image`
- `GET /api/records/{record_id}`
- `GET /api/records`
- `GET /api/dashboard/latest-records`
- `GET /api/mobile/records/{record_id}`
- `WS /ws/results`

## 6. Dashboard / Mobile / Alert Protection

| Protection | Result |
|---|---|
| `crop_object` excluded from `disease-statistics` | yes |
| `crop_object` excluded from latest disease alerts | yes |
| `crop_object` does not generate pest/disease alerts | yes |
| Mobile alert list filters to disease-like targets | yes |
| Disease-like targets allowed for alerts | `disease`, `pest`, `pest_damage` |
| Mock fallback labelled through model warning fields | yes |
| Suggestion disclaimer preserved | yes |

## 7. WebSocket

`WS /ws/results` broadcasts the full `DetectionResult`, so smoke/model display fields are preserved.

## 8. Documentation

Updated:

- `README.md`
- `docs/api_contract.md`
- `docs/demo_model_status_guide.md`
- `docs/integration_examples/model_status.http`

## 9. Tests

Command:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m pytest app/tests -q
```

Result:

```text
40 passed in 16.72s
```

## 10. Boundaries

| Item | Result |
|---|---|
| Started training | no |
| Generated new weights | no |
| Generated formal metrics | no |
| Replaced smoke weights | no |
| Removed Mock | no |
| Modified training datasets | no |
| Connected real UAV SDK | no |
| Full frontend rewrite | no |

## 11. Current Limitations

- All connected YOLO weights are still smoke-only.
- UAV `rice_panicle` remains a crop-object auxiliary route, not a disease route.
- UAV BLB remains a 1 epoch smoke route, not a formal multispectral model.
- Mock output remains simulated and must be labelled as fallback/demo output.
- Formal model performance still requires larger datasets and formal evaluation.

## 12. Next Round Suggestions

- Add frontend banners for `model_warning`.
- Add UI controls for `model_hint` and `target_type`.
- Add dashboard chips for `smoke_only`, `auxiliary_smoke_only`, and `mock_only`.
- Keep formal metrics hidden until a formal training/evaluation round exists.
- Consider adding explicit `main_target` in a future API version to reduce reliance on legacy `main_disease` naming.
