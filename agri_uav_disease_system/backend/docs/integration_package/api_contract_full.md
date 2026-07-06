# 当前接口文档

更新时间：2026-07-06  
来源：从 `app.main:create_app()` 导出的 FastAPI OpenAPI 结构整理。当前 HTTP path 共 66 个，另有 3 个 WebSocket 通道。

## 基础约定

- 对外联调地址：以 `README.md` 中部署负责人提供的 `BASE_URL` 为准。
- 本机开发说明：`http://127.0.0.1:8000` 仅后端本机调试使用。
- 在线文档：`GET /docs`、`GET /redoc`
- 机器可读接口：`GET /openapi.json`
- 静态资源前缀：`/static`
- 鉴权：当前版本未接入真实用户/鉴权体系。
- JSON 时间字段：接口中以字符串返回，通常为 ISO 时间或业务日期字符串。
- 上传接口：统一使用 `multipart/form-data`；图片二进制只走 HTTP 上传或静态 URL，不通过 WebSocket 推送。
- 分页响应常见结构：`items`、`total`、`page`、`page_size`。

## 统一错误响应

后端通过统一异常处理返回如下结构：

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {
    "errors": []
  }
}
```

常见 `error_code`：

| error_code | 含义 |
|---|---|
| `INVALID_IMAGE` | 上传文件不是有效图片或不符合图片约束 |
| `FILE_TOO_LARGE` | 文件过大 |
| `MODEL_ERROR` | 模型/推理服务错误 |
| `STORAGE_ERROR` | 文件或结果存储错误 |
| `RECORD_NOT_FOUND` | 识别记录不存在 |
| `DATABASE_ERROR` | 数据库操作错误 |
| `VALIDATION_ERROR` | FastAPI/Pydantic 参数校验失败 |
| `ALERT_NOT_FOUND` | 告警不存在 |
| `INTERNAL_ERROR` | 未捕获的服务端错误 |

## WebSocket

| 通道 | 用途 | 事件 |
|---|---|---|
| `wss://<host>/ws/results` | 推送单图/跟拍识别结果 | `detection_result` |
| `wss://<host>/ws/tasks` | 推送批量任务进度 | `task_status` |
| `wss://<host>/ws/alerts` | 推送告警变化 | `alert_event` |

WebSocket 仅推送 JSON，不推送图片、base64 或视频帧。客户端可保持连接并发送任意文本心跳，服务端当前主要用于广播事件。

## 关键响应结构

### DetectionResult

`DetectionResult` 是单图识别、无人机异常区手机复核、发布版 UAV BLB 分割等接口的核心响应。常用字段如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | string | 固定为 `detection_result` |
| `record_id` | string | 识别记录 ID |
| `image_id` | string | 图片 ID |
| `field_id` / `plot_id` | string/null | 地块 ID / 兼容旧版 plot ID |
| `plot_name` / `region_name` | string/null | 地块名 / 区域名 |
| `timestamp` | string | 识别时间 |
| `image_url` | string | 原图静态 URL |
| `result_image_url` | string | 结果图静态 URL |
| `image_width` / `image_height` | number | 图片尺寸 |
| `source_type` | string | 来源类型 |
| `model_name` / `model_version` | string | 模型名称和版本 |
| `detector_mode` | string | `mock`、`real`、`smoke` 等 |
| `is_smoke` | boolean | 是否为 smoke/演示能力 |
| `model_stage` | string | `mock`、`experimental` 等 |
| `uav_task_id` / `abnormal_region_id` | string/null | 无人机任务/异常区关联 |
| `geo` | object | `{ "lng": number|null, "lat": number|null }` |
| `detections` | array | 检测框数组 |
| `summary` | object | 疾病数量、主病害、置信度、严重程度、风险等级 |
| `suggestion` | object | 农事建议、注意事项、知识标签 |

### Detection

| 字段 | 类型 | 说明 |
|---|---|---|
| `class_id` | integer | 类别序号 |
| `label` | string | 展示标签 |
| `class_name` / `class_code` | string/null | 类别名 / 编码 |
| `category_type` | string/null | 类别类型 |
| `confidence` | number | 置信度 |
| `bbox` | array | `[x1, y1, x2, y2]` |
| `area_ratio` | number | 面积占比 |

