from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.main import app


client = TestClient(app)


def make_image_bytes() -> BytesIO:
    image = Image.new("RGB", (320, 240), color=(84, 145, 92))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def upload(source_type: str, extra: dict[str, str] | None = None) -> dict:
    data = {"source_type": source_type, "plot_id": f"demo_safety_{uuid4().hex[:8]}"}
    if extra:
        data.update(extra)
    response = client.post(
        "/api/detect/image",
        files={"file": ("demo.jpg", make_image_bytes(), "image/jpeg")},
        data=data,
    )
    assert response.status_code == 200
    return response.json()


def test_models_status_and_demo_safety_include_experimental_display_rules():
    status = client.get("/api/models/status")
    assert status.status_code == 200
    payload = status.json()
    assert set(payload["models"].keys()) == {
        "phone_model",
        "phone_experimental_model",
        "uav_crop_model",
        "uav_blb_model",
        "uav_blb_experimental_model",
        "mock_model",
    }
    assert payload["models"]["uav_crop_model"]["current_target_type"] == "crop_object"
    assert payload["models"]["uav_crop_model"]["capability_level"] == "auxiliary_smoke_only"
    assert payload["models"]["uav_blb_model"]["current_target_type"] == "disease"
    assert payload["models"]["phone_model"]["formal_metric_available"] is False

    phone_exp_model = payload["models"]["phone_experimental_model"]
    assert phone_exp_model["model_stage"] == "experimental"
    assert phone_exp_model["is_smoke"] is False
    assert phone_exp_model["formal_metric_available"] is False
    assert phone_exp_model["current_target_type"] == "disease"
    assert phone_exp_model["category_type"] == "disease"
    assert phone_exp_model["capability_level"] == "experimental_only"
    assert phone_exp_model["dataset_images"] == 7575
    assert phone_exp_model["dataset_bbox"] == 69769
    assert phone_exp_model["healthy_excluded"] is True
    assert phone_exp_model["class_mapping_strategy"] == "source_directory_based_remap"
    assert "Healthy" not in phone_exp_model["class_codes"]

    exp_model = payload["models"]["uav_blb_experimental_model"]
    assert exp_model["model_stage"] == "experimental"
    assert exp_model["is_smoke"] is False
    assert exp_model["formal_metric_available"] is False
    assert exp_model["current_target_type"] == "disease"
    assert exp_model["category_type"] == "disease"
    assert exp_model["capability_level"] == "experimental_only"
    assert exp_model["dataset_actual_images"] == 408
    assert exp_model["dataset_target_name"] == "preview_1000"
    assert exp_model["is_true_multichannel_model"] is False

    assert "demo_safety" in payload
    assert payload["demo_safety"]["has_formal_models"] is False
    assert payload["demo_safety"]["formal_metric_available"] is False
    assert "uav_with_model_hint_uav_blb_exp" in payload["active_routing"]
    assert "phone_rgb_with_model_hint_phone_exp" in payload["active_routing"]

    safety = client.get("/api/models/demo-safety")
    assert safety.status_code == 200
    safety_payload = safety.json()
    assert safety_payload["demo_safe"] is True
    assert safety_payload["has_formal_models"] is False
    assert any("crop_object" in rule for rule in safety_payload["display_rules"])
    assert any("experimental" in rule for rule in safety_payload["display_rules"])


