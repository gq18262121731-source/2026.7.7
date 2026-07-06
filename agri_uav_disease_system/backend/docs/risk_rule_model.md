# Risk Rule Model

The current prediction model is `rule_based` / `risk-rule-v0.1`.

It is a deterministic scoring model, not a trained model. It does not output formal prediction accuracy, AUC, F1, or calibrated probability.

`risk_probability = risk_score / 100` only normalizes the rule score. It is not a real statistical probability.

Scoring:
- Base score: `10`
- Same disease in last 30 days: `+20`
- Medium risk record in last 7 days: `+15`
- High risk record in last 7 days: `+25`
- Susceptible growth stage: `+15`
- High average humidity in last 3 weather records: `+15`
- Significant rainfall in last 3 weather records: `+10`
- No farm operation in last 7 days: `+10`
- Recent review, drainage, patrol, or management operation: `-10`
- Many active alerts: `+10`
- Continuous same disease: `+10`

Levels:
- `0-25`: `normal`
- `26-50`: `low`
- `51-75`: `medium`
- `76-100`: `high`

Missing weather, growth stage, or operation records are allowed. The model degrades gracefully and continues scoring with available features.

Suggestions never include pesticide dosage and never issue mandatory treatment commands.
