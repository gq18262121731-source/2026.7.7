# 主系统接口联调说明

主系统按业务流程联调，不建议只按接口表格逐个调用。

统一环境变量：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

统一 Header：

```http
Authorization: Bearer <TOKEN>
Content-Type: application/json
```

## 主流程

```text
创建地块 -> 创建 UAV 任务 -> 执行 dry-run -> 获取异常区 -> 手机复查 -> 风险融合 -> 生成报告 -> 查询报告历史
```

## 1. 创建地块

### 接口

POST `/api/fields`

### 稳定性

`stable`

### 用途

创建主系统中的巡检田块。

### Body 参数

```json
{
  "field_id": "SQ_FIELD_001",
  "field_name": "宿迁一号田",
  "location_city": "宿迁市",
  "location_district": "宿城区",
  "location_town": "示范镇",
  "center_lat": 33.51,
  "center_lng": 118.48,
  "current_growth_stage": "分蘖期",
  "notes": "外部联调田块"
}
```

### 成功响应示例

```json
{
  "field_id": "SQ_FIELD_001",
  "field_name": "宿迁一号田",
  "crop_type": "rice",
  "field_status": "active",
  "created_at": "2026-07-06T10:00:00"
}
```

### 失败响应示例

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

### 前端处理建议

- `field_id` 建议由主系统生成并保持唯一。
- 创建失败时不要重复提交，提示用户检查字段。

## 2. 查询地块

### 接口

GET `/api/fields`

### 稳定性

`stable`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `status` | string | 否 | 例如 `active` |
| `page` | integer | 否 | 默认 1 |
| `page_size` | integer | 否 | 默认 20 |

### 成功响应示例

```json
{
  "items": [
    {
      "field_id": "SQ_FIELD_001",
      "field_name": "宿迁一号田",
      "field_status": "active"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "DATABASE_ERROR",
  "message": "数据库访问失败",
  "detail": {}
}
```

### 前端处理建议

- 列表为空时显示“暂无田块”。
- 分页字段按后端返回为准。

## 3. 查询单个地块

### 接口

GET `/api/fields/{field_id}`

### 稳定性

`stable`

### 成功响应示例

```json
{
  "field_id": "SQ_FIELD_001",
  "field_name": "宿迁一号田",
  "location_city": "宿迁市",
  "current_growth_stage": "分蘖期"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "田块不存在",
  "detail": {}
}
```

### 前端处理建议

- 进入巡检工作台前先确认田块存在。

## 4. 创建 UAV 任务

### 接口

POST `/api/uav/tasks`

### 稳定性

`preview`

### Body 参数

```json
{
  "field_id": "SQ_FIELD_001",
  "task_name": "宿迁一号田 UAV dry-run 巡检",
  "sensor_type": "multispectral",
  "data_mode": "dry_run",
  "growth_stage": "分蘖期",
  "weather_text": "阴天，湿度较高"
}
```

### 成功响应示例

```json
{
  "uav_task_id": "uav_001",
  "field_id": "SQ_FIELD_001",
  "task_name": "宿迁一号田 UAV dry-run 巡检",
  "sensor_type": "multispectral",
  "data_mode": "dry_run",
  "status": "created",
  "is_mock": true
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {}
}
```

### 前端处理建议

- `data_mode=dry_run` 必须展示为演示/流程验证。
- 不要把 dry-run 包装成真实遥感反演结论。

## 5. 查询 UAV 任务

### 接口

GET `/api/uav/tasks`

### 稳定性

`preview`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `field_id` | string | 否 | 按田块过滤 |
| `page` | integer | 否 | 页码 |
| `page_size` | integer | 否 | 每页数量 |

### 成功响应示例

```json
{
  "items": [
    {
      "uav_task_id": "uav_001",
      "field_id": "SQ_FIELD_001",
      "status": "created",
      "data_mode": "dry_run"
    }
  ],
  "total": 1
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "DATABASE_ERROR",
  "message": "数据库访问失败",
  "detail": {}
}
```

### 前端处理建议

- 任务为空时提示先创建 UAV 任务。

## 6. 查询单个 UAV 任务

### 接口

GET `/api/uav/tasks/{uav_task_id}`

### 稳定性

`preview`

### 成功响应示例

```json
{
  "uav_task_id": "uav_001",
  "task_name": "宿迁一号田 UAV dry-run 巡检",
  "status": "created",
  "data_mode": "dry_run"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "UAV 任务不存在",
  "detail": {}
}
```

### 前端处理建议

- 若任务不存在，返回任务列表。

## 7. 执行 UAV dry-run

### 接口

POST `/api/uav/tasks/{uav_task_id}/dry-run`

### 稳定性

`experimental`

### Body 参数

```json
{
  "field_id": "SQ_FIELD_001",
  "task_name": "宿迁一号田 UAV dry-run 巡检",
  "sensor_type": "multispectral",
  "growth_stage": "分蘖期",
  "weather_text": "阴天，湿度较高",
  "dry_run_profile": "moderate_abnormal"
}
```

### 成功响应示例

```json
{
  "uav_task_id": "uav_001",
  "field_id": "SQ_FIELD_001",
  "status": "completed",
  "data_mode": "dry_run",
  "is_mock": true,
  "mock_safety_note": "dry-run 仅用于流程验证。",
  "indices": [],
  "abnormal_regions": []
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "MODEL_ERROR",
  "message": "UAV dry-run 分析失败",
  "detail": {}
}
```

### 前端处理建议

