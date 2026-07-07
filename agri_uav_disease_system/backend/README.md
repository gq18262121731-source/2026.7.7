# 三下乡无人机水稻病虫害识别系统 MVP 后端

这是第一阶段 MVP 后端代码骨架，目标是跑通单张图片上传、Mock 病虫害识别、结果图生成、SQLite 记录保存、历史查询、大屏/移动端查询和 WebSocket 实时推送闭环。

当前阶段不训练模型、不接真实无人机 SDK、不生成完整大屏和完整移动端。

## 目录结构

```text
backend/
  app/
    main.py
    api/                  # HTTP API 和 WebSocket 路由
    core/                 # 配置、日志、常量、统一异常
    database/             # SQLite 初始化和 Repository
    schemas/              # Pydantic 请求/响应结构
    services/
      inference/          # Mock/Real 检测器、预处理、结果图绘制
      algorithm/          # 后处理、严重程度、风险、农事建议
      storage/            # 原图/结果图存储、识别结果存储
      realtime/           # WebSocket 管理和结果发布
      dashboard/          # 大屏聚合数据
      mobile/             # 移动端预警和建议
    static/
      original/           # 原图
      result/             # 结果图
    tests/                # pytest 测试
```

## 安装依赖

v0.6 Mock 环境冻结基线要求使用项目内 `.venv`，不要再使用全局 Python 做后端验收。建议使用 Python 3.11。

```powershell
cd F:\学校\病虫害识别\agri_uav_disease_system\backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt
```

依赖分层：

- `requirements.txt`：默认运行依赖，支持 Mock 后端、核心接口、SQLite、图片处理和 WebSocket。
- `requirements-dev.txt`：开发和测试依赖，包含 `pytest`、`pytest-asyncio`、`httpx`。
- `requirements-yolo.txt`：后续真实 YOLO smoke 或真实模型接入时才使用，包含 `ultralytics`、`torch`、`torchvision`。

默认 Mock 环境不要安装 `requirements-yolo.txt`。

## 启动命令

```bash
cd agri_uav_disease_system/backend
.\.venv\Scripts\python.exe -m app.scripts.run_dev
```

服务默认运行在：

```text
http://127.0.0.1:8000
```

健康检查：

```text
GET /healthz
```

系统状态：

```text
GET /api/status
```

## 单图识别接口示例

```bash
curl -X POST "http://127.0.0.1:8000/api/detect/image" ^
  -F "file=@sample.jpg" ^
  -F "plot_id=plot_B_01" ^
  -F "plot_name=B-01 地块" ^
  -F "region_name=未指定乡镇" ^
  -F "lng=118.123456" ^
  -F "lat=33.123456" ^
  -F "source=manual_upload"
```

返回统一 `detection_result` JSON，包含原图地址、结果图地址、检测框、严重程度、风险等级和农事建议。

## WebSocket 连接说明

实时识别结果地址：

```text
ws://127.0.0.1:8000/ws/results
```

当 `/api/detect/image` 产生新的识别结果时，服务端会广播完整 `detection_result` JSON。

注意：WebSocket 只推送结构化 JSON，不传输大图、base64 图片或视频帧。

## Mock 模式说明

默认使用 `MockDiseaseDetector`，不依赖真实模型权重。Mock 检测器会根据图片路径和固定随机种子生成 0 到 2 个模拟目标，便于演示和联调。

可在 `.env` 或环境变量中配置：

```text
DETECTOR_MODE=mock
MOCK_SEED=20260622
MOCK_CLASSES=稻瘟病,纹枯病,稻曲病,稻飞虱,稻纵卷叶螟
```

## source_type 与双模型预留

`/api/detect/image` 支持 `source_type`：

- `uav_rgb`
- `uav_multispectral`
- `uav_video_frame`
- `phone_rgb`
- `manual_upload`
- `unknown`

当前真实模型不存在时仍使用 Mock。`ModelManager` 已预留选择规则：无人机来源后续可接 `uav_rice_disease_yolo`，手机/手动上传后续可接 `phone_rice_disease_yolo`。

## 记录分页

`GET /api/records` 返回：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

支持 `page`、`page_size`、`sort` 以及 `plot_id`、`risk_level`、`severity`、`disease`、`start_time`、`end_time` 筛选。

## 批量任务

