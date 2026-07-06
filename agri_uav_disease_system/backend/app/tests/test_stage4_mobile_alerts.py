from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas.detection_result import DetectionResult
from app.services.alert_service import alert_service
from app.services.realtime.websocket_manager import alert_websocket_manager
from app.services.storage.result_store import result_store


client = TestClient(app)


def make_image_bytes(color: tuple[int, int, int] = (120, 170, 110)) -> BytesIO:
    image = Image.new("RGB", (320, 240), color=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def make_record(plot_id: str, disease: str, severity: str, risk_level: str) -> DetectionResult:
    suffix = uuid4().hex[:8]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return DetectionResult(
        record_id=f"rec_stage4_{suffix}",
        image_id=f"img_stage4_{suffix}",
        plot_id=plot_id,
        plot_name=f"{plot_id} name",
        region_name="\u672a\u6307\u5b9a\u4e61\u9547",
        timestamp=timestamp,
        image_url=f"/static/original/img_stage4_{suffix}.jpg",
        result_image_url=f"/static/result/img_stage4_{suffix}.jpg",
        image_width=320,
        image_height=240,
        source_type="manual_upload",
        model_name="mock_disease_detector",
        model_version="mock-v1",
        detector_mode="mock",
        current_target_type="disease",
        geo={"lng": 118.5, "lat": 33.5},
        detections=[
            {
                "class_id": 0,
                "label": disease,
                "confidence": 0.9,
                "bbox": [10, 10, 160, 160],
                "area_ratio": 0.2,
            }
        ],
        summary={
            "disease_count": 1,
            "main_disease": disease,
            "max_confidence": 0.9,
            "severity": severity,
            "risk_level": risk_level,
        },
        suggestion={
            "title": "test",
            "content": "test",
            "need_expert_confirm": True,
            "actions": ["a"],
            "knowledge_tags": [disease],
            "disclaimer": "d",
        },
    )


def test_dashboard_plot_detail_and_records():
    record = make_record("plot_stage4_detail", "\u7a3b\u761f\u75c5", "\u4e2d\u5ea6", "medium")
    result_store.save(record)

    detail = client.get(f"/api/dashboard/plots/{record.plot_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["plot_id"] == record.plot_id
    assert payload["record_count"] >= 1
    assert payload["main_disease"] == "\u7a3b\u761f\u75c5"
    assert payload["latest_record"]["record_id"] == record.record_id

    records = client.get(f"/api/dashboard/plots/{record.plot_id}/records")
    assert records.status_code == 200
    assert records.json()["total"] >= 1


def test_mobile_overview_plots_plot_detail_and_record_detail():
    record = make_record("plot_stage4_mobile", "\u7a3b\u98de\u8671", "\u91cd\u5ea6", "high")
    result_store.save(record)

    overview = client.get("/api/mobile/overview")
    assert overview.status_code == 200
    assert "summary_text" in overview.json()

    plots = client.get("/api/mobile/plots", params={"keyword": "plot_stage4_mobile"})
    assert plots.status_code == 200
    assert any(item["plot_id"] == record.plot_id for item in plots.json()["items"])

    plot_detail = client.get(f"/api/mobile/plots/{record.plot_id}")
    assert plot_detail.status_code == 200
    assert plot_detail.json()["plot_id"] == record.plot_id
    assert "suggestion" in plot_detail.json()

    record_detail = client.get(f"/api/mobile/records/{record.record_id}")
    assert record_detail.status_code == 200
    assert record_detail.json()["record_id"] == record.record_id


async def create_alert(record: DetectionResult):
    result_store.save(record)
    return await alert_service.handle_detection_result(record)


def test_alert_generation_cooldown_and_upgrade():
    plot_id = f"plot_stage4_alert_{uuid4().hex[:8]}"
    medium = make_record(plot_id, "\u7a3b\u761f\u75c5", "\u4e2d\u5ea6", "medium")
    medium_again = make_record(plot_id, "\u7a3b\u761f\u75c5", "\u4e2d\u5ea6", "medium")
    high = make_record(plot_id, "\u7a3b\u761f\u75c5", "\u91cd\u5ea6", "high")

    alert1 = anyio.run(create_alert, medium)
    assert alert1 is not None
    assert alert1.risk_level == "medium"

    alert2 = anyio.run(create_alert, medium_again)
    assert alert2 is not None
    assert alert2.alert_id == alert1.alert_id

    alert3 = anyio.run(create_alert, high)
    assert alert3 is not None
    assert alert3.risk_level == "high"
    assert alert3.alert_id == alert1.alert_id
    assert alert3.latest_record_id == high.record_id

    alerts = client.get("/api/alerts", params={"plot_id": plot_id, "page_size": 10})
    assert alerts.status_code == 200
    assert alerts.json()["total"] == 1

    detail = client.get(f"/api/alerts/{alert3.alert_id}")
    assert detail.status_code == 200
    assert detail.json()["alert_id"] == alert3.alert_id

    resolved = client.post(f"/api/alerts/{alert3.alert_id}/resolve")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_alert_websocket_receives_alert_event():
    record = make_record(f"plot_stage4_ws_{uuid4().hex[:8]}", "\u7a3b\u98de\u8671", "\u91cd\u5ea6", "high")
    with client.websocket_connect("/ws/alerts") as websocket:
        assert alert_websocket_manager.client_count >= 1
        event_detail = anyio.run(create_alert, record)
        assert event_detail is not None
        event = websocket.receive_json()
        assert event["type"] == "alert_event"
        assert event["plot_id"] == record.plot_id
        assert "latest_record_id" in event
    assert alert_websocket_manager.client_count == 0


def test_new_error_shapes_for_missing_mobile_and_alert_resources():
    mobile = client.get("/api/mobile/records/not_exists")
    assert mobile.status_code == 400
    assert mobile.json()["success"] is False

    alert = client.get("/api/alerts/not_exists")
    assert alert.status_code == 400
    assert alert.json()["error_code"] == "ALERT_NOT_FOUND"
