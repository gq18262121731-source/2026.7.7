# Twelfth Round A Frontend Smoke Display Hotfix 2 Report

Generated at: 2026-06-23 Asia/Shanghai

## 1. Fixed Issue

This hotfix corrects a display wording problem where old Mock records could still show the `病害识别` badge when their stored `current_target_type` was `disease`.

The page now treats Mock as the first display priority.

## 2. Modified Files

| File | Change |
|---|---|
| `app/static/frontend/smoke-demo.html` | Added favicon data URL, Mock-first display normalization, Mock badge early return, and short-window duplicate page-log suppression. |
| `reports/twelfth_round_a_frontend_smoke_display_hotfix2_report.md` | Added this hotfix report. |

## 3. Mock Display Priority

Mock is now detected when any of these conditions is true:

```text
fallback_to_mock === true
model_stage === "mock"
model_name === "mock_disease_detector"
model_display_name contains "Mock"
```

When a result is Mock, the page displays:

```text
模拟结果
Mock 兜底结果
暂无正式模型指标
```

Mock rendering returns before disease/crop_object badges are added, so Mock records are not displayed as `病害识别` even if an old record has `current_target_type=disease`.

## 4. crop_object Rule

Still preserved.

Non-Mock `current_target_type=crop_object` records display:

```text
辅助目标检测
辅助目标检测，不是病害识别
```

They are not shown as disease recognition.

## 5. Disease Rule

Only non-Mock and non-crop_object records with:

```text
current_target_type === "disease"
```

show:

```text
病害识别
```

Unknown or missing target type still falls back to:

```text
未标明目标类型
```

## 6. favicon 404

Fixed in the HTML head:

```html
<link rel="icon" href="data:,">
```

No backend route was added or changed.

## 7. Page Log Noise

Added simple duplicate suppression for page logs:

- same message within 2000ms is ignored;
- page log cap remains 50 lines;
- manual refresh behavior is preserved;
- existing in-flight request protection is unchanged.

## 8. Verification

Inline JS syntax check:

```powershell
node --check app\static\frontend\smoke-demo-inline.final.js
```

Result: passed.

Required smoke checks:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m pytest
curl.exe -s -o NUL -w "html_http=%{http_code} bytes=%{size_download}\n" http://127.0.0.1:8000/static/frontend/smoke-demo.html
```

Results are recorded in the final handoff after command execution.

## 9. Boundary Confirmation

| Item | Result |
|---|---|
| Started training | no |
| Generated new weights | no |
| Modified training dataset | no |
| Generated Precision/Recall/mAP/F1 | no |
| Connected real UAV SDK | no |
| Weakened smoke/Mock/crop_object warning | no |
| Opened browser for verification | no |