第二阶段 MVP 已提供最小批量图片识别链路：

- `POST /api/detect/batch`
- `GET /api/tasks/{task_id}`

批量任务先使用 FastAPI `BackgroundTasks` 本地后台处理，返回 `task_id`、进度、成功 `record_ids` 和失败图片明细。后续任务量增大时可迁移到 Celery/RQ。

任务进度也会通过 WebSocket 推送：

```text
ws://127.0.0.1:8000/ws/tasks
```

事件类型为 `task_status`，只推 JSON，不推图片或视频帧。

## 大屏联动接口

第三阶段已提供后端大屏联动最小闭环：

- `GET /api/dashboard/summary`
- `GET /api/dashboard/plots`
- `GET /api/dashboard/plots/{plot_id}`
- `GET /api/dashboard/plots/{plot_id}/records`
- `GET /api/dashboard/heatmap`
- `GET /api/dashboard/disease-statistics`
- `GET /api/dashboard/latest-records`
- `GET /api/dashboard/latest-alerts`

地块聚合按 `plot_id` 分组；缺少 `plot_id` 的记录归入 `unknown_plot`。经纬度优先使用识别记录中的 `lng/lat`，缺失时从 `app/mocks/mock_plots.json` 读取；仍然缺失时热力图跳过该点。

热力图 intensity 和颜色只是大屏展示建议，不是模型指标。

## 第四阶段移动端与预警治理

第四阶段补齐了移动端联动和地块级预警治理骨架：

- `GET /api/mobile/overview`
- `GET /api/mobile/plots`
- `GET /api/mobile/plots/{plot_id}`
- `GET /api/mobile/records/{record_id}`
- `GET /api/alerts`
- `GET /api/alerts/{alert_id}`
- `POST /api/alerts/{alert_id}/resolve`
- `WS /ws/alerts`

当前没有接入真实用户体系，移动端的 `my_plot_count` 暂按系统内全部地块统计。没有接入真实地图服务，经纬度优先来自识别记录，缺失时使用 `app/mocks/mock_plots.json` 兜底。

预警规则：

- `normal`、`low` 默认不生成预警。
- `medium`、`high` 生成预警。
- cooldown 内同一 `plot_id + main_disease` 聚合到同一个 active alert，并更新 `latest_record_id`、`latest_seen_at`、`record_ids`、`severity`、`risk_level`。
- 风险升级会更新原 alert，不重复新建。
- cooldown 由 `ALERT_COOLDOWN_SECONDS` 配置，默认 `3600` 秒。

预警 WebSocket：

```text
ws://127.0.0.1:8000/ws/alerts
```

只推送 `alert_event` JSON，不推送图片、base64 或视频帧。推送失败只记录日志，不影响识别接口、批量任务或 SQLite 保存。

农事建议仅作为辅助参考，包含 `actions`、`knowledge_tags` 和 `disclaimer` 等字段；不会输出具体农药剂量或未经确认的强执行指令。

## 第五阶段联调与验收包

第五阶段补齐了工程联调和验收材料：

- `GET /api/models/status`：真实模型接入前置检查，只检查配置和路径，不加载 YOLO。
- `GET /api/status`：新增 `capabilities`、`models`、`storage` 子结构。
- `GET /api/alerts/{alert_id}/actions`：查询 alert 处理动作。
- `POST /api/alerts/{alert_id}/resolve`：支持 `operator_id`、`operator_name`、`note`，写入 `alert_actions`。
- `GET /api/mobile/overview?user_id=demo_user`：`user_id` 为预留参数，当前不做鉴权过滤。
- `GET /api/mobile/plots?user_id=demo_user`：`user_id` 为预留参数，当前返回全部可见地块。

新增脚本：

```bash
python -m app.scripts.seed_demo_data
python -m app.scripts.seed_demo_data --reset-demo-data
python -m app.scripts.system_smoke_test
```

`seed_demo_data` 只生成 `demo_stage5_` 前缀演示数据，不代表真实模型指标；默认不覆盖用户已有 SQLite，只有 `--reset-demo-data` 会清理第五阶段演示数据。

联调示例包位于：

```text
docs/integration_examples/
```

包含 dashboard/mobile HTTP 示例、curl 示例、WebSocket 说明和 Postman collection。

## 可选 Smoke YOLO 后续分支说明

