# 大屏联调指南

面向驾驶舱、大屏热力图、实时滚动识别记录和告警。完整字段以 `api_contract_full.md` 和 `openapi.json` 为准。

## 必接接口

| 稳定性 | 方法 | 路径 | 用途 |
|---|---|---|---|
| stable | GET | `/api/dashboard/summary` | 大屏顶部统计概览 |
| stable | GET | `/api/dashboard/plots` | 地块风险统计 |
| stable | GET | `/api/dashboard/plots/{plot_id}` | 地块详情弹窗 |
| stable | GET | `/api/dashboard/plots/{plot_id}/records` | 地块识别记录 |
| stable | GET | `/api/dashboard/heatmap` | 热力图点位 |
| stable | GET | `/api/dashboard/disease-statistics` | 病害统计 |
| stable | GET | `/api/dashboard/latest-records` | 最新识别记录 |
| stable | GET | `/api/dashboard/latest-alerts` | 最新告警 |
| stable | WS | `/ws/results` | 实时识别结果 |
| stable | WS | `/ws/alerts` | 实时告警 |

## 推荐首屏加载顺序

1. `GET /api/dashboard/summary`
2. `GET /api/dashboard/heatmap`
3. `GET /api/dashboard/latest-records?limit=10`
4. `GET /api/dashboard/latest-alerts?limit=10`
5. 建立 `/ws/results` 和 `/ws/alerts`。

WebSocket 只负责实时提示。页面刷新、断线重连或进入页面时，必须通过 HTTP 补拉最新数据，避免漏事件。

## WebSocket 策略

- `/ws/results`：上传图片识别完成后广播完整 `DetectionResult`。
- `/ws/alerts`：新增或更新中高风险告警时广播 `alert_event`。
- 断线后建议 3 秒重连；连续失败时使用 3s、5s、10s、30s 退避。
- 重连成功后立即调用 `GET /api/dashboard/latest-records` 和 `GET /api/dashboard/latest-alerts` 补拉。
- 客户端可发送文本心跳，服务端当前主要用于维持连接和广播 JSON。

## 热力图说明

`GET /api/dashboard/heatmap` 返回：

- `lng`、`lat`：点位坐标。
- `intensity`：大屏展示强度，范围通常为 0-1。
- `color`：服务端建议色，不是模型指标。
- `risk_level`：业务风险等级，建议作为图例和筛选依据。

## 过滤参数

| 接口 | 参数 |
|---|---|
| `/api/dashboard/plots` | `region_name`、`risk_level`、`disease` |
| `/api/dashboard/heatmap` | `region_name`、`risk_level`、`disease` |
| `/api/dashboard/plots/{plot_id}/records` | `risk_level`、`severity`、`disease`、`start_time`、`end_time`、`page`、`page_size` |

## 展示注意事项

- `model_stage=mock`、`detector_mode=mock` 表示演示/Mock 结果，不应当展示成正式模型指标。
- `risk_probability_note` 或 `safety_note` 出现时，需在详情中提示“辅助参考”。
- 图片使用 `BASE_URL + result_image_url` 加载。

