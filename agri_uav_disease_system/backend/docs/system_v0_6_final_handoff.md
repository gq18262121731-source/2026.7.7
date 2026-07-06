# System v0.6 Final Handoff

日期：2026-07-02

## 1. 冻结版本名称

```text
system-v0.6-mock-env-isolated-baseline
```

## 2. 当前定位

当前后端是“三下乡无人机水稻病虫害识别系统”的 Mock 可演示、可联调、可验收基线。

当前默认使用 Mock detector，不接真实 YOLO，不训练模型，不接真实无人机 SDK，不接真实天气 API，不接真实地图服务，不做完整大屏页面，不做完整移动端页面。

本版本的核心目标是固定一个稳定、隔离、可复现的系统侧基线，供后续大屏、移动端、模型分支按接口契约逐步对接。

## 3. 当前环境

项目目录：

```text
F:\学校\病虫害识别\agri_uav_disease_system\backend
```

项目虚拟环境 Python：

```text
F:\学校\病虫害识别\agri_uav_disease_system\backend\.venv\Scripts\python.exe
```

默认依赖文件：

- `requirements.txt`：Mock 后端运行依赖。
- `requirements-dev.txt`：开发与测试依赖。
- `requirements-yolo.txt`：后续真实 YOLO smoke 环境依赖，不进入默认 Mock 环境。
- `requirements.lock.txt`：当前默认 Mock 环境依赖快照。

默认环境不安装：

```text
ultralytics
torch
torchvision
torchaudio
```

## 4. 当前验收结果

当前默认 Mock 环境验收结果：

```text
compileall: PASS
pytest: 39 passed, 15 skipped, 1 warning
system_smoke_test: PASS
/api/status detector_mode: mock
/api/models/status detector_mode: mock
```

说明：

- 15 个 skipped 是 YOLO smoke 条件测试。
- 默认 Mock 环境不安装 `ultralytics/torch/torchvision`，因此 YOLO smoke 条件测试跳过符合预期。
- 当前后端验收不再使用全局 Python，统一使用项目 `.venv`。

## 5. 当前已完成能力

- 单图识别。
- 批量任务。
- 历史记录。
- 上传能力查询。
- 大屏接口。
- 移动端接口预留。
- alert 预警治理。
- detection alert / prediction alert 区分。
- Stage 6.1 规则预测模块。
- 天气观测、作物生育期、农事记录的接口契约。
- WebSocket JSON 通道。
- seed demo data。
- system smoke test。
- API 文档和联调示例。

## 6. 当前接口总览

当前已注册 13 个 FastAPI router。按交付分组统计为 12 个接口模块，其中 HTTP 接口模块 11 类，WebSocket 模块 1 类。

### 基础状态

- `GET /healthz`
- `GET /api/status`
- `GET /api/models/status`
- `GET /api/models/demo-safety`

### 上传能力

- `GET /api/upload/capabilities`

### 识别与任务

- `POST /api/detect/image`
- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`

### 历史记录

- `GET /api/records`
- `GET /api/records/{record_id}`

### 大屏

- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/plots/{plot_id}/records`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`

### 移动端接口预留

- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- `GET /api/mobile/alerts`
- `GET /api/mobile/suggestions/{record_id}`
- `GET /api/mobile/predictions`
- `GET /api/mobile/plots/{plot_id}/prediction`

### Alert

- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `GET /api/alerts/{alert_id}/actions`

### 预测模块

- `GET /api/prediction/plots/{plot_id}`
- `GET /api/prediction/dashboard/summary`
- `GET /api/prediction/risk-map`

### 天气观测

- `POST /api/weather/observations`
- `GET /api/weather/observations`

### 生育期

- `POST /api/growth-stages`
- `GET /api/growth-stages/plots/{plot_id}`

### 农事记录

- `POST /api/farm-operations`
- `GET /api/farm-operations`
- `GET /api/farm-operations/plots/{plot_id}`

### WebSocket

- `WS /ws/results`
- `WS /ws/tasks`
- `WS /ws/alerts`

WebSocket 只推 JSON，不推图片、base64 或视频帧。

## 7. 大屏联调说明

大屏当前只保留接口契约，不继续在系统分支设计页面。

大屏同学优先对接：

- `/api/dashboard/summary`
- `/api/dashboard/plots`
- `/api/dashboard/heatmap`
- `/api/dashboard/disease-statistics`
- `/api/dashboard/latest-records`
- `/api/dashboard/latest-alerts`
- `/api/prediction/dashboard/summary`
- `/api/prediction/risk-map`
- `/ws/results`
- `/ws/tasks`
- `/ws/alerts`

当前大屏数据仍以 Mock、seed demo data、规则预测和 SQLite 记录为主，不应包装成真实无人机生产数据。

## 8. 移动端联调说明

移动端当前只保留接口契约，不做页面设计。

移动端同学优先对接：

- `/api/mobile/overview`
- `/api/mobile/plots`
- `/api/mobile/plots/{plot_id}`
- `/api/mobile/records/{record_id}`
- `/api/mobile/alerts`
- `/api/mobile/suggestions/{record_id}`
- `/api/mobile/predictions`
- `/api/mobile/plots/{plot_id}/prediction`
- `/api/farm-operations`
- `/api/alerts/{alert_id}/resolve`
- `/ws/results`
- `/ws/alerts`

当前没有真实用户体系，`user_id` 只是预留参数，不代表已经完成登录、权限、组织或角色系统。

## 9. 模型分支接入说明

模型训练分支后续需要交付：

- UAV 远距离或多光谱 YOLO 权重。
- Phone 近距离 YOLO 权重。
- class map。
- 模型版本号。
- 输入尺寸。
- 置信度阈值建议。
- 验证报告。
- 成功样例和失败样例。
- 模型适用范围和不适用范围。

系统侧后续单独开 YOLO smoke 分支：

1. 新建或复用独立 YOLO smoke 环境。
2. 安装 `requirements-yolo.txt`。
3. 配置模型路径。
4. 使用 `/api/models/status` 检查路径、ready 状态和 fallback 状态。
5. 跑 smoke 测试。
6. 确认失败时仍可回退 Mock。
7. 不污染默认 Mock `.venv`。

安全边界：

- smoke 只能作为工程验证。
- experimental 只能作为实验模型。
- `formal_metric_available=false` 时不能展示正式准确率。
- 默认 Mock fallback 不能包装成真实预测。
- 模型训练不在系统侧分支完成。

## 10. 当前暂停事项

当前继续暂停：

- 移动端页面设计。
- 大屏页面设计。
- 真实 YOLO 接入。
- 模型训练。
- 真实无人机 SDK。
- 真实天气 API。
- 真实地图服务。
- 预测 UI 扩展。
- Celery/RQ 迁移。
- JWT/RBAC 登录权限。
- 正式模型指标展示。
- 预测准确率展示。
- 具体农药剂量输出。

## 11. 运行命令

默认后端运行命令：

```powershell
cd F:\学校\病虫害识别\agri_uav_disease_system\backend
.\.venv\Scripts\python.exe -m app.scripts.seed_demo_data --reset-demo-data
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
.\.venv\Scripts\python.exe -m app.scripts.run_dev
```

默认验收命令：

```powershell
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest app/tests -q
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

不要再使用全局 Python 做后端验收。

## 12. 冻结结论

当前版本可以作为系统侧稳定基线。后续新增真实模型接入、无人机 SDK、真实天气 API、地图服务、前端页面、移动端页面、大屏页面等，都应另开分支或阶段推进，不直接污染当前 Mock 基线。

当前冻结版本：

```text
system-v0.6-mock-env-isolated-baseline
```
