from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.realtime.websocket_manager import task_websocket_manager


def make_image_bytes(color: tuple[int, int, int]) -> BytesIO:
    image = Image.new("RGB", (320, 240), color=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def test_task_websocket_receives_batch_progress_events():
    client = TestClient(app)
    with client.websocket_connect("/ws/tasks") as websocket:
        assert task_websocket_manager.client_count >= 1
        response = client.post(
            "/api/detect/batch",
            files=[
                ("files", ("task_ws_1.jpg", make_image_bytes((80, 150, 90)), "image/jpeg")),
                ("files", ("task_ws_2.jpg", make_image_bytes((90, 160, 100)), "image/jpeg")),
            ],
            data={"plot_id": "plot_batch_01", "source_type": "uav_rgb"},
        )
        assert response.status_code == 200
        seen = []
        for _ in range(4):
            event = websocket.receive_json()
            seen.append(event)
            assert event["type"] == "task_status"
            assert event["task_id"] == response.json()["task_id"]
            if event["status"] == "completed":
                break
        assert any(event["status"] == "processing" for event in seen)
        assert seen[-1]["status"] == "completed"
        assert seen[-1]["progress"] == 1.0
    assert task_websocket_manager.client_count == 0
