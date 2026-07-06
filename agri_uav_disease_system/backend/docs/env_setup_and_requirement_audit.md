# ENV-0/ENV-1 项目虚拟环境创建、依赖分层与需求匹配审计

日期：2026-07-02

## 1. 虚拟环境创建命令

后端目录：

```powershell
cd F:\学校\病虫害识别\agri_uav_disease_system\backend
```

本机存在 Python 3.11，因此按优先方案创建项目虚拟环境：

```powershell
py -3.11 -m venv .venv
```

验证 Python 路径：

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.version)"
```

当前虚拟环境 Python：

```text
F:\学校\病虫害识别\agri_uav_disease_system\backend\.venv\Scripts\python.exe
Python 3.11.7
```

说明：终端在部分中文路径输出中出现乱码，但解释器实际路径位于项目 `.venv` 内。

## 2. 依赖安装结果

执行：

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

安装成功。当前默认开发/验收依赖不包含真实 YOLO 依赖：

- 未安装 `ultralytics`
- 未安装 `torch`
- 未安装 `torchvision`

已生成依赖快照：

```text
requirements.lock.txt
```

## 3. 验收结果

### 3.1 compileall

命令：

```powershell
.\.venv\Scripts\python.exe -m compileall app
```

结果：通过。

### 3.2 pytest

命令：

```powershell
.\.venv\Scripts\python.exe -m pytest app/tests -q
```

结果：

```text
39 passed, 15 skipped, 1 warning in 2.57s
```

说明：

- 15 个 skipped 为 smoke YOLO 条件测试。
- 默认 Mock 基线下不安装 Ultralytics/Torch，因此 smoke YOLO 测试应跳过。
- warning 来自 FastAPI/TestClient 对 `httpx` 的兼容提示，不影响当前验收。

### 3.3 system smoke test

命令：

```powershell
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

结果：通过。

通过项：

- FastAPI app import
- SQLite
- static dirs writable
- healthz
- api status
- detect image
- static original
- static result
- record detail
- dashboard summary
- mobile overview
- alert generated
- alerts
- ws results
- ws tasks
- ws alerts

## 4. 默认 Mock 状态

本轮发现代码默认值曾为 `DETECTOR_MODE=smoke`，这与 v0.5 Mock 冻结基线和当前需求不一致。

已修正：

- `app/core/config.py`：未设置 `DETECTOR_MODE` 时默认 `mock`
- `.env.example`：`DETECTOR_MODE=mock`

验证：

```text
/api/status detector_mode = mock
/api/models/status detector_mode = mock
```

结论：

- 默认 Mock 后端可运行。
- 没有真实模型、没有 Ultralytics、没有 Torch 时仍可运行。
- smoke/experimental/real 模型应由显式环境变量和可选依赖启用。

## 5. requirements 审计与分层结果

当前 `requirements.txt`：

```text
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
pydantic>=2.7.0
python-multipart>=0.0.9
pillow>=10.3.0
websockets>=12.0
```

当前 `requirements-dev.txt`：

```text
-r requirements.txt
pytest>=8.2.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
websockets>=12.0
```

当前 `requirements-yolo.txt`：

```text
-r requirements-dev.txt
ultralytics
torch
torchvision
```

审计结论：

- 默认运行依赖较干净。
- 未把 `ultralytics/torch/torchvision` 放入默认依赖，符合 Mock 主链路。
- `pytest/httpx/pytest-asyncio` 已移动到 `requirements-dev.txt`。
- `requirements-yolo.txt` 只作为后续 smoke/真实 YOLO 环境使用，本轮未安装。
- 未加入 `opencv-python`，因为当前后端代码未直接 import `cv2/opencv`。

建议分层：

| 分层 | 依赖 | 状态 |
| -- | -- | -- |
| 默认后端依赖 | fastapi, uvicorn, pydantic, python-multipart, pillow, websockets | 已覆盖 |
| 测试依赖 | pytest, pytest-asyncio, httpx | 已覆盖 |
| 可选 YOLO 依赖 | ultralytics, torch, torchvision | 未默认安装，符合要求 |

## 6. 需求匹配审计表

