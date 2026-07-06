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
    / "uav_blb_segmentation_408_patch_v2_controlled_field_trial_system_acceptance_results.json"
)

sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402
from app.services.alert_service import alert_service  # noqa: E402
from app.services.experimental.uav_blb_segmentation_dry_run_service import (  # noqa: E402
    uav_blb_segmentation_dry_run_service,
)
from app.services.storage.result_store import result_store  # noqa: E402


def field_record_line_count() -> int:
    path = uav_blb_segmentation_dry_run_service.field_trial_records_path
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").splitlines())


def make_jpeg_bytes() -> BytesIO:
    image = Image.new("RGB", (32, 32), color=(80, 160, 90))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer


def make_5band_tif_bytes() -> BytesIO:
    rng = np.random.default_rng(20260705)
    arr = rng.integers(100, 5000, size=(64, 64, 5), dtype=np.uint16)
    buffer = BytesIO()
    tifffile.imwrite(buffer, arr)
    buffer.seek(0)
    return buffer


def main() -> None:
    client = TestClient(app)

    before_field_lines = field_record_line_count()
    before_records = result_store.count_records()
    _, before_alerts = alert_service.list_alerts(page=1, page_size=1)
    before_stats = client.get("/api/dashboard/disease-statistics").json()
    before_latest_alerts = client.get("/api/dashboard/latest-alerts").json()

    response = client.post(
        "/api/experimental/uav-blb-segmentation/field-trial",
        files={"file": ("acceptance_5band.tif", make_5band_tif_bytes(), "image/tiff")},
        data={
            "mode": "field_trial_only",
            "plot_id": "acceptance_plot_001",
            "plot_name": "Controlled acceptance synthetic 5-band TIF",
            "operator_note": "system acceptance synthetic 5-band TIF; not production data",
            "human_review_status": "reviewed",
            "human_review_label": "acceptable",
            "issue_tags": "acceptable,boundary_error",
        },
    )
    payload = response.json()
    after_field_lines = field_record_line_count()
    after_records = result_store.count_records()
    _, after_alerts = alert_service.list_alerts(page=1, page_size=1)
    after_stats = client.get("/api/dashboard/disease-statistics").json()
    after_latest_alerts = client.get("/api/dashboard/latest-alerts").json()

    rgb_response = client.post(
        "/api/experimental/uav-blb-segmentation/field-trial",
        files={"file": ("rgb.jpg", make_jpeg_bytes(), "image/jpeg")},
        data={"mode": "field_trial_only"},
    )

    bad_tif_response = client.post(
        "/api/experimental/uav-blb-segmentation/field-trial",
        files={"file": ("bad.tif", BytesIO(b"not a tif"), "image/tiff")},
        data={"mode": "field_trial_only"},
    )

    invalid_label_response = client.post(
        "/api/experimental/uav-blb-segmentation/field-trial",
        files={"file": ("acceptance_5band.tif", make_5band_tif_bytes(), "image/tiff")},
        data={"mode": "field_trial_only", "human_review_label": "not_allowed_label"},
    )

    records_response = client.get("/api/experimental/uav-blb-segmentation/field-trial/records")
    export_csv_response = client.get("/api/experimental/uav-blb-segmentation/field-trial/export.csv")
    export_json_response = client.get("/api/experimental/uav-blb-segmentation/field-trial/export.json")

    detect_invalid_before = result_store.count_records()
    detect_invalid_response = client.post(
        "/api/detect/image",
        files={"file": ("bad.txt", BytesIO(b"hello"), "text/plain")},
    )
    detect_invalid_after = result_store.count_records()

    result = {
        "field_trial_status_code": response.status_code,
        "field_trial_payload": payload,
        "field_record_lines_before": before_field_lines,
        "field_record_lines_after": after_field_lines,
        "formal_records_before": before_records,
        "formal_records_after": after_records,
        "alerts_before": before_alerts,
        "alerts_after": after_alerts,
        "disease_statistics_unchanged": before_stats == after_stats,
        "latest_alerts_unchanged": before_latest_alerts == after_latest_alerts,
        "rgb_status_code": rgb_response.status_code,
        "rgb_payload": rgb_response.json(),
        "bad_tif_status_code": bad_tif_response.status_code,
        "bad_tif_payload": bad_tif_response.json(),
        "invalid_label_status_code": invalid_label_response.status_code,
        "invalid_label_payload": invalid_label_response.json(),
        "records_status_code": records_response.status_code,
        "records_total": records_response.json().get("total"),
        "export_csv_status_code": export_csv_response.status_code,
        "export_csv_has_trial_id": "trial_id" in export_csv_response.text,
        "export_csv_contains_sensitive_env_key": any(
            token in export_csv_response.text for token in ["LLM_API_KEY", "LLM_", "API_KEY="]
        ),
        "export_json_status_code": export_json_response.status_code,
        "export_json_total": export_json_response.json().get("total"),
        "detect_invalid_status_code": detect_invalid_response.status_code,
        "detect_invalid_error_code": detect_invalid_response.json().get("error_code"),
        "detect_invalid_records_before": detect_invalid_before,
        "detect_invalid_records_after": detect_invalid_after,
    }

    record = payload.get("trial_record", {})
    required_record_keys = {
        "trial_id",
        "plot_id",
        "plot_name",
        "model_sha256",
        "threshold",
        "min_area",
        "disease_area_ratio",
        "mode",
        "production_ready",
        "created_at",
    }

    assert response.status_code == 200, result
    assert payload["mode"] == "field_trial_only", result
    assert payload["production_ready"] is False, result
    assert payload["model_stage"] == "formal_candidate", result
    assert payload["warning"] == "field_trial_not_for_production", result
    assert payload.get("disease_area_ratio") is not None, result
    assert payload.get("mask_url") and payload.get("overlay_url") and payload.get("probability_map_url"), result
    assert required_record_keys.issubset(record), result
    assert record["plot_id"] == "acceptance_plot_001", result
    assert record["human_review_status"] == "reviewed", result
    assert record["human_review_label"] == "acceptable", result
    assert "boundary_error" in record["issue_tags"], result
    assert after_field_lines == before_field_lines + 1, result
    assert after_records == before_records, result
    assert after_alerts == before_alerts, result
    assert before_stats == after_stats, result
    assert before_latest_alerts == after_latest_alerts, result
    assert rgb_response.status_code == 400, result
    assert rgb_response.json()["error_code"] == "INVALID_MULTISPECTRAL_TIF", result
    assert rgb_response.json()["detail"]["fallback_to_rgb_or_yolo"] is False, result
    assert bad_tif_response.status_code == 400, result
    assert bad_tif_response.json()["error_code"] == "INVALID_MULTISPECTRAL_TIF", result
    assert bad_tif_response.json()["mode"] == "field_trial_only", result
    assert bad_tif_response.json()["production_ready"] is False, result
    assert invalid_label_response.status_code == 400, result
    assert invalid_label_response.json()["error_code"] == "INVALID_HUMAN_REVIEW_LABEL", result
    assert records_response.status_code == 200, result
    assert export_csv_response.status_code == 200 and result["export_csv_has_trial_id"], result
    assert result["export_csv_contains_sensitive_env_key"] is False, result
    assert export_json_response.status_code == 200, result
    assert detect_invalid_response.status_code == 400, result
    assert detect_invalid_response.json()["error_code"] == "INVALID_IMAGE", result
    assert detect_invalid_after == detect_invalid_before, result

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