- 必须展示 `mock_safety_note`。
- 不要写成正式遥感诊断。

## 8. 获取异常区列表

### 接口

GET `/api/uav/tasks/{uav_task_id}/abnormal-regions`

### 稳定性

`preview`

### 成功响应示例

```json
{
  "items": [
    {
      "region_id": "region_001",
      "uav_task_id": "uav_001",
      "region_name": "A-001",
      "abnormal_type": "ndvi_low",
      "abnormal_level": "medium",
      "abnormal_area_ratio": 0.12,
      "source_index_type": "ndvi",
      "confirm_status": "pending"
    }
  ],
  "total": 1
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "UAV 任务不存在",
  "detail": {}
}
```

### 前端处理建议

- 空列表显示“暂无异常区域”。
- 选择异常区后进入手机复查。

## 9. 获取异常区详情

### 接口

GET `/api/uav/abnormal-regions/{region_id}`

### 稳定性

`preview`

### 成功响应示例

```json
{
  "region_id": "region_001",
  "region_name": "A-001",
  "abnormal_level": "medium",
  "confirm_status": "phone_confirmed",
  "linked_phone_image_id": "img_phone_001",
  "linked_record_id": "rec_followup_001",
  "confirmed_disease_type": "疑似白叶枯"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "异常区域不存在",
  "detail": {}
}
```

### 前端处理建议

- 复查后刷新详情，确认回写字段。

## 10. 手机复查异常区

### 接口

POST `/api/uav/abnormal-regions/{region_id}/phone-followup`

### 稳定性

`preview`

### FormData 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | file | 是 | 手机近景图 |
| `field_id` | string | 是 | 田块 ID |
| `uav_task_id` | string | 是 | UAV 任务 ID |
| `source_type` | string | 否 | 建议 `phone_followup` |
| `model_hint` | string | 否 | 建议 `phone` |
| `target_type` | string | 否 | 建议 `disease` |
| `region_name` | string | 否 | 区域名称 |

### 成功响应示例

```json
{
  "record_id": "rec_followup_001",
  "abnormal_region_id": "region_001",
  "model_stage": "real",
  "summary": {
    "main_disease": "疑似白叶枯",
    "max_confidence": 0.79,
    "risk_level": "medium"
  }
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "INVALID_IMAGE",
  "message": "图片格式不支持或文件损坏",
  "detail": {}
}
```

### 前端处理建议

- 上传成功后刷新异常区详情。
- 不通过 WebSocket 上传图片。

## 11. 风险融合

### 接口

POST `/api/risk/fusion/evaluate`

### 稳定性

`experimental`

### 用途

基于 UAV、手机复查、天气、历史记录等字段生成实验性规则评分。

### Body 参数

```json
{
  "field_id": "SQ_FIELD_001",
  "uav_task_id": "uav_001",
  "abnormal_region_id": "region_001",
  "phone_image_id": "img_phone_001",
  "disease_type": "疑似白叶枯"
}
```

### 成功响应示例

```json
{
  "prediction_id": "risk_001",
  "field_id": "SQ_FIELD_001",
  "total_risk_score": 68,
  "risk_level": "medium",
  "model_type": "rule_weighted",
  "model_stage": "experimental",
  "probability_claim": false,
  "safety_note": "规则评分仅用于巡检优先级辅助判断。"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "VALIDATION_ERROR",
  "message": "请求参数校验失败",
  "detail": {}
}
```

### 前端处理建议

- 必须展示 `model_stage=experimental`。
- 不要展示为正式发病概率。

## 12. 生成巡检报告

### 接口

POST `/api/inspection-reports/generate`

### 稳定性

`preview`

### Body 参数

```json
{
  "field_id": "SQ_FIELD_001",
  "uav_task_id": "uav_001",
  "include_rag": true,
  "include_risk": true
}
```

### 成功响应示例

```json
{
  "report_id": "report_001",
  "field_id": "SQ_FIELD_001",
  "uav_task_id": "uav_001",
  "report_title": "宿迁一号田巡检报告",
  "summary": "本报告用于辅助巡检复核。",
  "report_status": "generated",
  "model_safety_note": "该报告不代表最终现场诊断结论。"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "田块或 UAV 任务不存在",
  "detail": {}
}
```

### 前端处理建议

- 报告为辅助巡检报告，不作为最终诊断或用药依据。

## 13. 查询报告历史

### 接口

GET `/api/inspection-reports`

### 稳定性

`preview`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `field_id` | string | 否 | 按田块过滤 |

### 成功响应示例

```json
{
  "items": [
    {
      "report_id": "report_001",
      "field_id": "SQ_FIELD_001",
      "report_status": "generated"
    }
  ],
  "total": 1
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "DATABASE_ERROR",
  "message": "数据库访问失败",
  "detail": {}
}
```

### 前端处理建议

- 历史列表为空时显示“暂无巡检报告”。

## 14. 查询报告详情

### 接口

GET `/api/inspection-reports/{report_id}`

### 稳定性

`preview`

### 成功响应示例

```json
{
  "report_id": "report_001",
  "report_title": "宿迁一号田巡检报告",
  "risk_summary": {
    "risk_level": "medium",
    "risk_score": 68
  },
  "rag_suggestion": "建议结合田间情况人工复核。",
  "model_safety_note": "报告仅用于辅助巡检。"
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "巡检报告不存在",
  "detail": {}
}
```

### 前端处理建议

- 始终展示 `model_safety_note`。
- RAG 建议不等于最终诊断。
