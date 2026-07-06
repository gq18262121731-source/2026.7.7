from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.inference.model_manager import model_manager
from app.services.realtime.websocket_manager import websocket_manager


client = TestClient(app)
TRAINING_DIR = settings.training_dir
PHONE_SAMPLE = TRAINING_DIR / "datasets" / "rice_phone_rgb" / "images" / "val"
UAV_SAMPLE = TRAINING_DIR / "datasets" / "rice_uav_ms" / "images" / "val"
UAV_BLB_SAMPLE = TRAINING_DIR / "datasets" / "rice_uav_ms_blb_preview" / "images" / "val"
UAV_BLB_EXP_SAMPLE = TRAINING_DIR / "datasets" / "rice_uav_ms_blb_preview_1000" / "images" / "val"
PHONE_EXP_SAMPLE = TRAINING_DIR / "datasets" / "rice_phone_rgb_expanded" / "images" / "val"

pytestmark = pytest.mark.skipif(
    settings.detector_mode.lower() != "smoke",
    reason="Smoke YOLO integration tests run only when DETECTOR_MODE=smoke is explicitly enabled.",
)


def first_image(directory: Path) -> Path:
    for suffix in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        match = next(directory.glob(suffix), None)
        if match:
            return match
    raise AssertionError(f"no test image found in {directory}")


def upload_image(image_path: Path, source_type: str, extra_data: dict[str, str] | None = None) -> dict:
    data = {"plot_id": f"stage6_{source_type}", "source_type": source_type}
    if extra_data:
        data.update(extra_data)
    with image_path.open("rb") as file:
        response = client.post(
            "/api/detect/image",
            files={"file": (image_path.name, file, "image/jpeg")},
            data=data,
        )
    assert response.status_code == 200
    return response.json()


