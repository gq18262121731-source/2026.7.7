# 移动端第二阶段可选接口

本文件仅用于后续规划，不属于移动端第一阶段联调范围。

## 11. 第二阶段可选：获取移动端首页

### 接口

GET `/api/mobile/overview`

### 稳定性

`stable`

### 用途

用于移动端第二阶段展示待处理告警、最近识别、风险摘要和巡检入口。第一阶段可以不接入该接口。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `user_id` | string | 否 | 当前用户 ID；演示环境可不传 |

### 成功响应示例

```json
{
  "user_id": "demo_user",
  "today_detect_count": 8,
  "pending_alert_count": 2,
  "high_risk_plot_count": 1,
  "latest_records": [
    {
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "main_disease": "疑似白叶枯",
      "risk_level": "medium",
      "timestamp": "2026-07-06T10:30:00"
    }
  ]
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

- 加载中显示骨架屏或 Loading。
- 数值为空显示 `0`。
- 接口失败时保留页面结构，展示中文错误提示。

## 12. 第二阶段可选：获取地块列表

### 接口

GET `/api/mobile/plots`

### 稳定性

`stable`

### 用途

用于移动端展示可巡检地块列表。第一阶段不强制接入。

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `risk_level` | string | 否 | 风险等级过滤 |
| `region_name` | string | 否 | 区域过滤 |
| `keyword` | string | 否 | 地块名称或编号关键词 |
| `user_id` | string | 否 | 用户 ID |

### 成功响应示例

```json
{
  "items": [
    {
      "plot_id": "plot_001",
      "plot_name": "宿迁一号田",
      "region_name": "宿城区示范镇",
      "risk_level": "medium",
      "latest_record_id": "rec_001"
    }
  ],
  "total": 1
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

- 空列表显示“暂无地块数据”。
- `risk_level` 使用统一风险标签，不要直接裸显示英文。

## 13. 第二阶段可选：获取地块详情

### 接口

GET `/api/mobile/plots/{plot_id}`

### 稳定性

`stable`

### 用途

用于移动端地块详情页展示地块摘要、最新记录、风险状态和告警。

### Path 参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `plot_id` | string | 地块 ID |

### 成功响应示例

```json
{
  "plot_id": "plot_001",
  "plot_name": "宿迁一号田",
  "region_name": "宿城区示范镇",
  "risk_level": "medium",
  "latest_record": {
    "record_id": "rec_001",
    "main_disease": "疑似白叶枯",
    "result_image_url": "/static/results/rec_001.jpg"
  },
  "alerts": []
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "记录不存在",
  "detail": {
    "plot_id": "plot_001"
  }
}
```

### 前端处理建议

- `image_url` / `result_image_url` 若为相对路径，使用 `BASE_URL` 拼接。
- 地块不存在时返回列表页或展示空态。

## 14. 第二阶段可选：UAV 异常区手机复查

### 接口

POST `/api/uav/abnormal-regions/{region_id}/phone-followup`

### 稳定性

`preview`

### 用途

用于移动端围绕 UAV 异常区域上传近景图，形成多源协同证据并回写异常区。

### Path 参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `region_id` | string | UAV 异常区域 ID |

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
  "image_id": "img_phone_001",
  "uav_task_id": "uav_001",
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
  "error_code": "RECORD_NOT_FOUND",
  "message": "异常区域不存在",
  "detail": {
    "region_id": "region_001"
  }
}
```

### 前端处理建议

- 仅在选择异常区后开放复查按钮。
- 复查成功后刷新异常区详情，读取 `linked_phone_image_id`、`linked_record_id`、`confirmed_disease_type`、`confirm_status`。

## 15. 第二阶段可选：获取移动端告警

### 接口

GET `/api/mobile/alerts`

### 稳定性

`stable`

### 用途

用于移动端展示待处理风险告警。

### 成功响应示例

```json
{
  "items": [
    {
      "alert_id": "alert_001",
      "plot_id": "plot_001",
      "plot_name": "宿迁一号田",
      "risk_level": "high",
      "status": "active",
      "message": "该地块出现高风险识别记录，建议复核。"
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

- 高风险告警置顶。
- 告警建议是巡检提示，不是最终诊断。
