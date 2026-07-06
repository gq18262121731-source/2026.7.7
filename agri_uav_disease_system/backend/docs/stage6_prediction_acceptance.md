# Stage 6.1 Prediction Acceptance

Implemented backend scope:
- Weather observation manual recording and query.
- Growth stage manual recording, basic inference, and query.
- Farm operation recording and query.
- Rule-based plot prediction for 3, 7, and 14 day windows.
- Saved prediction results in `risk_predictions`.
- Dashboard prediction summary and risk map.
- Mobile prediction list and plot prediction detail.
- Prediction alerts for medium/high prediction results.
- `alert_source` distinguishes detection and prediction alerts.
- `/ws/alerts` includes prediction alert metadata.

Database additions:
- `weather_observations`
- `plot_growth_stages`
- `farm_operations`
- `risk_predictions`

`alerts` additions:
- `alert_source TEXT DEFAULT 'detection'`
- `prediction_id TEXT`
- `prediction_window_days INTEGER`

Boundaries:
- No real model training.
- No real YOLO prediction model.
- No real weather API, sensors, UAV SDK, or map service.
- No formal accuracy, AUC, F1, or calibrated probability.
- No concrete pesticide dosage.
- WebSocket pushes JSON only.

Acceptance commands:

```bash
python -m compileall app
python -m pytest app/tests -q
python -m app.scripts.system_smoke_test
```
