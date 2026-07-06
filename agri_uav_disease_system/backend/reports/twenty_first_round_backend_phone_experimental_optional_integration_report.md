# Twenty-first Round B: Backend Phone Experimental Optional Integration Report

## Objective

Add an optional backend route for the phone RiceLeafDiseaseBD 3 epoch experimental YOLO weight. The route must be selected explicitly and must not replace the default phone smoke route.

## Modified Files

- `.env.example`
- `README.md`
- `docs/api_contract.md`
- `docs/demo_model_status_guide.md`
- `docs/phone_experimental_integration_guide.md`
- `app/core/config.py`
- `app/services/inference/model_manager.py`
- `app/services/inference/model_display.py`
- `app/schemas/status.py`
- `app/api/status_api.py`
- `app/tests/test_smoke_yolo_backend_integration.py`
- `app/tests/test_demo_safety_and_model_status.py`

## Phone Experimental Weight

- Path: `F:/学校/病虫害识别/ai_model_training/experiments/phone_rgb_yolo/runs/exp_phone_riceleafdiseasebd_v0_2_3epoch/weights/best.pt`
- Exists: true
- Size: 6,223,140 bytes
- Model name: `phone_rice_disease_yolo`
- Model version: `experimental_riceleafdiseasebd_3epoch_20260623`
- Stage: experimental
- Formal metric available: false

## Routing Strategy

Default routes remain unchanged:

- `phone_rgb` / `manual_upload` without hints: `phone_rice_disease_yolo` smoke
- UAV without hints: `uav_rice_disease_yolo` crop_object smoke
- UAV with `model_hint=uav_blb` or `target_type=disease`: UAV BLB smoke
- UAV with `model_hint=uav_blb_exp` or `model_stage_hint=experimental`: UAV BLB experimental

New explicit phone experimental route:

- `source_type=phone_rgb` or `manual_upload`
- plus `model_hint=phone_exp` or `model_stage_hint=experimental`

If the phone experimental weight is unavailable, the route falls back to Mock and returns `fallback_to_mock=true`. It does not silently downgrade to phone smoke.

## Response Fields

Phone experimental responses return:

- `model_name=phone_rice_disease_yolo`
- `model_version=experimental_riceleafdiseasebd_3epoch_20260623`
- `model_stage=experimental`
- `is_smoke=false`
- `formal_metric_available=false`
- `current_target_type=disease`
- `category_type=disease`
- `model_capability_level=experimental_only`
- `fallback_to_mock=false` when the experimental weight loads successfully

Allowed detection classes:

- `brown_spot`
- `rice_blast`
- `leaf_smut`
- `tungro`
- `sheath_blight`

Forbidden as disease detection classes:

- `Healthy`
- `healthy`
- `normal`
- `background`
- `unknown`
- `uncertain`

## `/api/models/status` Summary

`/api/models/status` now includes `phone_experimental_model` with:

- `model_stage=experimental`
- `is_smoke=false`
- `formal_metric_available=false`
- `current_target_type=disease`
- `class_codes=[brown_spot, rice_blast, leaf_smut, tungro, sheath_blight]`
- `source_types=[phone_rgb, manual_upload]`
- `route_condition=model_hint=phone_exp or model_stage_hint=experimental`
- `dataset_images=7575`
- `dataset_bbox=69769`
- `healthy_excluded=true`
- `class_mapping_strategy=source_directory_based_remap`

`active_routing` includes both the default phone smoke route and the explicit phone experimental route.

## `/api/models/demo-safety` Summary

Demo safety rules now include:

- phone experimental must show experimental-only wording
- formal metrics must not be displayed
- Healthy must not be displayed as a disease detection class
- `source_directory_based_remap` must be shown as a data-risk note
- Mock fallback must be shown when `fallback_to_mock=true`

## Self-check Results

- Local route/status self-check: passed
- `phone_experimental_model.ready`: true
- `phone_experimental_model.loaded`: true
- `phone_experimental_model.model_stage`: experimental
- active routing includes phone experimental: true
- demo-safety contains phone experimental rule: true

## Pytest Results

Command:

```powershell
C:\Users\13010\anaconda3\envs\torchgpu\python.exe -m pytest app/tests -q
```

Result:

```text
47 passed in 6.76s
```

## Non-goals Confirmed

- Training started: no
- Validation started: no
- infer_demo started: no
- New weights generated: no
- Formal metrics generated: no
- Real `.env` modified: no
- Backend default phone route changed: no
- Phone smoke weight overwritten: no
- Phone experimental weight overwritten: no
- Git add/commit: no

## Stability Checks

- phone smoke unaffected: covered by tests
- UAV crop_object smoke unaffected: covered by tests
- UAV BLB smoke unaffected: covered by tests
- UAV BLB experimental unaffected: covered by tests
- Mock fallback retained: covered by tests
- WebSocket phone experimental model fields: covered by tests

## Current Limitations

- Phone experimental is a 3 epoch experimental model, not formal.
- Existing metrics are experimental references only.
- RiceLeafDiseaseBD source class ids were not fully consistent with observed labels; the conversion uses `source_directory_based_remap`.
- Healthy is excluded and must not be shown as a disease detection class.
- The model covers only five phone RGB disease classes.

## Next Round Suggestions

1. If frontend work is approved, add a small experimental warning display for `model_stage=experimental`.
2. Keep default phone route unchanged unless a future formal model is produced and approved.
3. Continue RiceLeafDiseaseBD data cleaning and class-id consistency review.
4. Consider longer experimental runs only after documenting a stable validation protocol.