v0.6 Mock 环境冻结基线默认仍是 `DETECTOR_MODE=mock`，不加载真实 YOLO，也不要求 Ultralytics、Torch 或权重文件存在。

仓库中可能保留后续 smoke YOLO 适配器和条件测试，用于模型训练分支交付权重后的独立联调。该能力不属于默认 Mock 冻结基线；只有显式安装 `requirements-yolo.txt`、设置 `DETECTOR_MODE=smoke` 并配置权重路径时，才应运行 smoke YOLO 条件测试。

Smoke 边界：

- smoke 权重不是正式模型。
- smoke 指标不是正式 Precision/Recall/mAP。
- 后端不训练模型。
- 后端不生成新权重或正式指标。

## CORS

开发环境默认允许本地大屏/移动端调试地址，可通过 `.env.example` 中的 `CORS_ORIGINS`、`CORS_ALLOW_CREDENTIALS`、`CORS_ALLOW_METHODS`、`CORS_ALLOW_HEADERS` 配置。

## 未来如何接入真实 YOLO 模型

当前已预留 `RealDiseaseDetector`：

```text
app/services/inference/real_disease_detector.py
```

后续接入方式：

1. 安装可选模型依赖：`pip install -r requirements-yolo.txt`。
2. 设置 `DETECTOR_MODE=real`。
3. 设置 `MODEL_PATH=/path/to/best.pt`。
4. 在 `RealDiseaseDetector.detect()` 中加载 YOLO 并转换为统一 `Detection` 结构。

如果模型路径为空或权重不存在，系统会自动回退到 Mock，不影响服务启动。

第五阶段新增：

```text
GET /api/models/status
```

该接口只检查 `UAV_MODEL_PATH`、`PHONE_MODEL_PATH` 是否配置、路径是否存在，不安装 Ultralytics，不加载真实权重。空路径不是错误，默认 Mock 环境可显示 `path_exists=false`、`ready=false` 并回退到 Mock。模型训练分支独立负责权重、类别体系和模型指标。

## 结果图说明

结果图保存在：

```text
app/static/result/
```

Pillow 默认字体对中文支持不稳定，因此结果图上的 label 使用英文/拼音映射；接口 JSON 中仍保留中文病虫害名称。

## 测试

```powershell
cd agri_uav_disease_system/backend
.\.venv\Scripts\python.exe -m compileall app
.\.venv\Scripts\python.exe -m pytest app/tests -q
.\.venv\Scripts\python.exe -m app.scripts.system_smoke_test
```

当前 v0.6 Mock 默认验收结果为 `39 passed, 15 skipped, 1 warning`。15 个 skipped 为 YOLO smoke 条件测试在默认 Mock 环境中跳过，符合预期。

当前测试覆盖单图上传、批量任务、记录查询、分页结构、静态资源访问、上传错误、Mock 推理、严重程度、风险映射、农事建议、系统状态、大屏地块详情、移动端接口、预警治理、模型状态前置检查、seed 数据、smoke 自检和 WebSocket 推送。

## 当前未指定项

以下内容当前仍为未指定，MVP 不伪造硬指标：

- 真实无人机型号和 SDK
- 视频流协议
- RGB/多光谱相机方案
- 真实水稻病虫害类别总数
- 真实模型主版本
- 数据集规模
- Precision、Recall、mAP、推理延迟、并发指标
- 服务器配置和业务 SLA
- 地图服务来源
- 原图和结果图保留策略
- 真实用户登录、鉴权和完整告警处理审计链

## 第一阶段验收方式

1. FastAPI 服务可以启动。
2. `GET /healthz` 返回 `{"status":"ok"}`。
3. `GET /api/status` 返回 Mock 模型、数据库、存储和 WebSocket 状态。
4. `POST /api/detect/image` 可以上传图片并返回 `detection_result`。
5. 原图保存在 `app/static/original/`。
6. 结果图保存在 `app/static/result/`。
7. SQLite 中保存识别记录。
8. `GET /api/records` 可以查询历史记录。
9. `GET /api/dashboard/summary` 可以返回大屏汇总。
10. `GET /api/mobile/alerts` 和 `/api/mobile/suggestions/{record_id}` 可以服务移动端。
11. WebSocket 客户端连接 `/ws/results` 后可收到新识别结果。
12. 没有真实模型权重时系统仍正常运行。
# Stage 10 true UAV BLB smoke wiring