def assert_common_smoke_result(
    payload: dict,
    source_type: str,
    model_name: str,
    model_version: str = "smoke_epoch1_20260623",
) -> None:
    assert payload["type"] == "detection_result"
    assert payload["source_type"] == source_type
    assert payload["model_name"] == model_name
    assert payload["model_version"] == model_version
    assert payload["detector_mode"] == "smoke"
    assert payload["is_smoke"] is True
    assert payload["model_stage"] == "smoke"
    assert payload["formal_metric_available"] is False
    assert payload["fallback_to_mock"] is False
    assert payload["result_image_url"].startswith("/static/result/")
    assert client.get(payload["result_image_url"]).status_code == 200

    record_response = client.get(f"/api/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["record_id"] == payload["record_id"]
    assert record["is_smoke"] is True
    assert record["model_stage"] == "smoke"


def test_phone_smoke_yolo_api_sqlite_and_result_image():
    assert Path(settings.phone_model_path).exists()
    assert model_manager.smoke_status()["phone_smoke_loaded"] is True
    payload = upload_image(first_image(PHONE_SAMPLE), "phone_rgb")
    assert_common_smoke_result(payload, "phone_rgb", "phone_rice_disease_yolo")
    assert payload["current_target_type"] == "disease"


def test_uav_smoke_yolo_api_sqlite_and_result_image():
    assert Path(settings.uav_model_path).exists()
    assert model_manager.smoke_status()["uav_smoke_loaded"] is True
    payload = upload_image(first_image(UAV_SAMPLE), "uav_rgb")
    assert_common_smoke_result(payload, "uav_rgb", "uav_rice_disease_yolo")
    assert payload["current_target_type"] == "crop_object"


def test_uav_blb_smoke_yolo_api_sqlite_and_result_image():
    assert Path(settings.uav_blb_model_path).exists()
    assert model_manager.smoke_status()["uav_blb_smoke_loaded"] is True
    payload = upload_image(
        first_image(UAV_BLB_SAMPLE),
        "uav_multispectral",
        {"model_hint": "uav_blb", "target_type": "disease"},
    )
    assert_common_smoke_result(
        payload,
        "uav_multispectral",
        "uav_blb_disease_yolo",
        "smoke_epoch1_blb_20260623",
    )
    assert payload["current_target_type"] == "disease"
    for item in payload["detections"]:
        assert item["class_id"] == 0
        assert item["class_name"] == "bacterial_leaf_blight"
        assert item["category_type"] == "disease"
        assert item["class_code"] == "bacterial_leaf_blight"


def test_uav_without_hint_keeps_crop_object_route():
    payload = upload_image(first_image(UAV_SAMPLE), "uav_rgb")
    assert payload["model_name"] == "uav_rice_disease_yolo"
    assert payload["current_target_type"] == "crop_object"


def test_phone_route_not_affected_by_uav_blb():
    payload = upload_image(first_image(PHONE_SAMPLE), "phone_rgb")
    assert payload["model_name"] == "phone_rice_disease_yolo"
    assert payload["current_target_type"] == "disease"


def test_websocket_event_keeps_smoke_fields_for_phone():
    with client.websocket_connect("/ws/results") as websocket:
        assert websocket_manager.client_count >= 1
        payload = upload_image(first_image(PHONE_SAMPLE), "phone_rgb")
        event = websocket.receive_json()
        assert event["type"] == "detection_result"
        assert event["record_id"] == payload["record_id"]
        assert event["is_smoke"] is True
        assert event["model_stage"] == "smoke"
        assert event["formal_metric_available"] is False
        assert "detections" in event
        assert "summary" in event
        assert "suggestion" in event
    assert websocket_manager.client_count == 0


def test_websocket_event_keeps_uav_blb_fields():
    with client.websocket_connect("/ws/results") as websocket:
        assert websocket_manager.client_count >= 1
        payload = upload_image(
            first_image(UAV_BLB_SAMPLE),
            "uav_multispectral",
            {"model_hint": "uav_blb"},
        )
        event = websocket.receive_json()
        assert event["type"] == "detection_result"
        assert event["record_id"] == payload["record_id"]
        assert event["model_name"] == "uav_blb_disease_yolo"
        assert event["model_version"] == "smoke_epoch1_blb_20260623"
        assert event["current_target_type"] == "disease"
        assert event["formal_metric_available"] is False
        assert "detections" in event
        assert "summary" in event
        assert "suggestion" in event
    assert websocket_manager.client_count == 0


def test_uav_blb_weight_missing_falls_back_to_mock(tmp_path):
    original_detector = model_manager.uav_blb_detector
    original_path = settings.uav_blb_model_path
    try:
        settings.uav_blb_model_path = str(tmp_path / "missing_blb_best.pt")
        model_manager.uav_blb_detector = model_manager._build_uav_blb_detector()
        payload = upload_image(
            first_image(UAV_BLB_SAMPLE),
            "uav_multispectral",
            {"model_hint": "uav_blb"},
        )
        assert payload["model_name"] == "mock_disease_detector"
        assert payload["fallback_to_mock"] is True
        assert payload["current_target_type"] == "disease"
    finally:
        settings.uav_blb_model_path = original_path
        model_manager.uav_blb_detector = original_detector


def test_uav_blb_experimental_yolo_api_sqlite_and_result_image():
    assert Path(settings.uav_blb_experimental_model_path).exists()
    assert model_manager.smoke_status()["uav_blb_experimental_loaded"] is True
    payload = upload_image(
        first_image(UAV_BLB_EXP_SAMPLE),
        "uav_multispectral",
        {"model_hint": "uav_blb_exp", "model_stage_hint": "experimental", "target_type": "disease"},
    )
    assert payload["type"] == "detection_result"
    assert payload["model_name"] == "uav_blb_disease_yolo"
    assert payload["model_version"] == "experimental_preview408_epoch5_20260623"
    assert payload["detector_mode"] == "experimental"
    assert payload["model_stage"] == "experimental"
    assert payload["is_smoke"] is False
    assert payload["formal_metric_available"] is False
    assert payload["current_target_type"] == "disease"
    assert payload["category_type"] == "disease"
    assert payload["model_hint"] == "uav_blb_exp"
    assert payload["model_stage_hint"] == "experimental"
    assert payload["model_capability_level"] == "experimental_only"
    assert payload["fallback_to_mock"] is False
    assert payload["result_image_url"].startswith("/static/result/")
    assert client.get(payload["result_image_url"]).status_code == 200
    record_response = client.get(f"/api/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["model_stage"] == "experimental"
    assert record["model_capability_level"] == "experimental_only"
    for item in payload["detections"]:
        assert item["class_id"] == 0
        assert item["class_name"] == "bacterial_leaf_blight"
        assert item["class_code"] == "bacterial_leaf_blight"
        assert item["category_type"] == "disease"


def test_uav_blb_experimental_weight_missing_falls_back_to_mock(tmp_path):
    original_detector = model_manager.uav_blb_experimental_detector
    original_path = settings.uav_blb_experimental_model_path
    try:
        settings.uav_blb_experimental_model_path = str(tmp_path / "missing_exp_best.pt")
        model_manager.uav_blb_experimental_detector = model_manager._build_uav_blb_experimental_detector()
        payload = upload_image(
            first_image(UAV_BLB_EXP_SAMPLE),
            "uav_multispectral",
            {"model_hint": "uav_blb_exp", "model_stage_hint": "experimental"},
        )
        assert payload["model_name"] == "mock_disease_detector"
        assert payload["fallback_to_mock"] is True
        assert payload["current_target_type"] == "disease"
    finally:
        settings.uav_blb_experimental_model_path = original_path
        model_manager.uav_blb_experimental_detector = original_detector


def test_websocket_event_keeps_uav_blb_experimental_fields():
    with client.websocket_connect("/ws/results") as websocket:
        payload = upload_image(
            first_image(UAV_BLB_EXP_SAMPLE),
            "uav_multispectral",
            {"model_hint": "uav_blb_exp", "model_stage_hint": "experimental"},
        )
        event = websocket.receive_json()
        assert event["record_id"] == payload["record_id"]
        assert event["model_stage"] == "experimental"
        assert event["model_version"] == "experimental_preview408_epoch5_20260623"
        assert event["formal_metric_available"] is False
        assert event["model_capability_level"] == "experimental_only"
        assert event["current_target_type"] == "disease"




def test_phone_experimental_yolo_api_sqlite_and_result_image():
    assert Path(settings.phone_experimental_model_path).exists()
    assert model_manager.smoke_status()["phone_experimental_loaded"] is True
    payload = upload_image(
        first_image(PHONE_EXP_SAMPLE),
        "phone_rgb",
        {"model_hint": "phone_exp", "model_stage_hint": "experimental", "target_type": "disease"},
    )
    assert payload["type"] == "detection_result"
    assert payload["model_name"] == "phone_rice_disease_yolo"
    assert payload["model_version"] == "experimental_riceleafdiseasebd_3epoch_20260623"
    assert payload["detector_mode"] == "experimental"
    assert payload["model_stage"] == "experimental"
    assert payload["is_smoke"] is False
    assert payload["formal_metric_available"] is False
    assert payload["current_target_type"] == "disease"
    assert payload["category_type"] == "disease"
    assert payload["model_hint"] == "phone_exp"
    assert payload["model_stage_hint"] == "experimental"
    assert payload["model_capability_level"] == "experimental_only"
    assert payload["fallback_to_mock"] is False
    assert payload["result_image_url"].startswith("/static/result/")
    assert client.get(payload["result_image_url"]).status_code == 200
    record_response = client.get(f"/api/records/{payload['record_id']}")
    assert record_response.status_code == 200
    record = record_response.json()
    assert record["model_stage"] == "experimental"
    assert record["model_capability_level"] == "experimental_only"
    allowed = {"brown_spot", "rice_blast", "leaf_smut", "tungro", "sheath_blight"}
    forbidden = {"Healthy", "healthy", "normal", "background", "unknown", "uncertain"}
    for item in payload["detections"]:
        assert item["class_name"] in allowed
        assert item["class_name"] not in forbidden
        assert item["category_type"] == "disease"


def test_phone_experimental_weight_missing_falls_back_to_mock(tmp_path):
    original_detector = model_manager.phone_experimental_detector
    original_path = settings.phone_experimental_model_path
    try:
        settings.phone_experimental_model_path = str(tmp_path / "missing_phone_exp_best.pt")
        model_manager.phone_experimental_detector = model_manager._build_phone_experimental_detector()
        payload = upload_image(
            first_image(PHONE_EXP_SAMPLE),
            "phone_rgb",
            {"model_hint": "phone_exp", "model_stage_hint": "experimental"},
        )
        assert payload["model_name"] == "mock_disease_detector"
        assert payload["fallback_to_mock"] is True
        assert payload["current_target_type"] == "disease"
    finally:
        settings.phone_experimental_model_path = original_path
        model_manager.phone_experimental_detector = original_detector


def test_phone_default_route_does_not_switch_to_experimental():
    payload = upload_image(first_image(PHONE_SAMPLE), "phone_rgb")
    assert payload["model_name"] == "phone_rice_disease_yolo"
    assert payload["model_stage"] == "smoke"
    assert payload["is_smoke"] is True
    assert payload["model_version"] == "smoke_epoch1_20260623"


def test_websocket_event_keeps_phone_experimental_fields():
    with client.websocket_connect("/ws/results") as websocket:
        payload = upload_image(
            first_image(PHONE_EXP_SAMPLE),
            "phone_rgb",
            {"model_hint": "phone_exp", "model_stage_hint": "experimental"},
        )
        event = websocket.receive_json()
        assert event["record_id"] == payload["record_id"]
        assert event["model_name"] == "phone_rice_disease_yolo"
        assert event["model_stage"] == "experimental"
        assert event["model_version"] == "experimental_riceleafdiseasebd_3epoch_20260623"
        assert event["formal_metric_available"] is False
        assert event["model_capability_level"] == "experimental_only"
        assert event["current_target_type"] == "disease"
