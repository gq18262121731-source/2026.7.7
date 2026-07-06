# Sixteenth Round B-Fix - Pytest Environment Report

Generated: 2026-06-23

## Objective

Complete the backend pytest environment and rerun full verification for the optional UAV BLB 408 experimental backend integration.

## Environment Audit

Available Python interpreters:

- `C:\Users\13010\anaconda3\python.exe` Python 3.9.13
- `F:\Python3.13\python.exe`
- `C:\Users\13010\AppData\Local\Programs\Python\Python311\python.exe`
- `C:\Users\13010\anaconda3\envs\torchgpu\python.exe` Python 3.11.15
- `C:\Users\13010\anaconda3\envs\vision311\python.exe` Python 3.11.15

Conda environments audited:

- base
- health
- identity310
- torchgpu
- vision311

Initial dependency status:

- base: had pytest, pillow, numpy, sqlalchemy; missing fastapi, pydantic, httpx, ultralytics, cv2.
- torchgpu: had fastapi, pydantic, ultralytics, pillow, numpy, cv2, multipart; missing pytest, httpx, sqlalchemy.
- vision311: had fastapi, pydantic, ultralytics, pillow, numpy, cv2; missing pytest, httpx, sqlalchemy, multipart.

## Selected Environment

Selected `torchgpu` because it already had the model runtime dependencies required for the backend smoke/experimental adapter, including FastAPI, Pydantic, Ultralytics, Pillow, NumPy, OpenCV, and python-multipart.

Python path:
`C:\Users\13010\anaconda3\envs\torchgpu\python.exe`

Python version:
`3.11.15 | packaged by Anaconda, Inc.`

## Dependencies Filled

Added `requirements-test.txt` with:

```text
pytest
httpx
sqlalchemy
```

Installed with:

```powershell
& 'C:\Users\13010\anaconda3\envs\torchgpu\python.exe' -m pip install -r requirements-test.txt
```

Installed packages included:

- pytest 9.1.1
- httpx 0.28.1
- sqlalchemy 2.0.51
- httpcore 1.0.9
- greenlet 3.5.2
- pluggy 1.6.0
- iniconfig 2.3.0
- pygments 2.20.0

## Final Dependency Check

- fastapi 0.136.1
- pydantic 2.13.4
- pytest 9.1.1
- httpx 0.28.1
- ultralytics 8.4.52
- pillow 12.2.0
- numpy 2.4.4
- cv2 4.13.0
- sqlalchemy 2.0.51

## Pytest Result

Command:

```powershell
& 'C:\Users\13010\anaconda3\envs\torchgpu\python.exe' -m pytest app/tests -q
```

Result:

```text
42 passed in 9.19s
```

## Functional Boundary Self-check

Executed service-layer checks with `torchgpu` after pytest:

- Experimental explicit route selected `uav_blb_disease_yolo` with `model_stage=experimental`, `is_smoke=false`, `current_target_type=disease`, `fallback_to_mock=false`.
- BLB smoke route remained `model_stage=smoke`.
- Default UAV route remained `current_target_type=crop_object`.
- Phone route remained phone smoke.
- Missing experimental weight fell back to Mock with `fallback_to_mock=true`.
- `/api/models/status` includes `uav_blb_experimental_model` and marks it ready.
- `/api/models/demo-safety` keeps `formal_metric_available=false` and experimental display rules.

## Boundary Confirmation

- Training: no.
- Validation: no.
- infer_demo: no.
- New weights generated: no.
- Formal metrics generated: no.
- Real `.env` modified: no.
- Default UAV route changed: no.
- Experimental route remains explicit only.
- Mock fallback remains available.
- Git add/commit: no.

## Final Status

COMPLETE.
