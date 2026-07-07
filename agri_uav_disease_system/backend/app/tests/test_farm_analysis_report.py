from __future__ import annotations

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.report_storage_service import report_storage_service
from app.services.report_weather_service import report_weather_service


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
    assert payload["pdf_quality"] in {"official", "fallback"}
    if payload["pdf_fallback_used"]:
        assert payload["pdf_display_warning"] == "PDF 生成使用兜底模板，非正式展示版。"

    pdf_response = client.get(payload["pdf_url"])
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF")

    preview_response = client.get(payload["preview_url"])
    assert preview_response.status_code == 200
    assert preview_response.headers["content-type"] == "application/pdf"

    metadata = report_storage_service.get(payload["report_id"])
    assert metadata is not None
    html = Path(metadata.html_path).read_text(encoding="utf-8")
    assert "<svg" in html
    assert "证据来源构成图" in html
    assert "当前检测置信度横向柱状图" in html
    assert "检测图片缩略图" in html
    assert "模型信息表" in html
    assert metadata.weather_snapshot

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
    assert payload["pdf_display_warning"] in {None, "", "PDF 生成使用兜底模板，非正式展示版。"}


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


def test_report_weather_prefers_qweather(monkeypatch):
    monkeypatch.setattr(
        report_weather_service,
        "_qweather_live_weather",
        lambda: {
            "available": True,
            "source": "qweather",
            "provider_name": "和风天气",
            "temperature": "26 C",
            "humidity": "70%",
            "weather": "多云",
        },
    )
    monkeypatch.setattr(report_weather_service, "_amap_live_weather", lambda: (_ for _ in ()).throw(AssertionError("amap should not be called")))
    snapshot = report_weather_service.snapshot(True, "plot_001", None)
    assert snapshot["available"] is True
    assert snapshot["source"] == "qweather"
    assert snapshot["provider_name"] == "和风天气"
    assert snapshot["fallback_chain"] == ["qweather_success"]


def test_report_weather_falls_back_to_amap_after_qweather_failure(monkeypatch):
    monkeypatch.setattr(
        report_weather_service,
        "_qweather_live_weather",
        lambda: {"available": False, "source": "qweather", "provider_name": "和风天气", "message": "401"},
    )
    monkeypatch.setattr(
        report_weather_service,
        "_amap_live_weather",
        lambda: {
            "available": True,
            "source": "amap",
            "provider_name": "高德地图开放平台",
            "temperature": "27 C",
            "humidity": "68%",
            "weather": "晴",
        },
    )
    snapshot = report_weather_service.snapshot(True, "plot_001", None)
    assert snapshot["available"] is True
    assert snapshot["source"] == "amap"
    assert snapshot["provider_name"] == "高德地图开放平台"
    assert snapshot["fallback_chain"] == ["qweather_failed", "amap_success"]


def test_report_weather_unavailable_after_all_sources_fail(monkeypatch):
    monkeypatch.setattr(report_weather_service, "_qweather_live_weather", lambda: {"available": False, "source": "qweather"})
    monkeypatch.setattr(report_weather_service, "_amap_live_weather", lambda: {"available": False, "source": "amap"})
    monkeypatch.setattr(report_weather_service, "_local_weather", lambda plot_id, record: {"available": False, "source": "local_weather_observations"})
    snapshot = report_weather_service.snapshot(True, "plot_001", None)
    assert snapshot["available"] is False
    assert snapshot["source"] == "unavailable"
    assert snapshot["provider_name"] == "暂不可用"
    assert snapshot["message"] == "天气数据暂不可用，不影响本次检测记录分析。"
    assert snapshot["fallback_chain"] == ["qweather_failed", "amap_failed", "local_failed", "unavailable"]


def test_report_weather_falls_back_to_local_after_third_party_failure(monkeypatch):
    monkeypatch.setattr(report_weather_service, "_qweather_live_weather", lambda: {"available": False, "source": "qweather"})
    monkeypatch.setattr(report_weather_service, "_amap_live_weather", lambda: {"available": False, "source": "amap"})
    monkeypatch.setattr(
        report_weather_service,
        "_local_weather",
        lambda plot_id, record: {
            "available": True,
            "source": "local_weather_observations",
            "provider_name": "本地天气观测",
            "temperature": "25 C",
        },
    )
    snapshot = report_weather_service.snapshot(True, "plot_001", None)
    assert snapshot["available"] is True
    assert snapshot["source"] == "local_weather_observations"
    assert snapshot["provider_name"] == "本地天气观测"
    assert snapshot["fallback_chain"] == ["qweather_failed", "amap_failed", "local_success"]
