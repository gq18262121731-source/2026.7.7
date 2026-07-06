# System v0.6 Mock Env Isolated Baseline

日期：2026-07-02

## 冻结结论

当前后端冻结为：

```text
system-v0.6-mock-env-isolated-baseline
```

冻结目标：

- 使用项目内 `.venv`。
- 默认 `DETECTOR_MODE=mock`。
- 默认环境不安装 `ultralytics`、`torch`、`torchvision`、`torchaudio`。
- 默认 Mock 后端可完成单图识别、批量任务、大屏接口、移动端接口预留、alert、WebSocket、Stage 6.1 规则预测。
- 移动端页面、大屏页面、真实 YOLO、无人机 SDK、真实天气 API、地图服务均暂停。

## 默认安装

```powershell
cd F:\学校\病虫害识别\agri_uav_disease_system\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt
```

不要使用全局 Python 做后端验收。

## 依赖分层

### `requirements.txt`

默认运行依赖：

- `fastapi`
- `uvicorn[standard]`
- `pydantic`
- `python-multipart`
- `pillow`
- `websockets`

### `requirements-dev.txt`

开发和测试依赖：

- `-r requirements.txt`
- `pytest`
- `pytest-asyncio`
- `httpx`
- `websockets`

### `requirements-yolo.txt`

后续 YOLO smoke 或真实模型接入时才使用：

- `-r requirements-dev.txt`
- `ultralytics`
- `torch`
- `torchvision`

默认 `.venv` 不安装该文件。

## 默认验收命令

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest app/tests -q
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

当前默认验收结果：

```text
compileall: passed
pytest: 39 passed, 15 skipped, 1 warning
system_smoke_test: all PASS
```

15 个 skipped 是 YOLO smoke 条件测试在默认 Mock 环境中跳过，符合预期。

## Mock 默认规则

`.env.example` 默认：

```text
DETECTOR_MODE=mock
MODEL_PATH=
UAV_MODEL_PATH=
PHONE_MODEL_PATH=
UAV_BLB_MODEL_PATH=
UAV_BLB_EXPERIMENTAL_MODEL_PATH=
PHONE_EXPERIMENTAL_MODEL_PATH=
ENABLE_UAV_BLB_SMOKE=false
ENABLE_UAV_BLB_EXPERIMENTAL=false
ENABLE_PHONE_EXPERIMENTAL=false
```

空路径不是错误。`/api/models/status` 可显示 `path_exists=false`、`ready=false`。没有真实模型时系统仍回退到 Mock。

## 后续 YOLO Smoke 规则

只有在模型分支交付权重后，才进入 YOLO smoke 环境：

```powershell
pip install -r requirements-yolo.txt
```

并显式设置：

```text
DETECTOR_MODE=smoke
UAV_MODEL_PATH=...
PHONE_MODEL_PATH=...
UAV_BLB_MODEL_PATH=...
```

smoke 权重只用于工程联调，不是正式模型，不展示正式 Precision/Recall/mAP/F1。

## 当前暂停事项

- 移动端页面设计
- 大屏页面设计
- 前端信息架构扩展
- 真实 YOLO 接入
- YOLO 训练
- 无人机 SDK 接入
- 真实天气 API 接入
- 地图服务接入
- 传感器接入
- 正式模型指标展示
- 预测准确率展示
- 具体农药剂量输出

## 需求匹配复核

| 需求 | 当前状态 |
| -- | -- |
| 系统后端可运行 | 已满足 |
| 默认 Mock 可演示 | 已满足 |
| 大屏只预留接口 | 已满足 |
| 移动端只预留接口 | 已满足 |
| 不做移动端页面 | 已暂停 |
| 不做大屏页面 | 已暂停 |
| 模型训练由独立分支负责 | 已满足 |
| 真实 YOLO 后续单独 smoke | 待后续 |
| 默认环境不强依赖 YOLO | 已满足 |
| WebSocket 只推 JSON | 已满足 |
| 不伪造模型指标 | 已满足 |
| 不伪造预测准确率 | 已满足 |
| 不输出具体农药剂量 | 已满足 |

