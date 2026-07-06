from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas.experimental_uav_blb_segmentation import UavBlbSegmentationDryRunResponse
from app.services.alert_service import alert_service
from app.services.experimental.uav_blb_segmentation_dry_run_service import uav_blb_segmentation_dry_run_service
from app.services.storage.result_store import result_store


client = TestClient(app)


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


def test_dry_run_rejects_rgb_without_fallback_to_detection_or_yolo():
    before = count_records_and_alerts()
    response = client.post(
        "/api/experimental/uav-blb-segmentation/dry-run",
        files={"file": ("rgb.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"mode": "dry_run_only"},
    )
    after = count_records_and_alerts()

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["mode"] == "dry_run_only"
    assert payload["error_code"] == "INVALID_MULTISPECTRAL_TIF"
    assert payload["production_ready"] is False
    assert payload["backend_integration_allowed"] == "dry_run_only"
    assert payload["warning"] == "experimental_dry_run_only_not_for_production"
    assert payload["detail"]["fallback_to_rgb_or_yolo"] is False
    assert after == before


def test_dry_run_response_contract_and_isolation(monkeypatch: pytest.MonkeyPatch):
    before = count_records_and_alerts()

    async def fake_dry_run_upload(*_args, **_kwargs):
        return UavBlbSegmentationDryRunResponse(
            model_name="uav_blb_segmentation_408_patch_v2_d2_ndvi_unet_baseline",
            weight_sha256="62e9e88ee8778bdf4fa94547daa1395c6c1d49b4e6270af1b08062117057fb67",
            disease_area_ratio=0.125,
            mask_url="/static/experimental/uav_blb_segmentation_dry_run/test/mask.png",
            overlay_url="/static/experimental/uav_blb_segmentation_dry_run/test/overlay.jpg",
            probability_map_url="/static/experimental/uav_blb_segmentation_dry_run/test/probability_map.npy",
            original_preview_url="/static/experimental/uav_blb_segmentation_dry_run/test/original_preview.jpg",
        )

    monkeypatch.setattr(uav_blb_segmentation_dry_run_service, "dry_run_upload", fake_dry_run_upload)
    response = client.post(
        "/api/experimental/uav-blb-segmentation/dry-run",
        files={"file": ("sample.tif", BytesIO(b"fake tiff bytes"), "image/tiff")},
        data={"mode": "dry_run_only"},
    )
    after = count_records_and_alerts()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["mode"] == "dry_run_only"
    assert payload["production_ready"] is False
    assert payload["backend_integration_allowed"] == "dry_run_only"
    assert payload["model_stage"] == "formal_candidate"
    assert payload["input_config"] == "D2_5BAND_NDVI"
    assert payload["weight_sha256"].startswith("62e9e88e")
    assert payload["patch_size"] == 256
    assert payload["stride"] == 128
    assert payload["threshold"] == 0.45
    assert payload["min_area"] == 128
    assert payload["disease_area_ratio"] == 0.125
    assert payload["mask_url"].startswith("/static/experimental/uav_blb_segmentation_dry_run/")
    assert payload["overlay_url"].startswith("/static/experimental/uav_blb_segmentation_dry_run/")
    assert payload["probability_map_url"].startswith("/static/experimental/uav_blb_segmentation_dry_run/")
    assert payload["warning"] == "experimental_dry_run_only_not_for_production"
    assert after == before


def test_dry_run_requires_explicit_dry_run_mode():
    response = client.post(
        "/api/experimental/uav-blb-segmentation/dry-run",
        files={"file": ("sample.tif", BytesIO(b"fake tiff bytes"), "image/tiff")},
        data={"mode": "production"},
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_DRY_RUN_MODE"
    assert payload["production_ready"] is False
    assert payload["backend_integration_allowed"] == "dry_run_only"

