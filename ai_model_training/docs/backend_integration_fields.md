# 后端接入字段说明

## 模型选择

| source_type | 使用模型 | 说明 |
| --- | --- | --- |
| `uav_rgb` | `uav_rice_disease_yolo` | 无人机 RGB 航拍 |
| `uav_multispectral` | `uav_rice_disease_yolo` | 多光谱伪 RGB 或指数图 |
| `uav_video_frame` | `uav_rice_disease_yolo` | 无人机视频抽帧 |
| `phone_rgb` | `phone_rice_disease_yolo` | 手机近距离 RGB 图片 |
| `manual_upload` | 由用户选择或根据来源判断 | 后端策略配置 |
| `unknown` | 默认 phone 模型或 Mock | 需记录回退原因 |

## 单个 detection 字段

```json
{
  "class_id": 0,
  "label": "稻瘟病",
  "confidence": 0.91,
  "bbox": [120, 80, 360, 280],
  "area_ratio": 0.067,
  "model_name": "phone_rice_disease_yolo",
  "model_version": "v1.0.0"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `class_id` | number | 与 `class_map.yaml` 一致 |
| `label` | string | 中文或后端统一展示名 |
| `confidence` | number | 模型置信度，0 到 1 |
| `bbox` | number[] | 像素坐标 `[x1, y1, x2, y2]` |
| `area_ratio` | number | 检测框面积占图片面积比例 |
| `model_name` | string | 模型名称 |
| `model_version` | string | 模型版本 |

## detection_result 字段

```json
{
  "type": "detection_result",
  "record_id": "rec_20260622_0001",
  "image_id": "img_20260622_0001",
  "source_type": "phone_rgb",
  "model_name": "phone_rice_disease_yolo",
  "model_version": "v1.0.0",
  "plot_id": "plot_B_01",
  "timestamp": "2026-06-22T10:30:00.000Z",
  "detections": [],
  "summary": {
    "disease_count": 0,
    "main_disease": null,
    "severity": "无病",
    "risk_level": "normal"
  }
}
```

## 回退策略

真实权重不存在或加载失败时：

- 自动回退 `MockDiseaseDetector`。
- 日志中记录回退原因、请求来源和模型路径。
- 接口保持可用，返回字段结构不变。
- 响应中可增加 `is_mock: true`，便于前端和测试识别。
