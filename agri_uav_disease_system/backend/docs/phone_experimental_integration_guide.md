# Phone Experimental Integration Guide

## Scope

This guide documents the optional backend route for the phone RiceLeafDiseaseBD 3 epoch experimental weight.

## Boundary

- Optional only; not the default phone route.
- Experimental only; not formal.
- No formal metrics are available.
- Healthy is excluded from disease detection classes.
- RiceLeafDiseaseBD conversion uses `source_directory_based_remap` because source class ids were not fully consistent with observed labels.
- Frontend clients must display an experimental warning.
- Frontend clients must not display formal metrics.
- Frontend clients must not show Healthy as a detection result.

## Route Selection

Use one of these explicit conditions:

- `source_type=phone_rgb` and `model_hint=phone_exp`
- `source_type=phone_rgb` and `model_stage_hint=experimental`
- `source_type=manual_upload` and `model_hint=phone_exp`
- `source_type=manual_upload` and `model_stage_hint=experimental`

Default `phone_rgb` or `manual_upload` requests still use the phone smoke/stable route.

## Model Fields

Experimental responses must include:

- `model_name=phone_rice_disease_yolo`
- `model_version=experimental_riceleafdiseasebd_3epoch_20260623`
- `model_stage=experimental`
- `is_smoke=false`
- `formal_metric_available=false`
- `current_target_type=disease`
- `category_type=disease`
- `model_capability_level=experimental_only`
- `fallback_to_mock=false` or `true` when the weight/dependency is unavailable

## Allowed Classes

- `brown_spot`
- `rice_blast`
- `leaf_smut`
- `tungro`
- `sheath_blight`

Forbidden detection classes:

- `Healthy`
- `healthy`
- `normal`
- `background`
- `unknown`
- `uncertain`

## Fallback

If the experimental weight or Ultralytics dependency is unavailable, the explicit experimental route returns Mock fallback with `fallback_to_mock=true`. It does not silently downgrade to phone smoke.
