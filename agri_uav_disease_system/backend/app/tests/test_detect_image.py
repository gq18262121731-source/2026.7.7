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


def test_detect_image_endpoint_record_query_and_static_urls():
    response = client.post(
        "/api/detect/image",
        files={"file": ("rice.jpg", make_image_bytes(), "image/jpeg")},
        data={
            "plot_id": "plot_test_01",
            "plot_name": "\u6d4b\u8bd5\u5730\u5757",
            "region_name": "\u6d4b\u8bd5\u4e61\u9547",
            "source_type": "phone_rgb",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "detection_result"
    assert payload["source_type"] == "phone_rgb"
    assert payload["model_name"] in {"mock_disease_detector", "phone_rice_disease_yolo"}
    assert payload["detector_mode"] in {"mock", "smoke"}
    assert "is_smoke" in payload
    assert "model_stage" in payload
    assert "formal_metric_available" in payload
    assert payload["image_url"].startswith("/static/original/")
    assert payload["result_image_url"].startswith("/static/result/")

    original_response = client.get(payload["image_url"])
    result_response = client.get(payload["result_image_url"])
    assert original_response.status_code == 200
    assert result_response.status_code == 200
    assert original_response.headers["content-type"] in {"image/jpeg", "image/png", "image/webp"}

    record_response = client.get(f"/api/records/{payload['record_id']}")
    assert record_response.status_code == 200
    assert record_response.json()["record_id"] == payload["record_id"]


def test_detect_image_with_field_id_keeps_old_plot_compatibility():
    field_id = "SQ_FIELD_DETECT_COMPAT"
    response = client.post(
        "/api/detect/image",
        files={"file": ("rice.jpg", make_image_bytes(), "image/jpeg")},
        data={
            "field_id": field_id,
            "region_name": "\u5bbf\u8fc1\u6d4b\u8bd5\u4e61\u9547",
            "source_type": "phone_rgb",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["field_id"] == field_id
    assert payload["plot_id"] == field_id

    record_response = client.get(f"/api/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["field_id"] == field_id
    assert record["plot_id"] == field_id


def test_records_list_endpoint_pagination_shape():
    response = client.get("/api/records?page=1&page_size=5&sort=created_at_desc")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload.keys()) == {"items", "total", "page", "page_size"}
    assert payload["page"] == 1
    assert payload["page_size"] == 5


def test_invalid_image_returns_unified_error():
    response = client.post(
        "/api/detect/image",
        files={"file": ("bad.jpg", BytesIO(b"not an image"), "image/jpeg")},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_IMAGE"


def test_empty_file_returns_unified_error():
    response = client.post(
        "/api/detect/image",
        files={"file": ("empty.jpg", BytesIO(b""), "image/jpeg")},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_IMAGE"


def test_unsupported_extension_returns_unified_error():
    response = client.post(
        "/api/detect/image",
        files={"file": ("bad.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_IMAGE"
