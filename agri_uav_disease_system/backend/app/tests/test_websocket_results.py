from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.realtime.websocket_manager import websocket_manager


def make_image_bytes() -> BytesIO:
    image = Image.new("RGB", (320, 240), color=(100, 150, 90))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def test_websocket_receives_detection_result_and_disconnects():
    client = TestClient(app)
    with client.websocket_connect("/ws/results") as websocket:
        assert websocket_manager.client_count >= 1
        response = client.post(
            "/api/detect/image",
            files={"file": ("ws_rice.jpg", make_image_bytes(), "image/jpeg")},
            data={"source_type": "manual_upload"},
        )
        assert response.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "detection_result"
        assert event["record_id"] == response.json()["record_id"]
        for field in ["type", "record_id", "image_url", "result_image_url", "detections", "summary", "suggestion"]:
            assert field in event
    assert websocket_manager.client_count == 0
