from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.dashboard import DashboardSummary
from app.schemas.detection_result import DetectionResult
from app.services.storage.result_store import result_store


client = TestClient(app)


def make_record(
    plot_id: str,
    disease: str | None,
    severity: str,
    risk_level: str,
    lng: float | None = None,
    lat: float | None = None,
) -> DetectionResult:
    suffix = uuid4().hex[:8]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    detections = []
    if disease:
        detections = [
            {
                "class_id": 0,
                "label": disease,
                "confidence": 0.88,
                "bbox": [10, 10, 120, 120],
                "area_ratio": 0.12,
            }
        ]
    return DetectionResult(
        record_id=f"rec_dash_{suffix}",
        image_id=f"img_dash_{suffix}",
        plot_id=plot_id,
        plot_name=f"{plot_id} name",
        region_name="\u672a\u6307\u5b9a\u4e61\u9547",
        timestamp=timestamp,
        image_url=f"/static/original/img_dash_{suffix}.jpg",
        result_image_url=f"/static/result/img_dash_{suffix}.jpg",
        image_width=320,
        image_height=240,
        source_type="manual_upload",
        model_name="mock_disease_detector",
        model_version="mock-v1",
        detector_mode="mock",
        current_target_type="disease" if disease else None,
        geo={"lng": lng, "lat": lat},
        detections=detections,
        summary={
            "disease_count": len(detections),
            "main_disease": disease,
            "max_confidence": 0.88 if disease else 0.0,
            "severity": severity,
            "risk_level": risk_level,
        },
        suggestion={
            "title": "test",
            "content": "test",
            "need_expert_confirm": bool(disease),
        },
    )


def save_dashboard_fixture() -> tuple[DetectionResult, DetectionResult]:
    medium = make_record("plot_B_01", "\u7a3b\u761f\u75c5", "\u4e2d\u5ea6", "medium")
    high = make_record("plot_stage3_high", "\u7a3b\u98de\u8671", "\u91cd\u5ea6", "high", lng=118.2, lat=33.2)
    result_store.save(medium)
    result_store.save(high)
    return medium, high


def test_dashboard_summary_empty_shape(monkeypatch):
    class EmptyDashboard:
        def summary(self):
            return DashboardSummary(
                today_detect_count=0,
                total_record_count=0,
                disease_record_count=0,
                normal_record_count=0,
                high_risk_plot_count=0,
                medium_risk_plot_count=0,
                low_risk_plot_count=0,
                risk_level_counts={"normal": 0, "low": 0, "medium": 0, "high": 0},
                severity_counts={"\u65e0\u75c5": 0, "\u8f7b\u5ea6": 0, "\u4e2d\u5ea6": 0, "\u91cd\u5ea6": 0},
                top_diseases=[],
                latest_alerts=[],
                latest_records=[],
            )

    from app.api import dashboard_api

    monkeypatch.setattr(dashboard_api, "dashboard_service", EmptyDashboard())
    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_record_count"] == 0
    assert payload["latest_alerts"] == []
    assert payload["latest_records"] == []


def test_dashboard_summary_plots_heatmap_and_disease_statistics():
    medium, high = save_dashboard_fixture()

    summary = client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["total_record_count"] >= 2
    assert "risk_level_counts" in summary_payload
    assert "severity_counts" in summary_payload
    assert "top_diseases" in summary_payload

    plots = client.get("/api/dashboard/plots", params={"risk_level": "medium"})
    assert plots.status_code == 200
    plot_items = plots.json()["items"]
    assert any(item["plot_id"] == medium.plot_id for item in plot_items)

    heatmap = client.get("/api/dashboard/heatmap", params={"risk_level": "medium"})
    assert heatmap.status_code == 200
    points = heatmap.json()["points"]
    fallback_point = next(item for item in points if item["plot_id"] == "plot_B_01")
    assert fallback_point["lng"] == 118.123456
    assert fallback_point["lat"] == 33.123456
    assert fallback_point["intensity"] == 0.6
    assert fallback_point["color"] == "#f59e0b"

    disease_stats = client.get("/api/dashboard/disease-statistics")
    assert disease_stats.status_code == 200
    labels = {item["label"] for item in disease_stats.json()["items"]}
    assert "\u7a3b\u761f\u75c5" in labels
    assert "\u7a3b\u98de\u8671" in labels

    latest_records = client.get("/api/dashboard/latest-records", params={"limit": 5})
    assert latest_records.status_code == 200
    assert latest_records.json()["items"]

    latest_alerts = client.get("/api/dashboard/latest-alerts", params={"limit": 20})
    assert latest_alerts.status_code == 200
    alerts = latest_alerts.json()["items"]
    assert any(item["record_id"] == high.record_id for item in alerts)
    assert all(item["risk_level"] in {"medium", "high"} for item in alerts)