The backend supports an explicit true UAV BLB smoke route without replacing the older UAV crop-object route.

Smoke routing:
- `source_type=phone_rgb` or `manual_upload`: `phone_rice_disease_yolo`, `current_target_type=disease`.
- UAV source types without hints: `uav_rice_disease_yolo`, `current_target_type=crop_object`, class `rice_panicle`.
- UAV source types with `model_hint=uav_blb` or `target_type=disease`: `uav_blb_disease_yolo`, `current_target_type=disease`, class `bacterial_leaf_blight`.
- Unknown source types use Mock fallback.

BLB smoke environment variables:

```text
UAV_BLB_MODEL_PATH=F:/学校/病虫害识别/ai_model_training/experiments/uav_blb_yolo/runs/smoke_uav_blb_baseline_v0_1/weights/best.pt
UAV_BLB_MODEL_NAME=uav_blb_disease_yolo
UAV_BLB_MODEL_VERSION=smoke_epoch1_blb_20260623
ENABLE_UAV_BLB_SMOKE=true
UAV_BLB_SMOKE_CONFIDENCE=0.25
```

Boundary:
- The BLB weight is a 1 epoch smoke weight for backend wiring only.
- It was trained from RGB preview renders derived from multispectral TIF data; it is not a formal multispectral model.
- Standard-threshold smoke inference previously produced 0 detections on the tiny demo subset, so this weight is for schema, API, SQLite, result image, and WebSocket integration checks.
- Smoke metrics are not formal Precision/Recall/mAP/F1 and must not be presented as model performance.
- If Ultralytics or a configured smoke weight is unavailable, the API falls back to Mock and sets `fallback_to_mock=true`.
# Stage 11 demo safety and model status wording

The backend exposes demo-safety wording for every smoke/mock route so API clients do not present smoke wiring as formal model capability.

New or expanded fields in `detection_result`:
- `model_hint`
- `target_type`
- `model_display_name`
- `model_warning`
- `model_usage_scope`
- `model_capability_level`

Model status endpoints:
- `GET /api/models/status`: returns `models.phone_model`, `models.uav_crop_model`, `models.uav_blb_model`, `models.mock_model`, `active_routing`, and `demo_safety`.
- `GET /api/models/demo-safety`: returns display rules and warnings for demo pages.

Display rules:
- `is_smoke=true` must be shown as smoke-only wiring.
- `current_target_type=crop_object` must not be shown as disease detection.
- `uav_rice_disease_yolo` currently detects `rice_panicle` crop objects only.
- `uav_blb_disease_yolo` is a BLB smoke route, not a formal UAV disease model.
- `fallback_to_mock=true` must be shown as Mock fallback.
- Do not display Precision/Recall/mAP/F1 as formal performance for smoke models.

Dashboard, mobile, and alert protection:
- `crop_object` records are excluded from disease statistics and latest disease alerts.
- `crop_object` records do not generate pest/disease alerts.
- `disease`, `pest`, and `pest_damage` records can generate pest/disease alerts when risk is medium/high.

## Stage 16 Optional UAV BLB Experimental Route

The backend can optionally load the UAV BLB constrained-408 experimental weight without replacing the existing smoke/default routes.

Explicit experimental routing only:

- `source_type=uav_multispectral` plus `model_hint=uav_blb_exp`
- `source_type=uav_multispectral` plus `model_stage_hint=experimental`
- `model_hint=uav_blb` plus `model_stage_hint=experimental`

The default UAV route remains `uav_rice_disease_yolo` crop_object smoke. The UAV BLB smoke route remains available through `model_hint=uav_blb` or `target_type=disease`.

Experimental environment variables are documented in `.env.example`:

```text
UAV_BLB_EXPERIMENTAL_MODEL_PATH=F:/学校/病虫害识别/ai_model_training/experiments/uav_blb_yolo/runs/exp_uav_blb_preview408_v0_1_5epoch/weights/best.pt
UAV_BLB_EXPERIMENTAL_MODEL_NAME=uav_blb_disease_yolo
UAV_BLB_EXPERIMENTAL_MODEL_VERSION=experimental_preview408_epoch5_20260623
ENABLE_UAV_BLB_EXPERIMENTAL=true
UAV_BLB_EXPERIMENTAL_CONFIDENCE=0.25
```

