# Demo Model Status Guide

This guide defines how to describe the current backend model routes during demos and API integration.

## Current Routes

| Route | How to select | Target type | Capability level | Demo wording |
|---|---|---|---|---|
| `phone_rice_disease_yolo` | `source_type=phone_rgb` or `manual_upload` | `disease` | `smoke_only` | Near-range rice disease smoke model. |
| `uav_rice_disease_yolo` | UAV source without `model_hint` or `target_type=disease` | `crop_object` | `auxiliary_smoke_only` | UAV rice panicle crop-object smoke model. |
| `uav_blb_disease_yolo` | UAV source with `model_hint=uav_blb` or `target_type=disease` | `disease` | `smoke_only` | UAV bacterial leaf blight smoke model. |
| `mock_disease_detector` | fallback/default | none | `mock_only` | Mock demo detector. |

## Terms

Smoke means a small-sample engineering run used to verify the API, SQLite, result image, dashboard/mobile, and WebSocket chain. It is not a formal model.

Mock means simulated detections used for fallback and system integration when a model or dependency is unavailable.

Crop object means an agricultural object class such as `rice_panicle`. It is not a disease or pest class.

Disease means a disease target such as `bacterial_leaf_blight`.

## Why Rice Panicle Is Not Disease Detection

The old UAV smoke route detects `rice_panicle`. It validates UAV image upload and YOLO wiring, but it does not detect disease symptoms. It must not be counted in disease statistics or shown as pest/disease warning evidence.

## Why BLB Smoke Is Not Formal

The BLB route uses a 1 epoch smoke weight trained on a small RGB preview subset derived from multispectral TIF data. It validates the UAV disease wiring path, but it is not a formal multi-channel multispectral model and has no formal production metrics.

## Frontend Display Rules

- Show a smoke banner when `is_smoke=true`.
- Show Mock fallback wording when `fallback_to_mock=true`.
- Do not label `current_target_type=crop_object` as disease detection.
- Show `model_warning` near any result produced by a smoke or mock route.
- Do not display Precision, Recall, mAP, or F1 as formal performance for smoke routes.
- Keep `uav_rice_disease_yolo` and `uav_blb_disease_yolo` visually distinct.

## Recommended Demo Wording

Current system wording:

> The system has completed an engineering chain from image upload, model inference adapter, result image generation, SQLite persistence, dashboard/mobile display, and WebSocket push. The connected model weights are smoke weights for validating the engineering workflow. Formal model performance still requires larger datasets and formal evaluation.

UAV BLB wording:

> The UAV BLB route is a smoke-only bacterial leaf blight integration path. It proves the backend can select and run a UAV disease weight, but it is not a formal UAV multispectral disease model.

UAV crop-object wording:

> The default UAV route currently detects rice panicle crop objects only. It is useful as an auxiliary crop-object smoke path and must not be described as disease detection.

## Forbidden Wording

- The system has completed formal UAV multispectral disease model training.
- Current mAP has reached a usable production level.
- UAV rice panicle detection is disease detection.
- Smoke weights represent production model capability.
- Mock detections are real disease detections.

## Optional UAV BLB Experimental 408 Route

The `experimental_408_epoch5` weight can be exposed only as an optional route. It is selected with `model_hint=uav_blb_exp` or `model_stage_hint=experimental` on UAV multispectral-like requests.

Display wording:

- Show "experimental, for verification only".
- Show `actual_samples=408` when displaying `preview_1000`.
- Show that the input is an RGB preview render derived from multispectral TIF data, not a true multi-channel multispectral model.
- Never show formal Precision, Recall, mAP, or F1 for this route.
- Keep the default UAV crop_object route and the BLB smoke route visually distinct.

Recommended UI label:

> UAV BLB experimental model, constrained-408 RGB preview, not formal.

Forbidden wording:

- Formal UAV BLB model.
- Production-ready multispectral disease detector.
- Full preview_1000 training result.
- Official model performance.

## Optional Phone RiceLeafDiseaseBD Experimental Route

The `phone_riceleafdiseasebd_exp_epoch3` weight can be exposed only as an optional route. It is selected with `model_hint=phone_exp` or `model_stage_hint=experimental` on `phone_rgb` or `manual_upload` requests.

Display wording:

- Show "experimental, for verification only".
- Show that Healthy is excluded from disease detection classes.
- Show the `source_directory_based_remap` data-risk note.
- Never show formal Precision, Recall, mAP, or F1 for this route.
- Keep the default phone smoke route visually distinct from the optional experimental route.

Recommended UI label:

> Phone RiceLeafDiseaseBD experimental model, 3 epoch, not formal.

Forbidden wording:

- Formal phone disease model.
- Production-ready rice disease detector.
- Official model performance.
- Healthy disease detection class.
