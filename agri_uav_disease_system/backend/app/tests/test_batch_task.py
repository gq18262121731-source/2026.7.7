from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


client = TestClient(app)


def make_image_bytes(color: tuple[int, int, int]) -> BytesIO:
    image = Image.new("RGB", (320, 240), color=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def test_batch_detect_images_and_task_status():
    response = client.post(
        "/api/detect/batch",
        files=[
            ("files", ("batch_1.jpg", make_image_bytes((80, 150, 90)), "image/jpeg")),
            ("files", ("batch_2.jpg", make_image_bytes((90, 160, 100)), "image/jpeg")),
        ],
        data={"plot_id": "plot_batch_01", "source_type": "uav_rgb"},
    )
    assert response.status_code == 200
    created = response.json()
    assert created["task_id"].startswith("batch_")
    assert created["total_images"] == 2

    status_response = client.get(f"/api/tasks/{created['task_id']}")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "completed"
    assert status["processed_images"] == 2
    assert status["failed_images"] == 0
    assert status["progress"] == 1.0
    assert len(status["record_ids"]) == 2


def test_batch_detect_records_failed_item_for_invalid_image():
    response = client.post(
        "/api/detect/batch",
        files=[
            ("files", ("batch_good.jpg", make_image_bytes((120, 170, 110)), "image/jpeg")),
            ("files", ("batch_bad.jpg", BytesIO(b"not image"), "image/jpeg")),
        ],
        data={"plot_id": "plot_batch_02", "source_type": "manual_upload"},
    )
    assert response.status_code == 200
    created = response.json()

    status_response = client.get(f"/api/tasks/{created['task_id']}")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "partial_failed"
    assert status["processed_images"] == 2
    assert status["failed_images"] == 1
    assert status["progress"] == 1.0
    assert len(status["record_ids"]) == 1
    assert status["failed_items"][0]["error_code"] == "INVALID_IMAGE"


def test_batch_task_not_found_returns_unified_error():
    response = client.get("/api/tasks/not_exists")
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "TASK_NOT_FOUND"
