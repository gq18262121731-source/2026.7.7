# UAV BLB Experimental Integration Guide

This guide describes the optional backend route for the UAV BLB constrained-408 experimental weight.

## Boundary

- Optional only; not a default model.
- Experimental only; not formal.
- No formal metrics are available.
- Uses RGB preview renders derived from multispectral TIF data.
- Not a true multi-channel multispectral model.
- `preview_1000` is the dataset target name; actual samples are 408.

## Route Selection

Use one of the explicit selectors on UAV multispectral-like requests:

- `model_hint=uav_blb_exp`
- `model_stage_hint=experimental`
- `model_hint=uav_blb` plus `model_stage_hint=experimental`

Default UAV requests continue to use the rice_panicle crop_object smoke route.

## Response Contract

The experimental route must return:

- `model_stage=experimental`
- `is_smoke=false`
- `formal_metric_available=false`
- `current_target_type=disease`
- `category_type=disease`
- `model_capability_level=experimental_only`
- `fallback_to_mock=false` when the weight loads, or `true` when falling back to Mock

## Fallback Policy

If the experimental weight or dependency is unavailable, the explicit experimental route falls back to Mock and marks `fallback_to_mock=true`. It does not silently downgrade to the BLB smoke model.

## Frontend Display Rules

- Show the experimental warning.
- Do not show formal metrics.
- Show actual samples as 408.
- Do not describe RGB preview as true multi-channel multispectral inference.
- Do not describe crop_object output as disease detection.
