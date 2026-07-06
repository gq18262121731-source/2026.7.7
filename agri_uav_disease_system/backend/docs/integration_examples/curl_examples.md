# Curl Examples

The backend is still in Mock mode by default. These examples are for integration and demonstration.

```bash
BASE_URL=http://127.0.0.1:8000
```

## Status

```bash
curl "$BASE_URL/api/status"
curl "$BASE_URL/api/models/status"
```

## Seed Demo Data

```bash
python -m app.scripts.seed_demo_data
python -m app.scripts.seed_demo_data --reset-demo-data
```

## Single Image Detection

```bash
curl -X POST "$BASE_URL/api/detect/image" \
  -F "file=@sample.jpg" \
  -F "plot_id=demo_plot" \
  -F "source_type=manual_upload"
```

Use `image_url` and `result_image_url` from the response to fetch images:

```bash
curl "$BASE_URL/static/original/xxx.jpg" --output original.jpg
curl "$BASE_URL/static/result/xxx_result.jpg" --output result.jpg
```

## Dashboard

```bash
curl "$BASE_URL/api/dashboard/summary"
curl "$BASE_URL/api/dashboard/plots"
curl "$BASE_URL/api/dashboard/heatmap"
curl "$BASE_URL/api/dashboard/disease-statistics"
curl "$BASE_URL/api/dashboard/latest-records?limit=10"
curl "$BASE_URL/api/dashboard/latest-alerts?limit=10"
```

## Mobile

```bash
curl "$BASE_URL/api/mobile/overview?user_id=demo_user"
curl "$BASE_URL/api/mobile/plots?user_id=demo_user"
curl "$BASE_URL/api/mobile/alerts"
```

`user_id` is reserved for future ownership filtering. It currently does not enforce authentication or authorization.

## Alerts

```bash
curl "$BASE_URL/api/alerts"
curl "$BASE_URL/api/alerts/ALERT_ID"
curl -X POST "$BASE_URL/api/alerts/ALERT_ID/resolve" \
  -H "Content-Type: application/json" \
  -d '{"operator_id":"demo_user","operator_name":"演示用户","note":"已通知农技人员复核"}'
curl "$BASE_URL/api/alerts/ALERT_ID/actions"
```
