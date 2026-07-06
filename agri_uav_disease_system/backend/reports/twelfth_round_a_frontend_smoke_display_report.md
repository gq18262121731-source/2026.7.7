# Twelfth Round A Frontend Smoke Display Report

Generated at: 2026-06-23 Asia/Shanghai

## 1. Modified Files

| File | Change |
|---|---|
| `app/static/frontend/smoke-demo.html` | Added an in-backend static frontend page for dashboard/debug/mobile smoke display. It reads model status, demo-safety, records, dashboard statistics, mobile record detail, and `/ws/results`. |
| `docs/frontend_demo_safety_notes.md` | Added frontend smoke display rules, forbidden wording, upload route rules, demo script, and manual self-check steps. |
| `reports/twelfth_round_a_frontend_smoke_display_report.md` | Added this implementation and verification report. |

No training files, datasets, weights, or model metric artifacts were modified.

## 2. Pages Showing Smoke Labels

The new page is served by the existing FastAPI static mount:

```text
/static/frontend/smoke-demo.html
```

It includes:

- model status / debug panel;
- upload test entry;
- dashboard disease statistics and latest alert protection view;
- detection result card and history detail;
- mobile detail preview;
- WebSocket latest-result panel.

Every result-oriented area displays:

- `model_display_name`
- `model_stage`
- `model_warning`
- `current_target_type`
- `fallback_to_mock`
- `formal_metric_available`

## 3. `/api/models/status`

Connected: yes.

The page calls:

```text
GET /api/models/status
```

It displays:

- current routing;
- phone smoke model;
- UAV crop_object smoke model;
- UAV BLB disease smoke model;
- Mock fallback model;
- model stage;
- current target type;
- loaded/ready/fallback state;
- `formal_metric_available=false`;
- smoke/mock warnings.

## 4. `/api/models/demo-safety`

Connected: yes.

The page calls:

```text
GET /api/models/demo-safety
```

It displays:

- `has_smoke_models`;
- `has_formal_models=false`;
- `formal_metric_available=false`;
- warning text;
- frontend display rules.

## 5. phone / UAV crop / UAV BLB / Mock Display

| Route | Display effect |
|---|---|
| phone smoke | Shows `近距离水稻病害 smoke 模型`, `小样本 smoke，仅验证链路`, `current_target_type=disease`, and `暂无正式模型指标`. |
| UAV crop_object smoke | Shows `UAV 稻穗辅助目标 smoke 模型`, `辅助目标检测`, `作物目标辅助检测，不是病害识别`, and `current_target_type=crop_object`. |
| UAV BLB disease smoke | Shows `UAV 白叶枯病 smoke 模型`, `current_target_type=disease`, and smoke warning wording. |
| Mock fallback | Shows `Mock 演示检测器`, `Mock 兜底结果`, and simulated/fallback wording. |

The upload form exposes:

- `source_type`: `phone_rgb`, `uav_rgb`, `uav_multispectral`;
- `model_hint`: empty or `uav_blb`;
- `target_type`: empty or `disease`.

The page wording states that smoke weights do not represent formal model quality.

## 6. crop_object Protection

Still protected: yes.

The backend eleventh-round rules remain unchanged:

- `crop_object` is excluded from disease statistics;
- `crop_object` does not generate pest/disease alerts;
- latest records can show `crop_object`, but the page labels them as `辅助目标检测`;
- result detail replaces disease wording for `crop_object` with `辅助目标，不作为病害展示`.

The frontend disease-statistics table explicitly states that `crop_object` does not enter the disease ranking when the list is empty.

## 7. WebSocket

Preserved model fields: yes.

The page connects to:

```text
WS /ws/results
```

When a new result arrives, it displays:

- `model_display_name`;
- `model_stage`;
- `current_target_type`;
- `fallback_to_mock`;
- `formal_metric_available`;
- `model_warning`;
- `model_name`;
- `model_version`;
- `model_hint`;
- `target_type`;
- `is_smoke`.

The WebSocket panel does not reduce the result to only `summary.main_disease`.

## 8. Training / Weights / Metrics Boundary

| Item | Result |
|---|---|
| Started training | no |
| Generated new weights | no |
| Replaced backend model weights | no |
| Modified training dataset | no |
| Generated Precision/Recall/mAP/F1 | no |
| Connected real UAV SDK | no |
| Presented smoke as formal model | no |
| Presented UAV `rice_panicle` crop_object as disease recognition | no |

## 9. Verification

Static content check:

```text
rg -n "api/models/status|api/models/demo-safety|ws/results|model_display_name|current_target_type|formal_metric_available|Mock 兜底结果|作物目标辅助检测|UAV 白叶枯病 smoke" app/static/frontend/smoke-demo.html docs/frontend_demo_safety_notes.md
```

Result: required API calls and display wording are present.

Backend tests:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m pytest app/tests -q
```

Result:

```text
40 passed in 16.72s
```

## 10. Manual Self-check Steps

1. Open `/static/frontend/smoke-demo.html`.
2. Upload a phone image with `source_type=phone_rgb`; verify phone smoke disease wording.
3. Upload a UAV image with `source_type=uav_rgb` or `uav_multispectral` and empty hint/target; verify auxiliary crop_object wording.
4. Upload a UAV image with `source_type=uav_multispectral` and `model_hint=uav_blb`; verify UAV BLB disease smoke wording.
5. Verify `crop_object` records do not appear in the disease statistics ranking or latest pest/disease alerts.
6. Force or observe Mock fallback; verify `Mock 兜底结果` is shown.
7. Keep the page open during upload; verify `/ws/results` shows the same smoke/model fields as the HTTP result.

## 11. Next Round Suggestions

- If a separate Vue/React frontend is added later, extract the display rules from `smoke-demo.html` into shared UI helpers.
- Add automated browser smoke checks for the static page once a frontend test runner is introduced.
- Add a small `/api/frontend/demo-fixtures` endpoint only if the demo needs deterministic records without uploading images.
- Keep formal model metrics hidden until a formal training and evaluation round produces validated artifacts.