| 需求 | 当前是否匹配 | 证据/接口/文件 | 是否需要调整 | 建议 |
| -- | -- | -- | -- | -- |
| 系统后端可运行 | 匹配 | `system_smoke_test` 全部 PASS | 否 | 继续保持后端优先 |
| 默认 Mock 模式可演示 | 已匹配 | `/api/status detector_mode=mock`，`app/core/config.py` 默认 mock | 已调整 | smoke 仅显式启用 |
| 单图识别 | 匹配 | `POST /api/detect/image`，烟测 PASS | 否 | 保持 Mock 主链路 |
| 批量任务 | 匹配 | `POST /api/detect/batch`，`GET /api/tasks/{task_id}` | 否 | 后续任务量变大再考虑队列 |
| 大屏接口 | 匹配 | `/api/dashboard/summary` 等接口，烟测 dashboard PASS | 否 | 当前只保留接口契约，不做页面 |
| 移动端接口预留 | 匹配 | `/api/mobile/overview`、`/api/mobile/plots`、`/api/mobile/predictions` | 否 | 当前只保留接口契约，不做页面 |
| alert 预警 | 匹配 | `/api/alerts`、`/ws/alerts`，烟测 PASS | 否 | 继续保持 JSON 推送 |
| detection/prediction alert 区分 | 匹配 | `alert_source`、`prediction_id`、`prediction_window_days` | 否 | 前端后续必须展示来源 |
| 规则预测模块 | 基本匹配 | `/api/prediction/plots/{plot_id}`、`risk-rule-v0.1` | 否 | 不继续扩展预测 UI |
| 预测模块是否过早扩展 | 可控 | 当前仅后端骨架和接口 | 否 | 暂停页面和复杂模型 |
| 虚拟环境是否缺失 | 已修复 | `.venv` 已创建 | 否 | 后续验收统一使用 `.venv` |
| requirements 是否污染全局环境 | 已修复流程 | 本轮使用 `.venv` 安装依赖 | 否 | 不再往全局 Python 装依赖 |
| 真实 YOLO 是否默认强依赖 | 匹配 | `requirements.txt` 不含 ultralytics/torch；`requirements-yolo.txt` 单独存在 | 否 | 后续单独建 YOLO smoke 环境 |
| 无真实模型时是否可运行 | 匹配 | 默认 Mock + pytest/system smoke 通过 | 否 | 保持 fallback 安全提示 |
| 移动端页面设计是否暂停 | 匹配 | 本轮未做移动端 UI | 否 | 后续单独阶段再设计 |
| 大屏页面设计是否暂停 | 匹配 | 本轮未做大屏 UI | 否 | 后续单独阶段再设计 |
| 后端接口是否足够联调 | 基本匹配 | 单图、批量、大屏、移动端、alert、prediction 均有接口 | 否 | 优先写接口契约和联调样例 |
| 模型训练由分支负责 | 匹配 | 当前后端不训练模型 | 否 | 后端只接权重与状态 |
| 暂不接无人机 SDK | 匹配 | 当前无 SDK 接入 | 否 | 保留 source_type 字段即可 |
| 暂不接真实天气 API | 匹配 | 当前天气仅手动录入 | 否 | 后续接入前保留 data_source |
| 暂不接地图服务 | 匹配 | 当前只返回 geo/heatmap 数据 | 否 | 页面和地图 SDK 后期再做 |
| 不伪造模型指标 | 匹配 | `formal_metric_available=false`，预测 metrics 未指定 | 否 | 前端后续不得展示正式指标 |
| 不伪造预测准确率 | 匹配 | `risk_probability_note` 明确说明 | 否 | 保持文档说明 |
| 不输出具体农药剂量 | 匹配 | suggestion disclaimer；测试覆盖无剂量 | 否 | 保持“农技人员确认”口径 |
| WebSocket 只推 JSON | 匹配 | `/ws/results`、`/ws/tasks`、`/ws/alerts` | 否 | 不推图片/base64/视频帧 |

## 7. 当前应该暂停的事项

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

## 8. 当前未完全匹配或需后续关注

- smoke YOLO 测试当前在默认 Mock 环境中跳过；后续需要单独建立 smoke/YOLO 环境验收。
- FastAPI/TestClient 有 `httpx` 兼容提示，当前不影响验收；后续可根据 FastAPI/Starlette 官方建议调整依赖版本。
- 项目不是 git 仓库或当前目录未检测到 `.git`，无法用 git status 输出精确变更状态。

## 9. 下一步建议

1. 固定以后所有后端验收命令使用：

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest app/tests -q
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

2. 暂停 Stage 6.2 移动端/大屏页面设计。
3. 后续真实模型分支交付权重后，再单独创建 smoke/YOLO 验收流程，并显式安装 `requirements-yolo.txt`。
4. 当前可冻结为 `system-v0.6-mock-env-isolated-baseline`。
