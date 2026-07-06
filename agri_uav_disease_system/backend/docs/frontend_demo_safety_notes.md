# Frontend Demo Safety Notes

Generated for twelfth round A: frontend, dashboard, mobile smoke display.

## Current Model Routes

| Route | Selection | Target type | Frontend wording |
|---|---|---|---|
| `phone_rice_disease_yolo` | `source_type=phone_rgb` or `manual_upload` | `disease` | 近距离水稻病害 smoke 模型；小样本 smoke，仅验证链路。 |
| `uav_rice_disease_yolo` | UAV source without `model_hint` and without `target_type=disease` | `crop_object` | UAV 稻穗辅助目标 smoke 模型；作物目标辅助检测，不是病害识别。 |
| `uav_blb_disease_yolo` | UAV source with `model_hint=uav_blb` or `target_type=disease` | `disease` | UAV 白叶枯病 smoke 模型；不代表正式 UAV 病害模型效果。 |
| `mock_disease_detector` | fallback/default | none or backend fallback target | Mock 兜底结果；模拟检测结果，仅用于联调和演示兜底。 |

## Page Display Rules

- Show `model_display_name`, `model_stage`, `model_warning`, `current_target_type`, `fallback_to_mock`, and `formal_metric_available` on result cards, history detail, mobile detail, and WebSocket pushed results.
- When `is_smoke=true`, show: `小样本 smoke，仅验证链路`.
- When `fallback_to_mock=true`, show: `Mock 兜底结果`.
- When `current_target_type=crop_object`, show: `作物目标辅助检测，不是病害识别`.
- When `model_name=uav_blb_disease_yolo`, show: `UAV 白叶枯病 smoke 模型`.
- When `formal_metric_available=false`, show: `暂无正式模型指标`.
- Dashboard disease statistics and disease alerts must remain disease-like only. `crop_object` records can appear in latest records as auxiliary target detections, but must not appear as disease ranking or pest/disease warning evidence.
- WebSocket clients must render the complete `detection_result` model metadata, not only `summary.main_disease`.

## Upload Selection Rules

- `source_type=phone_rgb` selects the phone near-range disease smoke route.
- `source_type=uav_rgb` or `uav_multispectral` without `model_hint` and without `target_type=disease` keeps the default UAV crop-object smoke route.
- `source_type=uav_multispectral` plus `model_hint=uav_blb` selects the UAV BLB disease smoke route.
- Any UAV source plus `target_type=disease` selects the UAV BLB disease smoke route.
- The page must state that smoke weights do not represent formal model quality.

## Forbidden Wording

- Do not say the formal model is complete.
- Do not present smoke metrics as formal Precision, Recall, mAP, or F1.
- Do not present `rice_panicle` or `crop_object` as disease detection.
- Do not present Mock fallback as real disease detection.
- Do not claim a real UAV SDK, production model, or production SLA is connected.

## Recommended Demo Script

1. Open `/static/frontend/smoke-demo.html`.
2. Show `/api/models/status` and `/api/models/demo-safety` cards: phone smoke, UAV crop-object smoke, UAV BLB smoke, and Mock fallback.
3. Upload a phone image with `source_type=phone_rgb` and explain that it is a near-range disease smoke route.
4. Upload a UAV image with `source_type=uav_rgb` or `uav_multispectral` and no hint; explain that this is rice panicle crop-object auxiliary detection, not disease recognition.
5. Upload a UAV image with `source_type=uav_multispectral` and `model_hint=uav_blb`; explain that this is the UAV BLB disease smoke route.
6. Point out that `formal_metric_available=false` and that no Precision, Recall, mAP, or F1 is shown as formal performance.
7. Show that WebSocket pushed results keep the same smoke/model labels as the HTTP response and history detail.

## Manual Self-check

1. Upload phone image: verify `model_display_name` is the phone disease smoke route and `current_target_type=disease`.
2. Upload UAV default image: verify `current_target_type=crop_object` and the page says auxiliary target detection, not disease recognition.
3. Upload UAV + `model_hint=uav_blb`: verify `model_name=uav_blb_disease_yolo` and the page says UAV BLB smoke model.
4. Verify all result cards show `model_stage`, `model_warning`, `fallback_to_mock`, and `formal_metric_available`.
5. Verify `crop_object` does not appear in disease statistics or latest disease alerts.
6. Force or observe Mock fallback: verify the page shows Mock fallback wording.
