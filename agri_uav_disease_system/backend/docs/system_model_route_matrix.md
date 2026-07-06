# System Model Route Matrix

## Phone

| Route | source_type | model_hint | model_stage_hint | Model | Stage | target_type | formal_metric_available | usage | warning |
|---|---|---|---|---|---|---|---|---|---|
| Phone default | `phone_rgb` / `manual_upload` | none | none | `phone_rice_disease_yolo` smoke | smoke | disease | false | Near-range smoke wiring verification | Smoke only; not formal performance |
| Phone experimental | `phone_rgb` / `manual_upload` | `phone_exp` | `experimental` | `phone_rice_disease_yolo` experimental | experimental | disease | false | Phone RiceLeafDiseaseBD 3 epoch experimental | Experimental only; Healthy excluded; source_directory_based_remap risk note |

## UAV

| Route | source_type | model_hint | model_stage_hint | Model | Stage | target_type | formal_metric_available | usage | warning |
|---|---|---|---|---|---|---|---|---|---|
| UAV default | `uav_rgb` / `uav_ms` / `uav_multispectral` / `uav_video_frame` | none | none | `uav_rice_disease_yolo` smoke | smoke | crop_object | false | UAV crop-object wiring verification | Crop object only; not disease detection |
| UAV BLB smoke | `uav_rgb` / `uav_ms` / `uav_multispectral` | `uav_blb` | none | `uav_blb_disease_yolo` smoke | smoke | disease | false | True UAV BLB disease smoke | 1 epoch smoke only; not formal |
| UAV BLB experimental | `uav_rgb` / `uav_ms` / `uav_multispectral` | `uav_blb_exp` | `experimental` | `uav_blb_disease_yolo` experimental | experimental | disease | false | UAV BLB 408 experimental | 408 RGB preview experimental; not true multispectral formal model |

## Fallback

| Trigger | Model | Stage | target_type | formal_metric_available | usage | warning |
|---|---|---|---|---|---|---|
| Missing weight or dependency | `mock_disease_detector` | mock | none | false | API safety and integration fallback | Mock fallback result; not a real model prediction |

## Notes

- Smoke = engineering verification only.
- Experimental = explicit verification only.
- Formal = not yet available in this project.
- `crop_object` must never be described as disease detection.
- Healthy must never be returned as a detection class.
