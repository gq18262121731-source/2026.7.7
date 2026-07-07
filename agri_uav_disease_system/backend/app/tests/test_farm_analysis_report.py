from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


client = TestClient(app)


def make_image_bytes() -> BytesIO:
    image = Image.new("RGB", (320, 240), color=(80, 160, 90))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def test_farm_analysis_report_generates_downloadable_pdf():
    detect_response = client.post(
        "/api/detect/image",
        files={"file": ("rice.jpg", make_image_bytes(), "image/jpeg")},
        data={
            "plot_id": "plot_farm_report_01",
            "plot_name": "农情报告测试地块",
            "region_name": "宿迁测试乡镇",
            "source_type": "phone_rgb",
        },
    )
    assert detect_response.status_code == 200
    record = detect_response.json()

    response = client.post(
        "/api/farm-analysis-reports/generate",
        json={
            "plot_id": "plot_farm_report_01",
            "record_id": record["record_id"],
            "crop": "rice",
            "include_weather": True,
            "include_history_days": 7,
            "report_type": "record_analysis",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["report_id"].startswith("farm_report_")
    assert payload["pdf_url"].startswith("/api/farm-analysis-reports/")
    assert payload["pdf_url"].endswith("/download")
    assert payload["preview_url"].endswith("/preview")
    assert payload["rag_available"] in {True, False}

    pdf_response = client.get(payload["pdf_url"])
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")

    preview_response = client.get(payload["preview_url"])
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"] == "application/pdf"

    history_response = client.get("/api/farm-analysis-reports", params={"plot_id": "plot_farm_report_01"})
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["total"] >= 1
    assert any(item["report_id"] == payload["report_id"] for item in history["items"])


def test_farm_analysis_report_without_record_uses_fallback():
    response = client.post(
        "/api/farm-analysis-reports/generate",
        json={
            "plot_id": "plot_missing_record",
            "crop": "rice",
            "include_weather": True,
            "include_history_days": 7,
            "report_type": "plot_analysis",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["fallback_used"] is True
    assert payload["weather_available"] is False


def test_legacy_farm_analysis_report_route_still_works():
    response = client.post(
        "/api/agent/farm-analysis-report",
        json={
            "plot_id": "plot_legacy_report",
            "crop": "rice",
            "include_weather": False,
            "include_history_days": 7,
            "report_type": "daily_summary",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["pdf_url"].startswith("/api/farm-analysis-reports/")
