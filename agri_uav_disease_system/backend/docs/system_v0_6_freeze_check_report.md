# System v0.6 Freeze Check Report

## 1. Freeze Version

```text
system-v0.6-mock-env-isolated-baseline
```

## 2. Check Time

```text
2026-07-03 01:02 Asia/Shanghai
```

## 3. Environment

Project backend:

```text
F:\学校\病虫害识别\agri_uav_disease_system\backend
```

`.venv` Python:

```text
F:\学校\病虫害识别\agri_uav_disease_system\backend\.venv\Scripts\python.exe
```

Global Python was not used for backend acceptance in this check.

## 4. Mock Default Mode

Config check:

```text
settings.detector_mode = mock
/api/status detector_mode = mock
/api/models/status detector_mode = mock
```

`.env.example` check:

```text
DETECTOR_MODE=mock
MODEL_PATH=
UAV_MODEL_PATH=
PHONE_MODEL_PATH=
ENABLE_UAV_BLB_SMOKE=false
ENABLE_UAV_BLB_EXPERIMENTAL=false
ENABLE_PHONE_EXPERIMENTAL=false
```

Result: PASS.

## 5. YOLO/Torch Isolation

Default `.venv` package check:

```text
ultralytics = None
torch = None
torchvision = None
```

Result: PASS. YOLO/Torch are not installed in the default Mock `.venv`.

## 6. Acceptance Results

Commands executed with project `.venv`:

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest app/tests -q
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

Results:

```text
compileall: PASS
pytest: 39 passed, 15 skipped, 1 warning
system_smoke_test: PASS
```

The 15 skipped tests are YOLO smoke conditional tests. They are expected to skip in the default Mock environment.

## 7. Requirements Layering Check

`requirements.txt` contains default Mock backend runtime dependencies:

```text
fastapi
uvicorn[standard]
pydantic
python-multipart
pillow
websockets
```

`requirements.txt` does not contain:

```text
ultralytics
torch
torchvision
torchaudio
```

`requirements-dev.txt` inherits runtime dependencies and adds test dependencies:

```text
-r requirements.txt
pytest
pytest-asyncio
httpx
websockets
```

`requirements-yolo.txt` is reserved for a later real-model smoke branch:

```text
-r requirements-dev.txt
ultralytics
torch
torchvision
```

Result: PASS.

## 8. Document Existence Check

Required freeze and project documents:

| File | Exists |
| --- | --- |
| `docs/system_v0_6_final_handoff.md` | YES |
| `docs/system_v0_6_mock_env_freeze.md` | YES |
| `docs/env_setup_and_requirement_audit.md` | YES |
| `docs/api_contract.md` | YES |
| `README.md` | YES |
| `requirements.txt` | YES |
| `requirements-dev.txt` | YES |
| `requirements-yolo.txt` | YES |
| `requirements.lock.txt` | YES |
| `.env.example` | YES |

Integration examples:

| File | Exists |
| --- | --- |
| `docs/integration_examples/dashboard.http` | YES |
| `docs/integration_examples/mobile.http` | YES |
| `docs/integration_examples/websocket_examples.md` | YES |
| `docs/integration_examples/curl_examples.md` | YES |
| `docs/integration_examples/postman_collection.json` | YES |

Result: PASS.

## 9. Current Frozen Capabilities

- Single-image detection API.
- Batch detection task API.
- Detection record API.
- Dashboard API.
- Mobile API contract.
- Alert governance.
- Detection alert / prediction alert separation.
- Stage 6.1 rule-based prediction module.
- WebSocket JSON push through `/ws/results`, `/ws/tasks`, and `/ws/alerts`.
- Seed demo data.
- System smoke test.
- API documents and integration examples.
- `.venv` virtual environment isolation.
- Requirements dependency layering.

## 10. Items Still Paused

The following items remain paused:

- Mobile page design.
- Dashboard page design.
- Real YOLO integration.
- Model training.
- Real UAV SDK integration.
- Real weather API integration.
- Real map service integration.
- Prediction UI expansion.
- JWT/RBAC authentication and authorization.
- Celery/RQ queue migration.

The backend must not push images, base64, or video frames through WebSocket.

The backend must not fake Precision, Recall, mAP, formal model metrics, prediction accuracy, or pesticide dosage.

## 11. Conditions For Future System-Branch Work

### Condition 1: Frontend / dashboard / mobile integration finds interface field gaps

Allowed work:

- Add or adjust API fields only when needed for integration.
- Keep backward compatibility.
- Keep the existing Mock main chain intact.
- Do not introduce real YOLO/Torch.
- Do not design pages in this backend branch.

### Condition 2: Model training branch delivers real YOLO weights

Start a separate branch:

```text
YOLO-SMOKE-0: real model integration smoke branch
```

Rules:

- Use `requirements-yolo.txt`.
- Do not pollute the default Mock `.venv`.
- Check model paths through `/api/models/status` first.
- Do smoke integration only.
- Do not train models in the system branch.
- Failed real-model loading must fall back to Mock.

## 12. Freeze Conclusion

The backend can remain frozen as:

```text
system-v0.6-mock-env-isolated-baseline
```

This check did not add business features, did not modify business logic, did not install YOLO/Torch, did not train models, and did not modify the Mock main chain.
