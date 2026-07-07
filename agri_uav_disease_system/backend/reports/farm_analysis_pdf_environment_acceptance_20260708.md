# Farm Analysis PDF Environment Acceptance

Date: 2026-07-08

## Environment Steps

- Installed backend runtime dependencies with `pip install -r requirements.txt`.
- Installed Playwright Chromium with `python -m playwright install chromium`.
- Restarted backend with `uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload`.

## Generated Report

- Report ID: `farm_report_20260707_220637_46e0cb`
- Endpoint: `POST /api/farm-analysis-reports/generate`
- Preview URL: `/api/farm-analysis-reports/farm_report_20260707_220637_46e0cb/preview`
- Download URL: `/api/farm-analysis-reports/farm_report_20260707_220637_46e0cb/download`
- PDF size: `249384` bytes

## Acceptance Checklist

1. Formal PDF generation succeeded: yes.
2. Current report still uses fallback: no, `pdf_quality=official` and `pdf_fallback_used=false`.
3. Chromium installed: yes, `python -m playwright install chromium` completed successfully.
4. Third-party live weather returned real data: no. The current environment has no QWeather key/host and no Amap Web Service key configured.
5. Weather fallback works: yes. Weather failure returned `source=unavailable` and did not block report generation.
6. SVG charts display: yes. Generated HTML contains inline `<svg>` charts.
7. Detection image thumbnail displays: yes. Generated HTML contains the thumbnail image block.
8. `python -m compileall app`: passed.
9. `pytest app/tests/test_farm_analysis_report.py -q`: passed.
10. `npm run build`: passed.

## Notes

- The formal PDF path is active only when Playwright can launch Chromium.
- If Chromium is missing later, the API returns `pdf_quality=fallback` and `pdf_quality_note="PDF 生成使用兜底模板，非正式展示版。"`.
- Weather priority is QWeather first, Amap weather fallback, local weather observation fallback, then weather unavailable.
- To enable the first-priority weather service, configure `QWEATHER_API_KEY` / `QWEATHER_API_HOST` or `VITE_QWEATHER_API_KEY` / `VITE_QWEATHER_API_HOST`.
- To enable the second-priority fallback weather service, configure one of: `AMAP_WEATHER_KEY`, `GAODE_WEATHER_KEY`, or `AMAP_WEB_SERVICE_KEY`.
