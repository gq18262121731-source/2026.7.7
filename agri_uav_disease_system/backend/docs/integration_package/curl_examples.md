# Curl Examples

These examples are for external integration. Replace `BASE_URL` and `TOKEN` with values provided by the deployment owner.

```bash
BASE_URL=https://test-api.example.com
TOKEN=replace-with-your-token
```

## Status

```bash
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/healthz"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/status"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/models/status"
```

## Seed Demo Data

```bash
python -m app.scripts.seed_demo_data
python -m app.scripts.seed_demo_data --reset-demo-data
```

## Single Image Detection

```bash
curl -X POST "$BASE_URL/api/detect/image" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.jpg" \
  -F "plot_id=demo_plot" \
  -F "source_type=phone_rgb"
```

Use `image_url` and `result_image_url` from the response to fetch images:

```bash
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/static/original/xxx.jpg" --output original.jpg
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/static/result/xxx_result.jpg" --output result.jpg
```

## Dashboard

```bash
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/summary"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/plots"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/heatmap"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/disease-statistics"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/latest-records?limit=10"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/dashboard/latest-alerts?limit=10"
```

## Mobile

```bash
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/mobile/overview?user_id=demo_user"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/mobile/plots?user_id=demo_user"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/mobile/alerts"
```

`user_id` is reserved for future ownership filtering. It currently does not enforce authentication or authorization.

## Alerts

```bash
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/alerts"
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/alerts/ALERT_ID"
curl -X POST "$BASE_URL/api/alerts/ALERT_ID/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"operator_id":"demo_user","operator_name":"演示用户","note":"已通知农技人员复核"}'
curl -H "Authorization: Bearer $TOKEN" "$BASE_URL/api/alerts/ALERT_ID/actions"
```

## Notes

- 本机开发说明：后端本机调试可使用 `BASE_URL=http://127.0.0.1:8000`。
- Current mock backend may not enforce the `Authorization` header yet; external environments should enforce it.
- Current `image_url` and `result_image_url` may be relative URLs. Clients should resolve them against `BASE_URL`.