### DetectionSummary

| 字段 | 类型 | 说明 |
|---|---|---|
| `disease_count` | integer | 检出目标数 |
| `main_disease` | string/null | 主病害 |
| `max_confidence` | number | 最大置信度 |
| `severity` | string | 严重程度 |
| `risk_level` | string | `normal`、`low`、`medium`、`high` |

## 接口清单

### 状态与模型

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/healthz` | 无 | 健康检查 |
| GET | `/api/status` | 无 | `StatusResponse` |
| GET | `/api/models/status` | 无 | `ModelsStatusResponse` |
| GET | `/api/models/demo-safety` | 无 | `DemoSafetyStatus` |

### 图片识别与分割

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/detect/image` | `multipart/form-data`，见 `DetectImageForm` | `DetectionResult` |
| POST | `/api/detect/uav-blb-segmentation` | `multipart/form-data`，见 `UavBlbReleaseForm` | `DetectionResult` |
| POST | `/api/detect/batch` | `multipart/form-data`，见 `BatchDetectForm` | `BatchTaskCreateResponse` |
| GET | `/api/tasks/{task_id}` | path: `task_id` | `BatchTaskStatus` |
| GET | `/api/upload/capabilities` | 无 | 上传能力说明 |

### 实验性 UAV BLB 分割

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/experimental/uav-blb-segmentation/dry-run` | `multipart/form-data`，见 `UavBlbDryRunForm` | `UavBlbSegmentationDryRunResponse` |
| POST | `/api/experimental/uav-blb-segmentation/field-trial` | `multipart/form-data`，见 `UavBlbFieldTrialForm` | `UavBlbSegmentationFieldTrialResponse` |
| GET | `/api/experimental/uav-blb-segmentation/field-trial/records` | query: `limit=100`，范围 1-1000 | `UavBlbSegmentationFieldTrialRecordsResponse` |
| GET | `/api/experimental/uav-blb-segmentation/field-trial/export.csv` | 无 | CSV 文件 |
| GET | `/api/experimental/uav-blb-segmentation/field-trial/export.json` | 无 | JSON 导出 |

### 地块

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/fields` | JSON: `FieldCreate` | `FieldInfo` |
| GET | `/api/fields` | query: `status`、`page=1`、`page_size=50`，最大 200 | `FieldListResponse` |
| GET | `/api/fields/{field_id}` | path: `field_id` | `FieldInfo` |
| PUT | `/api/fields/{field_id}` | path: `field_id`；JSON: `FieldUpdate` | `FieldInfo` |
| DELETE | `/api/fields/{field_id}` | path: `field_id` | `FieldInfo` |

### 无人机任务与异常区

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/uav/tasks` | JSON: `UavTaskCreate` | `UavTask` |
| GET | `/api/uav/tasks` | query: `field_id`、`page=1`、`page_size=50`，最大 200 | `UavTaskListResponse` |
| GET | `/api/uav/tasks/{uav_task_id}` | path: `uav_task_id` | `UavTask` |
| POST | `/api/uav/tasks/{uav_task_id}/dry-run` | path: `uav_task_id`；JSON: `UavDryRunRequest` | `UavDryRunResponse` |
| GET | `/api/uav/tasks/{uav_task_id}/indices` | path: `uav_task_id` | `UavIndexListResponse` |
| POST | `/api/uav/tasks/{uav_task_id}/analyze-indices` | path: `uav_task_id` | `UavIndexAnalysisResponse` |
| GET | `/api/uav/tasks/{uav_task_id}/index-analysis` | path: `uav_task_id` | `UavIndexAnalysisResponse` |
| GET | `/api/uav/tasks/{uav_task_id}/abnormal-regions` | path: `uav_task_id` | `AbnormalRegionListResponse` |
| GET | `/api/uav/abnormal-regions/{region_id}` | path: `region_id` | `AbnormalRegion` |
| POST | `/api/uav/abnormal-regions/{region_id}/phone-followup` | path: `region_id`；`multipart/form-data`，见 `PhoneFollowupForm` | `DetectionResult` |

### 记录

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/api/records` | query: `plot_id`、`risk_level`、`severity`、`disease`、`start_time`、`end_time`、`page=1`、`page_size=20`、`sort=created_at_desc` | `RecordListResponse` |
| GET | `/api/records/{record_id}` | path: `record_id` | `DetectionResult` |

