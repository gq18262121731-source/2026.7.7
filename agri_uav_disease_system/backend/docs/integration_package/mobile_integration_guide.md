# 移动端联调指南

面向手机端巡田、告警查看、图片上传、异常区复核。完整字段以 `api_contract_full.md` 和 `openapi.json` 为准。

## 必接接口

| 稳定性 | 方法 | 路径 | 用途 |
|---|---|---|---|
| stable | GET | `/api/mobile/overview` | 首页概览 |
| stable | GET | `/api/mobile/plots` | 地块列表 |
| stable | GET | `/api/mobile/plots/{plot_id}` | 地块详情 |
| stable | GET | `/api/mobile/records/{record_id}` | 识别记录详情 |
| stable | GET | `/api/mobile/alerts` | 移动端告警摘要 |
| stable | GET | `/api/mobile/suggestions/{record_id}` | 单条记录处置建议 |
| stable | POST | `/api/detect/image` | 手机拍照/相册图片识别 |
| stable | POST | `/api/uav/abnormal-regions/{region_id}/phone-followup` | 无人机异常区手机复核 |
| stable | GET | `/api/alerts` | 告警分页列表 |
| stable | GET | `/api/alerts/{alert_id}` | 告警详情 |
| stable | POST | `/api/alerts/{alert_id}/resolve` | 处理/关闭告警 |

## 推荐流程

1. 进入首页：`GET /api/mobile/overview?user_id=demo_user`
2. 查看地块：`GET /api/mobile/plots?user_id=demo_user`
3. 查看地块详情：`GET /api/mobile/plots/{plot_id}`
4. 拍照识别：`POST /api/detect/image`
5. 使用返回的 `record_id` 进入记录详情：`GET /api/mobile/records/{record_id}`
6. 若返回 `risk_level=medium` 或 `high`，进入告警列表/详情。
7. 处理完成后调用 `POST /api/alerts/{alert_id}/resolve`。

## 上传图片

`POST /api/detect/image` 使用 `multipart/form-data`：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `file` | 是 | 图片文件 |
| `plot_id` / `field_id` | 否 | 地块 ID |
| `plot_name` | 否 | 地块名 |
| `region_name` | 否 | 区域名 |
| `lng` / `lat` | 否 | 手机定位经纬度 |
| `source_type` | 否 | 手机端建议传 `phone_rgb` |

支持格式由后端配置决定，当前默认 `.jpg,.jpeg,.png,.webp`；最大上传大小默认 `15MB`。

## 静态图片 URL

当前后端返回的 `image_url`、`result_image_url` 多为相对路径，例如：

```json
{
  "image_url": "/static/original/img_001.jpg",
  "result_image_url": "/static/result/img_001_result.jpg"
}
```

移动端应使用 `BASE_URL + image_url` 拼接访问。正式对外部署时，建议网关或后端返回绝对 URL，减少多环境联调问题。

## 鉴权

联调阶段统一预留：

```http
Authorization: Bearer <TOKEN>
```

当前版本 `user_id` 是预留字段，不做真实权限过滤；正式环境必须由服务端鉴权决定用户可见地块和告警。

## 移动端注意事项

- 农事建议仅作辅助参考，不作为用药处方。
- `is_smoke=true`、`model_stage=experimental` 的结果需明显标注为演示/实验。
- 客户端展示风险时优先使用 `risk_level`，再展示 `severity` 和 `main_disease`。
- 上传后如果 WebSocket 未收到事件，仍以 HTTP 返回结果为准。
