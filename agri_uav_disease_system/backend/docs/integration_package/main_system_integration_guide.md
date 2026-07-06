# 主系统联调指南

面向主业务系统、管理后台、数据中台和巡检报告流程。完整字段以 `api_contract_full.md` 和 `openapi.json` 为准。

## 核心对象

| 对象 | 主要接口 |
|---|---|
| 地块 | `/api/fields` |
| 无人机任务 | `/api/uav/tasks` |
| 无人机指数/异常区 | `/api/uav/tasks/{uav_task_id}/indices`、`/api/uav/tasks/{uav_task_id}/abnormal-regions` |
| 手机复核 | `/api/uav/abnormal-regions/{region_id}/phone-followup` |
| 识别记录 | `/api/records`、`/api/records/{record_id}` |
| 多源风险融合 | `/api/risk/fusion/*` |
| 天气/生育期/农事 | `/api/weather/observations`、`/api/growth-stages`、`/api/farm-operations` |
| 巡检报告 | `/api/inspection-reports/*` |

## 推荐业务流程

1. 主系统创建地块：`POST /api/fields`
2. 创建无人机巡检任务：`POST /api/uav/tasks`
3. 演示环境生成 dry-run 指数与异常区：`POST /api/uav/tasks/{uav_task_id}/dry-run`
4. 查询异常区：`GET /api/uav/tasks/{uav_task_id}/abnormal-regions`
5. 手机现场复核：`POST /api/uav/abnormal-regions/{region_id}/phone-followup`
6. 触发风险融合：`POST /api/risk/fusion/evaluate`
7. 生成巡检报告：`POST /api/inspection-reports/generate`
8. 查询报告列表或详情：`GET /api/inspection-reports`

## 地块字段口径

主系统建议以 `field_id` 作为正式地块主键；`plot_id` 保留给旧版移动端/大屏兼容。新集成尽量同时传：

```json
{
  "field_id": "field_001",
  "field_name": "B-01 地块",
  "location_city": "宿迁市",
  "crop_type": "rice"
}
```

## 风险融合口径

`POST /api/risk/fusion/evaluate` 当前是规则加权分，不是统计概率或正式诊断：

```json
{
  "field_id": "field_001",
  "uav_task_id": "uav_task_001",
  "abnormal_region_id": "region_001",
  "phone_image_id": "img_001",
  "include_weather": true,
  "include_history": true,
  "include_treatment": true
}
```

返回中的 `experimental_only=true`、`not_for_production=true`、`probability_claim=false` 必须保留语义，不要在主系统中展示为“确诊概率”。

## 实验接口边界

以下接口仅用于实验展示或模型候选验证，不建议主系统长期依赖：

- `/api/experimental/uav-blb-segmentation/*`
- `detector_mode=smoke`
- `model_stage=experimental`
- `production_ready=false`

如确需接入，主系统应把结果标记为“实验结果/人工待复核”。