`sort` 支持：`created_at_desc`、`created_at_asc`、`timestamp_desc`、`timestamp_asc`、`risk_level_desc`。

### 告警

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/api/alerts` | query: `status`、`risk_level`、`plot_id`、`page=1`、`page_size=20`，最大 200 | `AlertPageResponse` |
| GET | `/api/alerts/{alert_id}` | path: `alert_id` | `AlertDetail` |
| POST | `/api/alerts/{alert_id}/resolve` | path: `alert_id`；JSON: `{ "operator_id"?, "operator_name"?, "note"? }` | `AlertDetail` |
| GET | `/api/alerts/{alert_id}/actions` | path: `alert_id` | `AlertActionListResponse` |

### 大屏看板

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/api/dashboard/summary` | 无 | `DashboardSummary` |
| GET | `/api/dashboard/plots` | query: `region_name`、`risk_level`、`disease` | `PlotStatisticsResponse` |
| GET | `/api/dashboard/plots/{plot_id}` | path: `plot_id` | `PlotDetailResponse` |
| GET | `/api/dashboard/plots/{plot_id}/records` | path: `plot_id`；query 同 `/api/records` 的过滤项 | `RecordListResponse` |
| GET | `/api/dashboard/heatmap` | query: `region_name`、`disease`、`risk_level` | `HeatmapResponse` |
| GET | `/api/dashboard/disease-statistics` | 无 | `DiseaseStatisticsResponse` |
| GET | `/api/dashboard/latest-records` | query: `limit=10`，范围 1-50 | `LatestRecordsResponse` |
| GET | `/api/dashboard/latest-alerts` | query: `limit=10`，范围 1-50 | `LatestAlertsResponse` |

### 移动端

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/api/mobile/overview` | query: `user_id`，当前预留 | `MobileOverview` |
| GET | `/api/mobile/plots` | query: `risk_level`、`region_name`、`keyword`、`user_id` | `MobilePlotListResponse` |
| GET | `/api/mobile/plots/{plot_id}` | path: `plot_id` | `MobilePlotDetail` |
| GET | `/api/mobile/records/{record_id}` | path: `record_id` | `MobileRecordDetail` |
| GET | `/api/mobile/alerts` | 无 | `AlertListResponse` |
| GET | `/api/mobile/suggestions/{record_id}` | path: `record_id` | `Suggestion` |

### 预测

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/api/prediction/plots/{plot_id}` | path: `plot_id`；query: `window_days=7`、`disease`、`save=true`、`create_alert=true` | `RiskPredictionResponse` |
| GET | `/api/prediction/dashboard/summary` | 无 | `PredictionSummaryResponse` |
| GET | `/api/prediction/risk-map` | 无 | `PredictionRiskMapResponse` |
| GET | `/api/mobile/predictions` | query: `limit=50`，范围 1-200 | `MobilePredictionListResponse` |
| GET | `/api/mobile/plots/{plot_id}/prediction` | path: `plot_id` | `RiskPredictionResponse` |

### 多源风险融合

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/risk/fusion/evaluate` | JSON: `RiskFusionEvaluateRequest` | `RiskFusionResponse` |
| GET | `/api/risk/fusion/field/{field_id}` | path: `field_id` | `RiskFusionListResponse` |
| GET | `/api/risk/fusion/{prediction_id}` | path: `prediction_id` | `RiskFusionResponse` |

风险融合当前是规则加权评分，用于辅助巡检和实验评估，不是病害概率声明、农艺诊断或用药处方。

### 天气、生育期、农事

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/weather/observations` | JSON: `WeatherObservationCreate` | `WeatherObservation` |
| GET | `/api/weather/observations` | query: `plot_id`、`limit=100`，范围 1-500 | `WeatherObservationListResponse` |
| POST | `/api/growth-stages` | JSON: `GrowthStageCreate` | `GrowthStage` |
| GET | `/api/growth-stages/plots/{plot_id}` | path: `plot_id` | `GrowthStageListResponse` |
| POST | `/api/farm-operations` | JSON: `FarmOperationCreate` | `FarmOperation` |
| GET | `/api/farm-operations` | query: `plot_id`、`limit=100`，范围 1-500 | `FarmOperationListResponse` |
| GET | `/api/farm-operations/plots/{plot_id}` | path: `plot_id`；query: `limit=100`，范围 1-500 | `FarmOperationListResponse` |

