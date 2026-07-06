from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

np = pytest.importorskip("numpy")
tifffile = pytest.importorskip("tifffile")

from app.main import app
from app.services.alert_service import alert_service
from app.services.storage.result_store import result_store


client = TestClient(app)


def make_5band_tif_bytes() -> BytesIO:
    rng = np.random.default_rng(20260705)
    arr = rng.integers(100, 5000, size=(64, 64, 5), dtype=np.uint16)
    buffer = BytesIO()
    tifffile.imwrite(buffer, arr)
    buffer.seek(0)
    return buffer


def make_jpeg_bytes() -> BytesIO:
    image = Image.new("RGB", (64, 64), color=(80, 160, 90))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def count_records_and_alerts() -> tuple[int, int]:
    records = result_store.count_records()
    _, alerts = alert_service.list_alerts(page=1, page_size=1)
    return records, alerts


def test_uav_blb_segmentation_v1_creates_formal_record_without_alert_pollution():
    before_records, before_alerts = count_records_and_alerts()
    before_latest_alerts = client.get("/api/dashboard/latest-alerts").json()
    before_disease_stats = client.get("/api/dashboard/disease-statistics").json()

    response = client.post(
        "/api/detect/uav-blb-segmentation",
        files={"file": ("release_5band.tif", make_5band_tif_bytes(), "image/tiff")},
        data={
            "plot_id": "release_plot_001",
            "plot_name": "Release test plot",
            "region_name": "Release test region",
            "human_review_status": "reviewed",
            "human_review_label": "acceptable",
            "issue_tags": "acceptable,boundary_error",
            "reviewer_note": "v1.0 release API test",
        },
    )
    after_records, after_alerts = count_records_and_alerts()
    after_latest_alerts = client.get("/api/dashboard/latest-alerts").json()
    after_disease_stats = client.get("/api/dashboard/disease-statistics").json()

    assert response.status_code == 200
    payload = response.json()
    assert after_records == before_records + 1
    assert after_alerts == before_alerts
    assert after_latest_alerts == before_latest_alerts
    assert after_disease_stats == before_disease_stats

    assert payload["source_type"] == "uav_multispectral"
    assert payload["task_type"] == "blb_segmentation"
    assert payload["result_type"] == "segmentation_mask"
    assert payload["disease_name"] == "bacterial_leaf_blight"
    assert payload["model_version"] == "uav_blb_ms_seg_v1.0"
    assert payload["model_stage"] == "initial_release_testing"
    assert payload["model_sha256"] == "62e9e88ee8778bdf4fa94547daa1395c6c1d49b4e6270af1b08062117057fb67"
    assert payload["input_config"] == "D2_5BAND_NDVI"
    assert payload["threshold"] == 0.45
    assert payload["min_area"] == 128
    assert payload["disease_area_ratio"] is not None
    assert payload["mask_url"].startswith("/static/result/uav_blb_ms_seg_v1_0/")
    assert payload["overlay_url"].startswith("/static/result/uav_blb_ms_seg_v1_0/")
    assert payload["probability_map_url"].startswith("/static/result/uav_blb_ms_seg_v1_0/")
    assert payload["production_scope"] == "record_and_visualization_only"
    assert payload["human_review_required"] is True
    assert payload["human_review_status"] == "reviewed"
    assert payload["human_review_label"] == "acceptable"
    assert "boundary_error" in payload["issue_tags"]
    assert payload["alerting_enabled"] is False
    assert payload["latest_alerts_enabled"] is False
    assert payload["active_model_version"] == "uav_blb_ms_seg_v1.0"
    assert payload["current_target_type"] == "blb_segmentation"
    assert payload["summary"]["risk_level"] == "normal"

    record_response = client.get(f"/api/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["record_id"] == payload["record_id"]
    assert record["model_version"] == "uav_blb_ms_seg_v1.0"
    assert record["task_type"] == "blb_segmentation"
    assert record["result_type"] == "segmentation_mask"
    assert record["human_review_required"] is True


def test_uav_blb_segmentation_v1_rejects_rgb_without_fallback_or_alerts():
    before = count_records_and_alerts()
    response = client.post(
        "/api/detect/uav-blb-segmentation",
        files={"file": ("rgb.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"plot_id": "release_plot_rgb"},
    )
    after = count_records_and_alerts()

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_MULTISPECTRAL_TIF"
    assert payload["production_ready"] is True
    assert payload["production_scope"] == "record_and_visualization_only"
    assert payload["alerting_enabled"] is False
    assert payload["latest_alerts_enabled"] is False
    assert payload["fallback_to_rgb_or_yolo"] is False
    assert after == before


def test_uav_blb_segmentation_v1_rejects_invalid_human_review_label():
    response = client.post(
        "/api/detect/uav-blb-segmentation",
        files={"file": ("release_5band.tif", make_5band_tif_bytes(), "image/tiff")},
        data={"human_review_label": "not_allowed_label"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "INVALID_HUMAN_REVIEW_LABEL"
    assert "acceptable" in payload["detail"]["allowed_labels"]
    assert "major_failure" in payload["detail"]["allowed_labels"]
