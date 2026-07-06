# Prediction API Contract

## GET `/api/prediction/plots/{plot_id}`

Query:
- `window_days`: `3`, `7`, or `14`; default `7`.
- `disease`: optional disease label.
- `save`: default `true`.
- `create_alert`: default `true`.

Invalid `window_days` returns the common error structure with `error_code=INVALID_PREDICTION_WINDOW`.

Response example:

```json
{
  "plot_id": "plot_B_01",
  "prediction_window_days": 7,
  "prediction_time": "2026-06-23T10:00:00.000Z",
  "risk_score": 76,
  "risk_probability": 0.76,
  "risk_probability_note": "当前为规则分数归一化值，不代表真实统计概率。",
  "risk_level": "high",
  "predicted_diseases": [{"label": "稻瘟病", "probability": 0.76}],
  "main_factors": ["最近 7 天存在高风险识别记录"],
  "suggestion": {
    "title": "未来 7 天存在较高病虫害风险",
    "content": "建议加强田间巡查，关注湿度、通风和积水情况，具体防治方案需由农技人员确认。",
    "need_expert_confirm": true,
    "actions": ["加强田间巡查", "关注田间湿度和积水情况", "必要时联系农技人员复核"],
    "knowledge_tags": ["风险预测", "稻瘟病", "田间巡查"],
    "disclaimer": "本建议为辅助参考，具体防治方案和用药剂量需由农技人员确认。"
  },
  "model": {
    "type": "rule_based",
    "version": "risk-rule-v0.1",
    "metrics": {
      "prediction_accuracy": "未指定",
      "auc": "未指定",
      "f1_score": "未指定"
    }
  },
  "prediction_id": "pred_001"
}
```

## GET `/api/prediction/dashboard/summary`

Returns high/medium plot counts, top risk plots, top predicted diseases, and risk factor counts.

## GET `/api/prediction/risk-map`

Returns saved prediction points for dashboard map display. Color and intensity are display hints, not model metrics.

## GET `/api/mobile/predictions`

Returns saved predictions sorted with medium/high risk first.

## GET `/api/mobile/plots/{plot_id}/prediction`

Returns the latest saved prediction for the plot. If none exists, the backend creates a default 7 day prediction without creating an alert.

## Prediction Alert WebSocket

`WS /ws/alerts` may push:

```json
{
  "type": "alert_event",
  "alert_source": "prediction",
  "alert_id": "alert_pred_001",
  "plot_id": "plot_B_01",
  "risk_level": "high",
  "message": "预测未来 7 天存在高风险病虫害风险，请及时关注。",
  "prediction_id": "pred_001",
  "prediction_window_days": 7
}
```

WebSocket pushes JSON only. It does not push images, base64, or video frames.