### 巡检报告

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| POST | `/api/inspection-reports/generate` | JSON: `InspectionReportGenerateRequest` | `InspectionReport` |
| GET | `/api/inspection-reports` | query: `field_id` | `InspectionReportListResponse` |
| GET | `/api/inspection-reports/{report_id}` | path: `report_id` | `InspectionReport` |

### 知识库与 Agent

| 方法 | 路径 | 参数/请求体 | 响应 |
|---|---|---|---|
| GET | `/api/knowledge/diseases` | 无 | `DiseaseListResponse` |
| GET | `/api/knowledge/diseases/{disease_id}` | path: `disease_id` | `DiseaseDetail` |
| POST | `/api/knowledge/search` | JSON: `KnowledgeSearchRequest` | `KnowledgeSearchResponse` |
| POST | `/api/agent/knowledge-context` | JSON: `KnowledgeContextRequest` | `KnowledgeContextResponse` |
| POST | `/api/agent/diagnosis-report` | JSON: `DiagnosisReportRequest` | `DiagnosisReportResponse` |
| GET | `/api/agent/llm-status` | 无 | `LLMStatusResponse` |

## 请求体速查

### DetectImageForm

`POST /api/detect/image`，`multipart/form-data`。

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `file` | 是 | file | 图片文件 |
| `field_id` | 否 | string | 新地块 ID |
| `plot_id` | 否 | string | 兼容旧版地块 ID |
| `plot_name` | 否 | string | 地块名 |
| `region_name` | 否 | string | 区域名 |
| `lng` / `lat` | 否 | number | 经纬度 |
| `source` | 否 | string | 旧版来源字段 |
| `source_type` | 否 | string | 推荐来源字段，如 `phone_rgb`、`uav_multispectral` |
| `model_hint` | 否 | string | 模型路由提示，如 `uav_blb` |
| `target_type` | 否 | string | 目标类型，如 `disease` |
| `model_stage_hint` | 否 | string | 模型阶段提示 |
| `uav_task_id` | 否 | string | 关联无人机任务 |
| `abnormal_region_id` | 否 | string | 关联异常区 |

常用 `source_type`：`uav_rgb`、`uav_multispectral`、`uav_video_frame`、`phone_rgb`、`manual_upload`、`unknown`、`phone_followup`。

### UavBlbReleaseForm

`POST /api/detect/uav-blb-segmentation`，`multipart/form-data`。

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `file` | 是 | file | 图片文件 |
| `field_id` / `plot_id` / `plot_name` / `region_name` | 否 | string | 地块和区域信息 |
| `lng` / `lat` | 否 | number | 经纬度 |
| `human_review_status` | 否 | string | 默认 `pending` |
| `human_review_label` | 否 | string | 人工复核标签 |
| `issue_tags` | 否 | string | 问题标签，服务端按字符串接收 |
| `reviewer_note` | 否 | string | 复核备注 |

### UavBlbDryRunForm

`POST /api/experimental/uav-blb-segmentation/dry-run`，`multipart/form-data`。

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `file` | 是 | file | 图片文件 |
| `mode` | 是 | string | dry-run 模式 |
| `return_probability_map` | 否 | boolean | 默认 `true` |
| `return_overlay` | 否 | boolean | 默认 `true` |

### UavBlbFieldTrialForm

