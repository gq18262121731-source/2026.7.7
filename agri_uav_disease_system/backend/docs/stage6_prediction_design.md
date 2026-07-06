# Stage 6.1 Prediction Design

Stage 6.1 adds a minimal rule-based disease and pest risk prediction loop on top of the v0.5 Mock integration baseline.

Scope:
- No model training.
- No real YOLO connection.
- No real weather API.
- No real sensor, UAV SDK, or map service.
- No full frontend page.
- No claimed accuracy, AUC, F1, or calibrated probability.

Pipeline:
1. Operators manually record weather, growth stage, and farm operations.
2. The backend reads historical detection records for a plot.
3. `FeatureBuilder` builds historical, weather, growth, operation, and active-alert features.
4. `RiskRuleModel` scores future 3, 7, or 14 day risk.
5. The result can be saved to `risk_predictions`.
6. Dashboard and mobile endpoints read saved prediction results.
7. Medium and high prediction results can create `alert_source=prediction` alerts.

The current model is `rule_based` / `risk-rule-v0.1`.

`risk_probability` is only `risk_score / 100`. It is a normalized rule score and does not represent a real statistical probability.
