from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.schemas.experimental_uav_blb_segmentation import (
    UavBlbSegmentationFieldTrialRecord,
    UavBlbSegmentationFieldTrialResponse,
)
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


def make_field_trial_record() -> UavBlbSegmentationFieldTrialRecord:
    return UavBlbSegmentationFieldTrialRecord(
        trial_id="trial_test_001",
        plot_id="plot_field_01",
        plot_name="Field trial plot",
        tif_filename="sample.tif",
        model_name="uav_blb_segmentation_408_patch_v2_d2_ndvi_unet_baseline",
        model_sha256="62e9e88ee8778bdf4fa94547daa1395c6c1d49b4e6270af1b08062117057fb67",
        disease_area_ratio=0.125,
        mask_url="/static/experimental/uav_blb_field_trial_outputs/trial_test_001/mask.png",
        overlay_url="/static/experimental/uav_blb_field_trial_outputs/trial_test_001/overlay.jpg",
        probability_map_url="/static/experimental/uav_blb_field_trial_outputs/trial_test_001/probability_map.npy",
        original_preview_url="/static/experimental/uav_blb_field_trial_outputs/trial_test_001/original_preview.jpg",
        inference_time_ms=123,
        created_at="2026-07-05T00:00:00+00:00",
        operator_note="onsite controlled validation",
        human_review_status="pending",
        human_review_label=None,
        issue_tags=["boundary_error"],
    )


def test_field_trial_response_contract_and_isolation(monkeypatch: pytest.MonkeyPatch):
    before_counts = count_records_and_alerts()
    before_stats = client.get("/api/dashboard/disease-statistics").json()
    before_latest_alerts = client.get("/api/dashboard/latest-alerts").json()

    async def fake_field_trial_upload(*_args, **_kwargs):
        record = make_field_trial_record()
        return UavBlbSegmentationFieldTrialResponse(
            model_name=record.model_name,
            weight_sha256=record.model_sha256,
            disease_area_ratio=record.disease_area_ratio,
            mask_url=record.mask_url,
            overlay_url=record.overlay_url,
            probability_map_url=record.probability_map_url,
            original_preview_url=record.original_preview_url,
            trial_record=record,
        )

    monkeypatch.setattr(uav_blb_segmentation_dry_run_service, "field_trial_upload", fake_field_trial_upload)
    response = client.post(
        "/api/experimental/uav-blb-segmentation/field-trial",
        files={"file": ("sample.tif", BytesIO(b"fake tiff bytes"), "image/tiff")},
        data={"mode": "field_trial_only", "plot_id": "plot_field_01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["mode"] == "field_trial_only"
    assert payload["production_ready"] is False
    assert payload["backend_integration_allowed"] == "field_trial_only"
    assert payload["model_stage"] == "formal_candidate"
    assert payload["input_config"] == "D2_5BAND_NDVI"
    assert payload["weight_sha256"].startswith("62e9e88e")
    assert payload["patch_size"] == 256
    assert payload["stride"] == 128
    assert payload["threshold"] == 0.45
    assert payload["min_area"] == 128
    assert payload["warning"] == "field_trial_not_for_production"
    assert payload["trial_record"]["mode"] == "field_trial_only"
    assert payload["trial_record"]["production_ready"] is False
    assert payload["trial_record"]["human_review_status"] == "pending"

    assert count_records_and_alerts() == before_counts
    assert client.get("/api/dashboard/disease-statistics").json() == before_stats
    assert client.get("/api/dashboard/latest-alerts").json() == before_latest_alerts


def test_field_trial_rejects_rgb_without_fallback_to_detection_or_yolo():
    before = count_records_and_alerts()
    response = client.post(
        "/api/experimental/uav-blb-segmentation/field-trial",
        files={"file": ("rgb.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"mode": "field_trial_only"},
    )
    after = count_records_and_alerts()

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["mode"] == "field_trial_only"
    assert payload["error_code"] == "INVALID_MULTISPECTRAL_TIF"
    assert payload["production_ready"] is False
    assert payload["backend_integration_allowed"] == "field_trial_only"
    assert payload["warning"] == "field_trial_not_for_production"
    assert payload["detail"]["fallback_to_rgb_or_yolo"] is False
    assert after == before


def test_field_trial_records_and_exports_use_isolated_store(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(uav_blb_segmentation_dry_run_service, "field_trial_storage_root", tmp_path)
    monkeypatch.setattr(uav_blb_segmentation_dry_run_service, "field_trial_records_path", tmp_path / "records.jsonl")
    record = make_field_trial_record()
    uav_blb_segmentation_dry_run_service._append_field_trial_record(record)

    records_response = client.get("/api/experimental/uav-blb-segmentation/field-trial/records")
    assert records_response.status_code == 200
    records_payload = records_response.json()
    assert records_payload["success"] is True
    assert records_payload["mode"] == "field_trial_only"
    assert records_payload["production_ready"] is False
    assert records_payload["total"] == 1
    assert records_payload["records"][0]["trial_id"] == "trial_test_001"

    csv_response = client.get("/api/experimental/uav-blb-segmentation/field-trial/export.csv")
    assert csv_response.status_code == 200
    assert "trial_id" in csv_response.text
    assert "trial_test_001" in csv_response.text
    assert "boundary_error" in csv_response.text

    json_response = client.get("/api/experimental/uav-blb-segmentation/field-trial/export.json")
    assert json_response.status_code == 200
    json_payload = json_response.json()
    assert json_payload["mode"] == "field_trial_only"
    assert json_payload["total"] == 1


def test_detect_image_route_remains_available_without_field_trial_pollution():
    before = count_records_and_alerts()
    response = client.post(
        "/api/detect/image",
        files={"file": ("bad.txt", BytesIO(b"hello"), "text/plain")},
    )
    after = count_records_and_alerts()

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["error_code"] == "INVALID_IMAGE"
    assert after == before