`POST /api/experimental/uav-blb-segmentation/field-trial`，`multipart/form-data`。

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `file` | 是 | file | 图片文件 |
| `mode` | 是 | string | 试验模式 |
| `plot_id` / `plot_name` | 否 | string | 地块信息 |
| `operator_note` | 否 | string | 操作备注 |
| `human_review_status` | 否 | string | 默认 `pending` |
| `human_review_label` | 否 | string | 人工复核标签 |
| `issue_tags` | 否 | string | 问题标签 |
| `return_probability_map` | 否 | boolean | 默认 `true` |
| `return_overlay` | 否 | boolean | 默认 `true` |

### BatchDetectForm

`POST /api/detect/batch`，`multipart/form-data`。

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `files` | 是 | file[] | 多图上传，重复使用同一个 form key |
| `plot_id` / `plot_name` / `region_name` | 否 | string | 批量共用地块信息 |
| `lng` / `lat` | 否 | number | 批量共用经纬度 |
| `source` / `source_type` | 否 | string | 来源字段 |

### PhoneFollowupForm

`POST /api/uav/abnormal-regions/{region_id}/phone-followup`，`multipart/form-data`。

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `file` | 是 | file | 复核图片 |
| `field_id` / `plot_id` / `plot_name` / `region_name` | 否 | string | 地块和区域信息 |
| `lng` / `lat` | 否 | number | 经纬度 |
| `source_type` | 否 | string | 默认 `phone_followup` |
| `model_hint` | 否 | string | 模型路由提示 |
| `target_type` | 否 | string | 默认 `disease` |
| `model_stage_hint` | 否 | string | 模型阶段提示 |

### FieldCreate

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `field_id` | 是 | string | 地块 ID |
| `field_name` | 是 | string | 地块名称 |
| `location_city` | 否 | string | 默认宿迁市 |
| `location_district` / `location_town` / `location_village` | 否 | string | 行政区划 |
| `center_lat` / `center_lng` | 否 | number | 中心经纬度 |
| `area_estimate_mu` | 否 | number | 面积估算，单位亩 |
| `crop_type` | 否 | string | 默认 `rice` |
| `current_growth_stage` | 否 | string | 当前生育期 |
| `field_status` | 否 | string | 默认 `active` |
| `notes` | 否 | string | 备注 |

`FieldUpdate` 字段与 `FieldCreate` 类似，全部可选。

### UavTaskCreate

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `task_name` | 是 | string | 任务名称 |
| `field_id` | 否 | string | 地块 ID |
| `flight_date` | 否 | string | 飞行日期 |
| `sensor_type` | 否 | string | 默认 `multispectral` |
| `data_mode` | 否 | string | 默认 `dry_run` |
| `growth_stage` | 否 | string | 生育期 |
| `weather_text` | 否 | string | 天气说明 |

### UavDryRunRequest

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `field_id` | 否 | string | 地块 ID |
| `task_name` | 否 | string | 任务名称 |
| `sensor_type` | 否 | string | 默认 `multispectral` |
| `growth_stage` | 否 | string | 生育期 |
| `weather_text` | 否 | string | 天气说明 |
| `dry_run_profile` | 否 | string | 默认 `moderate_abnormal` |

### RiskFusionEvaluateRequest

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `field_id` | 是 | string | 地块 ID |
| `uav_task_id` | 否 | string | 无人机任务 ID |
| `abnormal_region_id` | 否 | string | 异常区 ID |
| `phone_image_id` | 否 | string | 手机复核图片 ID |
| `include_weather` | 否 | boolean | 默认 `true` |
| `include_history` | 否 | boolean | 默认 `true` |
| `include_treatment` | 否 | boolean | 默认 `true` |

### WeatherObservationCreate

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `observed_date` | 是 | string | 观测日期 |
| `plot_id` / `region_name` | 否 | string | 地块/区域 |
| `temperature_max` / `temperature_min` | 否 | number | 最高/最低温 |
| `humidity_avg` | 否 | number | 平均湿度 |
| `rainfall_mm` | 否 | number | 降雨量 |
| `wind_speed` | 否 | number | 风速 |
| `sunshine_hours` | 否 | number | 日照时长 |
| `weather_text` | 否 | string | 天气描述 |
| `data_source` | 否 | string | 默认 `manual` |

