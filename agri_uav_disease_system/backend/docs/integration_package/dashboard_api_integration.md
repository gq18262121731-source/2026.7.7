# 大屏接口联调说明

大屏以只读展示为主，WebSocket 只做实时通知。收到推送后应通过 HTTP 补拉最新记录或告警。

统一环境变量：

```bash
BASE_URL="https://test-api.example.com"
TOKEN="replace-with-your-token"
```

## 大屏接口总表

| 接口 | 稳定性 | 用途 |
|---|---|---|
| GET `/api/dashboard/summary` | stable | 总览数字 |
| GET `/api/dashboard/plots` | stable | 地块风险列表 |
| GET `/api/dashboard/plots/{plot_id}` | stable | 地块详情 |
| GET `/api/dashboard/heatmap` | stable | 地图热力点 |
| GET `/api/dashboard/disease-statistics` | stable | 病害统计 |
| GET `/api/dashboard/latest-records` | stable | 最新识别记录 |
| GET `/api/dashboard/latest-alerts` | stable | 最新告警 |
| WS `/ws/results` | preview | 新识别事件 |
| WS `/ws/alerts` | preview | 新告警事件 |

## 1. 获取总览数字

### 接口

GET `/api/dashboard/summary`

### 稳定性

`stable`

### 用途

用于大屏首页展示检测数量、风险分布、告警数量和记录总量。

### 请求 Header

```http
Authorization: Bearer <TOKEN>
```

### 请求参数

无。

### 成功响应示例

```json
{
  "today_detect_count": 12,
  "total_record_count": 236,
  "disease_record_count": 58,
  "normal_record_count": 178,
  "high_risk_plot_count": 2,
  "medium_risk_plot_count": 6,
  "low_risk_plot_count": 18,
  "risk_level_counts": {
    "high": 2,
    "medium": 6,
    "low": 18
  }
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "服务端内部错误",
  "detail": {}
}
```

### 前端处理建议

- 数字为空时显示 `0`。
- 定时轮询建议 30 到 60 秒。
- WebSocket 事件到达后可立即刷新。

## 2. 获取地块风险列表

### 接口

GET `/api/dashboard/plots`

### 稳定性

`stable`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `risk_level` | string | 否 | 风险等级 |
| `region_name` | string | 否 | 区域名称 |

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

- 地图和列表共用该接口。
- 风险等级统一映射颜色，不要直接依赖后端颜色字段。

## 3. 获取地块详情

### 接口

GET `/api/dashboard/plots/{plot_id}`

### 稳定性

`stable`

### 成功响应示例

```json
{
  "plot_id": "plot_001",
  "plot_name": "宿迁一号田",
  "risk_level": "medium",
  "latest_record": {
    "record_id": "rec_001",
    "main_disease": "疑似白叶枯"
  },
  "records_count": 12
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "RECORD_NOT_FOUND",
  "message": "地块不存在",
  "detail": {}
}
```

### 前端处理建议

- 详情弹窗打开时调用。
- 失败时关闭详情或显示空态。

## 4. 获取热力图

### 接口

GET `/api/dashboard/heatmap`

### 稳定性

`stable`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `risk_level` | string | 否 | 风险过滤 |

### 成功响应示例

```json
{
  "points": [
    {
      "plot_id": "plot_001",
      "lng": 118.48,
      "lat": 33.51,
      "risk_level": "medium",
      "intensity": 0.65
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

- 坐标缺失的点不要绘制。
- 热力值仅用于态势展示，不代表正式发病概率。

## 5. 获取病害统计

### 接口

GET `/api/dashboard/disease-statistics`

### 稳定性

`stable`

### 成功响应示例

```json
{
  "items": [
    {
      "disease_name": "疑似白叶枯",
      "count": 8,
      "risk_level": "medium"
    }
  ]
}
```

### 失败响应示例

```json
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "服务端内部错误",
  "detail": {}
}
```

### 前端处理建议

- 图表为空时显示“暂无病害统计”。
- 名称为 `null` 时显示“未识别到明确病害”。

## 6. 获取最新识别记录

### 接口

GET `/api/dashboard/latest-records`

### 稳定性

`stable`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | integer | 否 | 默认 10，建议 1-50 |

### 成功响应示例

```json
{
  "items": [
    {
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "main_disease": "疑似白叶枯",
      "risk_level": "medium",
      "result_image_url": "/static/results/rec_001.jpg",
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

- WebSocket `/ws/results` 收到事件后调用该接口补拉。
- 图片 URL 相对路径需拼接 `BASE_URL`。

## 7. 获取最新告警

### 接口

GET `/api/dashboard/latest-alerts`

### 稳定性

`stable`

### Query 参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `limit` | integer | 否 | 默认 10，建议 1-50 |

### 成功响应示例

```json
{
  "items": [
    {
      "alert_id": "alert_001",
      "record_id": "rec_001",
      "plot_name": "宿迁一号田",
      "risk_level": "high",
      "message": "该地块出现高风险识别记录，建议复核。",
      "timestamp": "2026-07-06T10:31:00"
    }
  ]
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

- WebSocket `/ws/alerts` 收到事件后调用该接口补拉。
- 高风险告警置顶或闪烁提示，但不要写成正式诊断。

## WebSocket 与 HTTP 补拉策略

WebSocket 只推 JSON 事件，不传图片、不传 base64、不传视频帧。

| 事件来源 | 收到后建议 |
|---|---|
| `/ws/results` | 调用 `/api/dashboard/latest-records` |
| `/ws/alerts` | 调用 `/api/dashboard/latest-alerts` |
| `/ws/tasks` | 调用 `/api/tasks/{task_id}` |

断线后客户端应自动重连。重连成功后，先通过 HTTP 补拉最新数据，不依赖 WebSocket 保存历史。
