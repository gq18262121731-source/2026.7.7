# Twelfth Round A Frontend Smoke Display Hotfix Report

Generated at: 2026-06-23 Asia/Shanghai

## 1. Crash Risk Assessment

The previous `smoke-demo.html` had several browser-side load risks:

- page load automatically called `refreshAll()`, which requested model status, dashboard summary, disease statistics, latest alerts, and records together;
- page load automatically created a WebSocket connection;
- WebSocket `onclose` used recursive `setTimeout(connectWebSocket, 3000)` with no retry cap;
- WebSocket message handling called `loadRecords()`, which could add extra API work after every pushed result;
- record loading immediately selected a record and then requested both record detail and `/api/mobile/records/{record_id}`;
- WebSocket output rendered a JSON block for model fields, adding unnecessary DOM work.

The hotfix changes the page into a low-load safe demo page.

## 2. Modified Files

| File | Change |
|---|---|
| `app/static/frontend/smoke-demo.html` | Reworked as a safe demo page. Page load only requests `/api/models/status` and `/api/models/demo-safety`; records/dashboard/WebSocket are manual. |
| `reports/twelfth_round_a_frontend_smoke_display_hotfix_report.md` | Added this hotfix report. |

Temporary syntax-check files were used during verification and are not part of the intended delivery.

## 3. Page Load Behavior

Page load now only calls:

```text
GET /api/models/status
GET /api/models/demo-safety
```

It no longer auto-loads:

- `/api/records`
- `/api/dashboard/summary`
- `/api/dashboard/disease-statistics`
- `/api/dashboard/latest-alerts`
- `/api/mobile/records/{record_id}`
- `WS /ws/results`

## 4. WebSocket Safety

Automatic WebSocket on page load: disabled.

The page now has manual buttons:

- `连接 WebSocket`
- `断开 WebSocket`

Protections:

- `state.ws = null`;
- `state.wsConnected = false`;
- `state.wsReconnectCount = 0`;
- only one WebSocket instance is allowed;
- `beforeunload` closes the socket;
- auto reconnect is off by default;
- retry cap is defined as `MAX_WS_RECONNECT = 3`;
- reconnect path, if enabled later, waits 3000ms;
- WebSocket logs are capped to 30 lines;
- WebSocket result cards are capped to 10 items.

## 5. Request Safety

All page fetches now go through:

```text
safeFetchJson(path, options, key)
```

Protections:

- `try/catch`;
- `AbortController`;
- 8000ms timeout;
- in-flight request map to avoid duplicate same-key requests;
- failures are shown in page logs or target panels;
- no recursive retry;
- no exception is intentionally thrown into the global page flow.

## 6. Records And Mobile Detail Limits

Records rendering is capped:

- request uses `page_size=20`;
- frontend also applies `MAX_RECORDS_RENDER = 20`;
- no auto-selected record detail on records load;
- no batch mobile detail requests;
- `/api/mobile/records/{record_id}` is called only after the user clicks one record;
- mobile preview renders only the currently selected record.

## 7. Log And DOM Limits

Limits added:

- page logs: `MAX_LOG_LINES = 50`;
- WebSocket logs: `MAX_WS_LOG_LINES = 30`;
- history records: `MAX_RECORDS_RENDER = 20`;
- WebSocket result cards: `MAX_WS_RESULTS = 10`;
- no full `JSON.stringify` block is rendered into the DOM;
- WebSocket cards show only key model fields.

## 8. Smoke / Mock / crop_object Rules

Preserved: yes.

The page still shows:

- `is_smoke=true`: `小样本 smoke，仅验证链路`;
- `fallback_to_mock=true`: `Mock 兜底结果`;
- `current_target_type=crop_object`: `辅助目标检测，不是病害识别`;
- `model_name=uav_blb_disease_yolo`: `UAV 白叶枯病 smoke 模型`;
- `formal_metric_available=false`: `暂无正式模型指标`;
- Mock fallback as `模拟结果`;
- crop_object as auxiliary target detection, not disease recognition.

`rice_panicle` is not promoted to disease wording.

## 9. Verification

Inline JS syntax check:

```powershell
node --check app/static/frontend/smoke-demo-inline.final.js
```

Result: passed.

Python compile check:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m py_compile app\main.py app\api\status_api.py app\api\records_api.py app\api\mobile_api.py app\api\dashboard_api.py
```

Result: passed.

Backend tests:

```powershell
F:\学校\病虫害识别\.venv\Scripts\python.exe -m pytest
```

Result:

```text
40 passed in 17.81s
```

Low-load curl checks:

```powershell
curl.exe -s -o NUL -w "models_status_http=%{http_code} bytes=%{size_download}\n" http://127.0.0.1:8000/api/models/status
curl.exe -s -o NUL -w "demo_safety_http=%{http_code} bytes=%{size_download}\n" http://127.0.0.1:8000/api/models/demo-safety
curl.exe -s -o NUL -w "html_http=%{http_code} bytes=%{size_download}\n" http://127.0.0.1:8000/static/frontend/smoke-demo.html
```

Result:

```text
models_status_http=200 bytes=7791
demo_safety_http=200 bytes=795
html_http=200 bytes=33332
```

No browser page was opened for this verification.

## 10. Boundary Confirmation

| Item | Result |
|---|---|
| Started training | no |
| Generated new weights | no |
| Modified training dataset | no |
| Generated Precision/Recall/mAP/F1 | no |
| Replaced model weights | no |
| Connected real UAV SDK | no |
| Modified `.env` | no |
| Covered baseline | no |
| Ran `git add` or `git commit` | no |

## 11. Residual Risk

- This is still a static demo page without a browser automation test in this round because the request explicitly forbids browser opening for verification.
- If future code enables `state.autoReconnect`, the existing cap is 3 retries with 3000ms delay.