### GrowthStageCreate

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `plot_id` | 是 | string | 地块 ID |
| `rice_variety` | 否 | string | 水稻品种 |
| `sowing_date` | 否 | string | 播种日期 |
| `transplanting_date` | 否 | string | 移栽日期 |
| `growth_stage` | 否 | string | 生育期 |
| `manual_growth_stage` | 否 | string | 人工录入生育期 |
| `inferred_growth_stage` | 否 | string | 推断生育期 |

### FarmOperationCreate

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `plot_id` | 是 | string | 地块 ID |
| `operation_type` | 是 | string | 农事类型 |
| `operation_time` | 是 | string | 操作时间 |
| `target_disease` | 否 | string | 目标病害 |
| `material_name` | 否 | string | 物料名称 |
| `dosage_text` | 否 | string | 用量文本 |
| `operator_id` / `operator_name` | 否 | string | 操作人 |
| `note` | 否 | string | 备注 |
| `photo_url` | 否 | string | 图片 URL |

### InspectionReportGenerateRequest

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `field_id` | 是 | string | 地块 ID |
| `uav_task_id` | 否 | string | 无人机任务 ID |
| `include_rag` | 否 | boolean | 默认 `true` |
| `include_risk` | 否 | boolean | 默认 `true` |

### KnowledgeSearchRequest

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `query` | 否 | string | 默认空字符串 |
| `disease_id` | 否 | string | 病害 ID |
| `section_type` | 否 | string | 知识章节类型 |
| `top_k` | 否 | integer | 默认 5 |

### DiagnosisReportRequest

| 字段 | 必填 | 类型 | 默认/说明 |
|---|---:|---|---|
| `record_id` | 否 | string | 识别记录 ID |
| `disease_id` | 否 | string | 病害 ID |
| `model_class` | 否 | string | 模型输出类别 |
| `confidence` | 否 | number | 置信度 |
| `source_type` | 否 | string | 来源类型 |
| `user_question` | 否 | string | 用户问题 |

## 示例

以下示例使用：

```bash
BASE_URL=https://test-api.example.com
TOKEN=replace-with-your-token
```

### 单图识别

```bash
curl -X POST "$BASE_URL/api/detect/image" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.jpg" \
  -F "plot_id=plot_B_01" \
  -F "plot_name=B-01 地块" \
  -F "region_name=宿迁试验田" \
  -F "lng=118.123456" \
  -F "lat=33.123456" \
  -F "source_type=phone_rgb"
```

### UAV BLB smoke 路由

```bash
curl -X POST "$BASE_URL/api/detect/image" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@blb_preview.jpg" \
  -F "source_type=uav_multispectral" \
  -F "model_hint=uav_blb" \
  -F "target_type=disease"
```

### 批量识别

```bash
curl -X POST "$BASE_URL/api/detect/batch" \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@sample_1.jpg" \
  -F "files=@sample_2.jpg" \
  -F "plot_id=plot_B_01" \
  -F "source_type=phone_rgb"
```

### 创建地块

```bash
curl -X POST "$BASE_URL/api/fields" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field_id": "field_001",
    "field_name": "B-01 地块",
    "location_city": "宿迁市",
    "crop_type": "rice"
  }'
```

### 创建无人机任务并 dry-run

```bash
curl -X POST "$BASE_URL/api/uav/tasks" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field_id": "field_001",
    "task_name": "B-01 多光谱巡检",
    "sensor_type": "multispectral",
    "data_mode": "dry_run"
  }'

curl -X POST "$BASE_URL/api/uav/tasks/{uav_task_id}/dry-run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dry_run_profile": "moderate_abnormal"
  }'
```

### 风险融合

```bash
curl -X POST "$BASE_URL/api/risk/fusion/evaluate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field_id": "field_001",
    "uav_task_id": "uav_task_001",
    "include_weather": true,
    "include_history": true,
    "include_treatment": true
  }'
```

## 相关文档

- `docs/integration_examples/curl_examples.md`
- `docs/integration_examples/postman_collection.json`
- `docs/integration_examples/websocket_examples.md`
- `docs/prediction_api_contract.md`
- `docs/kg_rag_agent_v0_1_api.md`
- `docs/uav_blb_experimental_integration_guide.md`
