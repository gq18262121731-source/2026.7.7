# Twenty-second Round: System Acceptance and Demo Runbook Report

## Objective

Create a system-level acceptance and demo runbook that summarizes the current backend model routes, demo wording, test coverage, and known limitations. No training, validation, or inference was run in this round.

## Read-Only Review Files

Training side:

- `ai_model_training/reports/fifteenth_round_b_uav_blb_experimental_model_registry_report.md`
- `ai_model_training/metadata/uav_blb_model_registry.yaml`
- `ai_model_training/reports/uav_blb_experimental_model_comparison.md`
- `ai_model_training/model_delivery/uav_blb_experimental_package/weights_manifest.json`
- `ai_model_training/reports/eighteenth_round_b_phone_riceleafdiseasebd_conversion_report.md`
- `ai_model_training/reports/nineteenth_round_b_phone_riceleafdiseasebd_experimental_train_report.md`
- `ai_model_training/metadata/phone_model_registry.yaml`
- `ai_model_training/reports/phone_riceleafdiseasebd_experimental_model_comparison.md`
- `ai_model_training/model_delivery/phone_riceleafdiseasebd_experimental_package/weights_manifest.json`
- `ai_model_training/reports/twentieth_round_b_phone_experimental_model_registry_report.md`

Backend side:

- `backend/reports/sixteenth_round_backend_uav_blb_experimental_optional_integration_report.md`
- `backend/reports/sixteenth_round_b_fix_pytest_environment_report.md`
- `backend/reports/twenty_first_round_backend_phone_experimental_optional_integration_report.md`
- `backend/docs/api_contract.md`
- `backend/docs/demo_model_status_guide.md`
- `backend/docs/uav_blb_experimental_integration_guide.md`
- `backend/docs/phone_experimental_integration_guide.md`
- `backend/docs/system_model_route_matrix.md`
- `backend/docs/system_demo_runbook.md`
- `backend/docs/demo_qa_answering_guide.md`
- `backend/docs/system_acceptance_summary.md`
- `backend/README.md`
- `backend/app/core/config.py`
- `backend/app/services/inference/model_manager.py`
- `backend/app/services/inference/model_display.py`
- `backend/app/api/status_api.py`
- `backend/app/tests/`

## Added / Updated Documents

- `backend/docs/system_model_route_matrix.md`
- `backend/docs/system_demo_runbook.md`
- `backend/docs/demo_qa_answering_guide.md`
- `backend/docs/system_acceptance_summary.md`
- `backend/README.md` top-level references

## Model Route Summary

### Phone

- Default phone route: `phone_rice_disease_yolo` smoke.
- Phone experimental route: `phone_rice_disease_yolo` experimental, selected only by `model_hint=phone_exp` or `model_stage_hint=experimental`.
- Phone experimental is not formal and uses `formal_metric_available=false`.

### UAV

- Default UAV route: `uav_rice_disease_yolo` smoke with `rice_panicle` crop_object target.
- UAV BLB smoke: `uav_blb_disease_yolo` smoke, selected by `model_hint=uav_blb` or `target_type=disease`.
- UAV BLB experimental: `uav_blb_disease_yolo` experimental, selected by `model_hint=uav_blb_exp` or `model_stage_hint=experimental`.

### Fallback

- Any unavailable route falls back to `mock_disease_detector`.
- Mock fallback is a safety route, not a real prediction.

## Demo Runbook Summary

The runbook now explains:

- How to verify health/status endpoints.
- How to call `POST /api/detect/image`.
- How to demonstrate phone smoke, phone experimental, UAV default, UAV BLB smoke, and UAV BLB experimental.
- How to explain smoke vs experimental vs formal.
- How to explain crop_object, Mock fallback, Healthy exclusion, and RGB preview renders.

## Q&A Summary

The Q&A guide now answers:

- Why the system is not formal yet.
- Why smoke and experimental routes exist.
- Why default UAV detection is rice panicle crop_object.
- Why UAV BLB experimental is not formal.
- Why phone experimental is not formal.
- Why Healthy is excluded.
- What happens when weights are missing.
- Why Mock fallback is retained.

## Acceptance Summary

The summary document now states:

- Dataset landing is complete.
- Phone expanded training is complete.
- UAV BLB expanded training is complete.
- Smoke and experimental routes are complete.
- Backend route matrix is complete.
- Demo safety wording is complete.
- WebSocket, SQLite history, dashboard/mobile protections, and pytest verification are complete.
- Formal validation and production-grade claims are still not complete.

## Tests Executed This Round

Command:

```powershell
C:\Users\13010\anaconda3\envs\torchgpu\python.exe -m pytest app/tests -q
```

Result:

```text
47 passed in 6.76s
```

Health checks:

- `GET /healthz` -> 200
- `GET /api/status` -> 200
- `GET /api/models/status` -> 200
- `GET /api/models/demo-safety` -> 200

## Non-Goals Confirmed

- Training: no
- validate: no
- infer_demo: no
- New weights: no
- New metrics: no
- Route logic changes: no
- Real `.env`: no
- Git add/commit: no

## Current Limitations

- Smoke and experimental routes are engineering-verification routes.
- Formal validation is still not available.
- Phone experimental still carries source class-id remapping risk.
- Crop_object must never be described as disease detection.
- Healthy must never be shown as a detection class.

## Next Step

If the project continues, the next logical improvement is a frontend/demo presentation pass that consumes these docs and keeps the smoke/experimental/formal wording visible to users.