Boundary:

- The 408 weight is experimental_only, not formal.
- It uses RGB preview renders derived from BLB UAV multispectral TIF data; it is not a true multi-channel multispectral model.
- `preview_1000` is a target name; actual_samples is 408.
- `formal_metric_available=false` must be shown by clients.
- If the experimental weight or dependency is unavailable, the explicit experimental route falls back to Mock and sets `fallback_to_mock=true`; it does not silently downgrade to smoke.

## Stage 21 Optional Phone RiceLeafDiseaseBD Experimental Route

The backend can optionally load the phone RiceLeafDiseaseBD 3 epoch experimental weight without replacing the default phone smoke route.

Explicit experimental routing only:

- `source_type=phone_rgb` plus `model_hint=phone_exp`
- `source_type=phone_rgb` plus `model_stage_hint=experimental`
- `source_type=manual_upload` plus `model_hint=phone_exp` or `model_stage_hint=experimental`

The default phone route remains `phone_rice_disease_yolo` smoke. The experimental route is not formal and must display `formal_metric_available=false` and an experimental warning. Healthy is excluded from disease detection classes. The RiceLeafDiseaseBD conversion uses `source_directory_based_remap` because source class ids were not fully consistent with observed labels.

If the experimental weight or dependency is unavailable, the explicit experimental route falls back to Mock with `fallback_to_mock=true`; it does not silently downgrade to phone smoke.


## Demo And Route References

- [System Model Route Matrix](docs/system_model_route_matrix.md)
- [System Demo Runbook](docs/system_demo_runbook.md)
- [Demo Q&A Guide](docs/demo_qa_answering_guide.md)
- [System Acceptance Summary](docs/system_acceptance_summary.md)

## Stage 6.1 Rule-Based Risk Prediction

Stage 6.1 adds a minimal backend-only disease and pest risk prediction loop. It keeps the v0.5 Mock detection chain intact and does not connect real YOLO, real weather APIs, sensors, UAV SDKs, or map services.

Current consolidated project documentation is available at [docs/current_project_spec.md](docs/current_project_spec.md).

New APIs:
- `GET /api/prediction/plots/{plot_id}`
- `GET /api/prediction/dashboard/summary`
- `GET /api/prediction/risk-map`
- `GET /api/mobile/predictions`
- `GET /api/mobile/plots/{plot_id}/prediction`
- `POST /api/weather/observations`
- `GET /api/weather/observations`
- `POST /api/growth-stages`
- `GET /api/growth-stages/plots/{plot_id}`
- `POST /api/farm-operations`
- `GET /api/farm-operations`
- `GET /api/farm-operations/plots/{plot_id}`

The current prediction model is `rule_based` / `risk-rule-v0.1`. `risk_probability` is only `risk_score / 100`, a normalized rule score, and does not represent a calibrated statistical probability. Model metrics such as accuracy, AUC, and F1 remain `未指定`.

Weather data is manually recorded. Growth stage supports manual correction and basic date inference. Farm operation records only capture user actions. Agriculture suggestions are auxiliary references; concrete prevention plans and pesticide dosage require agricultural technician confirmation.

Prediction alerts and detection alerts are distinguished by `alert_source`:
- `detection`: existing alerts from medium/high detection records.
- `prediction`: alerts from medium/high prediction results, with `prediction_id` and `prediction_window_days`.

`WS /ws/alerts` still pushes JSON only and never pushes images, base64, or video frames.

## Farm Analysis PDF Deployment

The farm analysis report agent uses HTML/CSS plus Playwright Chromium to produce the formal defense-ready PDF.

Install runtime dependencies:

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

Start the backend for local validation:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Generate a report:

```http
POST /api/farm-analysis-reports/generate
```

When Chromium is installed and Playwright succeeds, the response contains:

```json
{
  "pdf_quality": "official",
  "pdf_fallback_used": false,
  "pdf_quality_note": null
}
```

If Chromium is not installed or Playwright PDF rendering fails, the system still writes a basic fallback PDF and returns:

```json
{
  "pdf_quality": "fallback",
  "pdf_quality_note": "PDF 生成使用兜底模板，非正式展示版。"
}
```

The fallback PDF is only for basic download continuity. It should not be used as the formal defense display report.