def test_upload_routes_return_model_warnings_and_experimental_fields():
    phone = upload("phone_rgb")
    assert phone["model_name"] in {"phone_rice_disease_yolo", "mock_disease_detector"}
    assert phone["model_capability_level"] in {"smoke_only", "mock_only"}
    assert phone["model_warning"]

    default_mock = settings.detector_mode.lower() == "mock"

    uav_crop = upload("uav_rgb")
    if default_mock:
        assert uav_crop["model_name"] == "mock_disease_detector"
        assert uav_crop["fallback_to_mock"] is True
        assert uav_crop["model_capability_level"] == "mock_only"
    else:
        assert uav_crop["model_name"] == "uav_rice_disease_yolo"
        assert uav_crop["current_target_type"] == "crop_object"
        assert uav_crop["model_capability_level"] == "auxiliary_smoke_only"
        assert "crop_object" in uav_crop["model_warning"]

    uav_blb = upload("uav_multispectral", {"model_hint": "uav_blb", "target_type": "disease"})
    if default_mock:
        assert uav_blb["model_name"] == "mock_disease_detector"
        assert uav_blb["fallback_to_mock"] is True
        assert uav_blb["model_capability_level"] == "mock_only"
    else:
        assert uav_blb["model_name"] == "uav_blb_disease_yolo"
        assert uav_blb["current_target_type"] == "disease"
        assert uav_blb["model_capability_level"] == "smoke_only"
    assert uav_blb["model_hint"] == "uav_blb"
    assert uav_blb["target_type"] == "disease"

    phone_exp = upload("phone_rgb", {"model_hint": "phone_exp", "model_stage_hint": "experimental"})
    if default_mock:
        assert phone_exp["model_name"] == "mock_disease_detector"
        assert phone_exp["fallback_to_mock"] is True
        assert phone_exp["model_capability_level"] == "mock_only"
    else:
        assert phone_exp["model_name"] == "phone_rice_disease_yolo"
        assert phone_exp["model_version"] == "experimental_riceleafdiseasebd_3epoch_20260623"
        assert phone_exp["model_stage"] == "experimental"
        assert phone_exp["is_smoke"] is False
        assert phone_exp["formal_metric_available"] is False
        assert phone_exp["model_capability_level"] == "experimental_only"
        assert phone_exp["current_target_type"] == "disease"
        assert phone_exp["category_type"] == "disease"

    uav_blb_exp = upload("uav_multispectral", {"model_hint": "uav_blb_exp", "model_stage_hint": "experimental"})
    if default_mock:
        assert uav_blb_exp["model_name"] == "mock_disease_detector"
        assert uav_blb_exp["fallback_to_mock"] is True
        assert uav_blb_exp["model_capability_level"] == "mock_only"
    else:
        assert uav_blb_exp["model_name"] == "uav_blb_disease_yolo"
        assert uav_blb_exp["model_version"] == "experimental_preview408_epoch5_20260623"
        assert uav_blb_exp["model_stage"] == "experimental"
        assert uav_blb_exp["is_smoke"] is False
        assert uav_blb_exp["formal_metric_available"] is False
        assert uav_blb_exp["model_capability_level"] == "experimental_only"
        assert uav_blb_exp["current_target_type"] == "disease"
        assert uav_blb_exp["category_type"] == "disease"


def test_mock_fallback_warning_is_stable(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.services.inference.model_manager import model_manager

    original_detector = model_manager.uav_blb_experimental_detector
    original_path = settings.uav_blb_experimental_model_path
    try:
        settings.uav_blb_experimental_model_path = str(tmp_path / "missing.pt")
        model_manager.uav_blb_experimental_detector = model_manager._build_uav_blb_experimental_detector()
        payload = upload("uav_multispectral", {"model_hint": "uav_blb_exp", "model_stage_hint": "experimental"})
        assert payload["model_name"] == "mock_disease_detector"
        assert payload["fallback_to_mock"] is True
        assert payload["model_capability_level"] == "mock_only"
        assert payload["model_warning"]
    finally:
        settings.uav_blb_experimental_model_path = original_path
        model_manager.uav_blb_experimental_detector = original_detector



def test_phone_experimental_mock_fallback_warning_is_stable(tmp_path):
    from app.core.config import settings
    from app.services.inference.model_manager import model_manager

    original_phone_detector = model_manager.phone_experimental_detector
    original_phone_path = settings.phone_experimental_model_path
    try:
        settings.phone_experimental_model_path = str(tmp_path / "missing_phone_exp.pt")
        model_manager.phone_experimental_detector = model_manager._build_phone_experimental_detector()
        payload = upload("phone_rgb", {"model_hint": "phone_exp", "model_stage_hint": "experimental"})
        assert payload["model_name"] == "mock_disease_detector"
        assert payload["fallback_to_mock"] is True
        assert payload["model_capability_level"] == "mock_only"
        assert payload["model_warning"]
    finally:
        settings.phone_experimental_model_path = original_phone_path
        model_manager.phone_experimental_detector = original_phone_detector
