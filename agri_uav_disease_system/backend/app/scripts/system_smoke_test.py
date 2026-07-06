from __future__ import annotations

import anyio
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.database.database import check_database, init_db
from app.main import app
from app.schemas.detection_result import DetectionResult
from app.services.alert_service import alert_service
from app.services.storage.file_storage import file_storage_service
from app.services.storage.result_store import result_store


def _pass(name: str) -> None:
    print(f"[PASS] {name}")


def _assert_response(name: str, response, expected_status: int = 200) -> dict:
    if response.status_code != expected_status:
        raise RuntimeError(f"{name} failed: status={response.status_code}, body={response.text[:500]}")
    _pass(name)
    try:
        return response.json()
    except ValueError:
        return {}


def _image_bytes() -> BytesIO:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), color=(120, 170, 110)).save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def _alert_record() -> DetectionResult:
    suffix = uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return DetectionResult(
        record_id=f"smoke_rec_{suffix}",
        image_id=f"smoke_img_{suffix}",
        plot_id=f"smoke_plot_{suffix}",
        plot_name="Smoke Test Plot",
        region_name="未指定乡镇",
        timestamp=now,
        image_url=f"/static/original/smoke_img_{suffix}.jpg",
        result_image_url=f"/static/result/smoke_img_{suffix}.jpg",
        image_width=320,
        image_height=240,
        source_type="manual_upload",
        model_name="mock_disease_detector",
        model_version="mock-v1",
        detector_mode="mock",
        current_target_type="disease",
        geo={"lng": 118.5, "lat": 33.5},
        detections=[{"class_id": 0, "label": "稻飞虱", "confidence": 0.9, "bbox": [10, 10, 160, 160], "area_ratio": 0.2}],
        summary={"disease_count": 1, "main_disease": "稻飞虱", "max_confidence": 0.9, "severity": "重度", "risk_level": "high"},
        suggestion={
            "title": "smoke",
            "content": "smoke",
            "need_expert_confirm": True,
            "actions": ["现场复查"],
            "knowledge_tags": ["稻飞虱"],
            "disclaimer": "本建议为辅助参考，具体用药和处置方案需由农技人员确认。",
        },
    )


def main() -> None:
    init_db()
    client = TestClient(app)

    assert app is not None
    _pass("FastAPI app import")
    if check_database() != "ok":
        raise RuntimeError("SQLite check failed")
    _pass("SQLite")
    if file_storage_service.check_storage() != "ok":
        raise RuntimeError("Static storage is not writable")
    _pass("static dirs writable")

    _assert_response("healthz", client.get("/healthz"))
    _assert_response("api status", client.get("/api/status"))

    detect = _assert_response(
        "detect image",
        client.post(
            "/api/detect/image",
            files={"file": ("smoke.jpg", _image_bytes(), "image/jpeg")},
            data={"plot_id": f"smoke_plot_{uuid4().hex[:8]}", "source_type": "manual_upload"},
        ),
    )
    original = _assert_response("static original", client.get(detect["image_url"]))
    result = _assert_response("static result", client.get(detect["result_image_url"]))
    _ = original, result
    _assert_response("record detail", client.get(f"/api/records/{detect['record_id']}"))
    _assert_response("dashboard summary", client.get("/api/dashboard/summary"))
    _assert_response("mobile overview", client.get("/api/mobile/overview"))

    record = _alert_record()
    result_store.save(record)
    alert = anyio.run(alert_service.handle_detection_result, record)
    if not alert:
        raise RuntimeError("Alert was not generated for high-risk smoke record")
    _pass("alert generated")
    _assert_response("alerts", client.get("/api/alerts"))

    for path, name in [("/ws/results", "ws results"), ("/ws/tasks", "ws tasks"), ("/ws/alerts", "ws alerts")]:
        with client.websocket_connect(path):
            _pass(name)


if __name__ == "__main__":
    main()
