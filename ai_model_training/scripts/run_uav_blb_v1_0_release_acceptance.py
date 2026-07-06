from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import tifffile
from fastapi.testclient import TestClient
from PIL import Image


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = WORKSPACE_DIR / "agri_uav_disease_system" / "backend"
REPORT_PATH = (
    WORKSPACE_DIR
    / "ai_model_training"
    / "reports"
    / "uav_blb_segmentation_408_patch_v2_v1_0_release_acceptance_results.json"
)

sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.services.alert_service import alert_service  # noqa: E402
from app.services.storage.result_store import result_store  # noqa: E402


def make_5band_tif_bytes() -> BytesIO:
    rng = np.random.default_rng(20260705)
    arr = rng.integers(100, 5000, size=(64, 64, 5), dtype=np.uint16)
    buffer = BytesIO()
    tifffile.imwrite(buffer, arr)
    buffer.seek(0)
    return buffer


def make_jpeg_bytes() -> BytesIO:
    image = Image.new("RGB", (32, 32), color=(80, 160, 90))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def main() -> None:
    client = TestClient(app)

    before_records = result_store.count_records()
    _, before_alerts = alert_service.list_alerts(page=1, page_size=1)
    before_latest_alerts = client.get("/api/dashboard/latest-alerts").json()
    before_disease_statistics = client.get("/api/dashboard/disease-statistics").json()

    response = client.post(
        "/api/detect/uav-blb-segmentation",
        files={"file": ("release_acceptance_5band.tif", make_5band_tif_bytes(), "image/tiff")},
        data={
            "plot_id": "release_acceptance_plot_001",
            "plot_name": "UAV BLB v1.0 release acceptance plot",
            "region_name": "Release acceptance region",
            "human_review_status": "reviewed",
            "human_review_label": "acceptable",
            "issue_tags": "acceptable,boundary_error",
            "reviewer_note": "v1.0 initial release acceptance; not alerting",
        },
    )
    payload = response.json()
    after_records = result_store.count_records()
    _, after_alerts = alert_service.list_alerts(page=1, page_size=1)
    after_latest_alerts = client.get("/api/dashboard/latest-alerts").json()
    after_disease_statistics = client.get("/api/dashboard/disease-statistics").json()

    rgb_response = client.post(
        "/api/detect/uav-blb-segmentation",
        files={"file": ("rgb.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"plot_id": "release_acceptance_rgb"},
    )

    invalid_label_response = client.post(
        "/api/detect/uav-blb-segmentation",
        files={"file": ("release_acceptance_5band.tif", make_5band_tif_bytes(), "image/tiff")},
        data={"human_review_label": "not_allowed_label"},
    )

    record_response = client.get(f"/api/records/{payload.get('record_id')}")
    latest_records_response = client.get("/api/dashboard/latest-records", params={"limit": 5})

    result = {
        "release_endpoint_status_code": response.status_code,
        "release_payload": payload,
        "formal_records_before": before_records,
        "formal_records_after": after_records,
        "alerts_before": before_alerts,
        "alerts_after": after_alerts,
        "latest_alerts_unchanged": before_latest_alerts == after_latest_alerts,
        "disease_statistics_unchanged": before_disease_statistics == after_disease_statistics,
        "rgb_status_code": rgb_response.status_code,
        "rgb_payload": rgb_response.json(),
        "invalid_label_status_code": invalid_label_response.status_code,
        "invalid_label_payload": invalid_label_response.json(),
        "record_fetch_status_code": record_response.status_code,
        "record_fetch_payload": record_response.json(),
        "latest_records_status_code": latest_records_response.status_code,
        "latest_records_contains_release_record": any(
            item.get("record_id") == payload.get("record_id") for item in latest_records_response.json().get("items", [])
        ),
    }

    assert response.status_code == 200, result
    assert after_records == before_records + 1, result
    assert after_alerts == before_alerts, result
    assert before_latest_alerts == after_latest_alerts, result
    assert before_disease_statistics == after_disease_statistics, result
    assert payload["source_type"] == "uav_multispectral", result
    assert payload["task_type"] == "blb_segmentation", result
    assert payload["result_type"] == "segmentation_mask", result
    assert payload["disease_name"] == "bacterial_leaf_blight", result
    assert payload["model_version"] == "uav_blb_ms_seg_v1.0", result
    assert payload["model_stage"] == "initial_release_testing", result
    assert payload["production_scope"] == "record_and_visualization_only", result
    assert payload["human_review_required"] is True, result
    assert payload["alerting_enabled"] is False, result
    assert payload["latest_alerts_enabled"] is False, result
    assert payload["current_target_type"] == "blb_segmentation", result
    assert payload["summary"]["risk_level"] == "normal", result
    assert payload["mask_url"] and payload["overlay_url"] and payload["probability_map_url"], result
    assert record_response.status_code == 200, result
    assert record_response.json()["model_version"] == "uav_blb_ms_seg_v1.0", result
    assert rgb_response.status_code == 400, result
    assert rgb_response.json()["error_code"] == "INVALID_MULTISPECTRAL_TIF", result
    assert rgb_response.json()["fallback_to_rgb_or_yolo"] is False, result
    assert invalid_label_response.status_code == 400, result
    assert invalid_label_response.json()["error_code"] == "INVALID_HUMAN_REVIEW_LABEL", result

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
