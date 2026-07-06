from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "agri_uav_disease_system" / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


client = TestClient(app)


def image_bytes() -> BytesIO:
    image = Image.new("RGB", (320, 240), color=(82, 154, 91))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def assert_status(name: str, response, expected: int = 200) -> dict:
    if response.status_code != expected:
        raise AssertionError(f"{name} expected {expected}, got {response.status_code}: {response.text}")
    payload = response.json()
    print(f"[PASS] {name}")
    return payload


def main() -> None:
    field_id = f"SQ_FIELD_P5_{uuid4().hex[:8]}"

    field = assert_status(
        "create field",
        client.post(
            "/api/fields",
            json={
                "field_id": field_id,
                "field_name": "宿迁 P5 验证田",
                "location_city": "宿迁市",
                "location_district": "宿城区",
                "location_town": "示范镇",
                "center_lat": 33.51,
                "center_lng": 118.48,
                "current_growth_stage": "分蘖期",
                "notes": "P5 command-line verification",
            },
        ),
    )
    assert field["field_id"] == field_id

    fields = assert_status("list fields", client.get("/api/fields", params={"status": "active"}))
    assert any(item["field_id"] == field_id for item in fields["items"])

    task = assert_status(
        "create uav task",
        client.post(
            "/api/uav/tasks",
            json={
                "field_id": field_id,
                "task_name": "P5 UAV dry-run",
                "sensor_type": "multispectral",
                "data_mode": "dry_run",
                "growth_stage": "分蘖期",
                "weather_text": "命令行验证天气",
            },
        ),
    )
    task_id = task["uav_task_id"]
    assert task["data_mode"] == "dry_run"

    dry_run = assert_status(
        "run uav dry-run",
        client.post(
            f"/api/uav/tasks/{task_id}/dry-run",
            json={"field_id": field_id, "dry_run_profile": "moderate_abnormal"},
        ),
    )
    assert dry_run["data_mode"] == "dry_run"
    assert dry_run["is_mock"] is True
    assert {item["index_type"] for item in dry_run["indices"]} == {"ndvi", "ndre"}
    assert dry_run["abnormal_regions"]
    region_id = dry_run["abnormal_regions"][0]["region_id"]

    regions = assert_status("list abnormal regions", client.get(f"/api/uav/tasks/{task_id}/abnormal-regions"))
    assert any(item["region_id"] == region_id for item in regions["items"])

    followup = assert_status(
        "phone followup",
        client.post(
            f"/api/uav/abnormal-regions/{region_id}/phone-followup",
            files={"file": ("followup.png", image_bytes(), "image/png")},
            data={
                "field_id": field_id,
                "source_type": "phone_followup",
                "model_hint": "phone",
                "target_type": "disease",
            },
        ),
    )
    assert followup["field_id"] == field_id
    assert followup["uav_task_id"] == task_id
    assert followup["abnormal_region_id"] == region_id

    region = assert_status("get abnormal region detail", client.get(f"/api/uav/abnormal-regions/{region_id}"))
    assert region["linked_record_id"] == followup["record_id"]
    assert region["confirm_status"] in {"phone_confirmed", "phone_uncertain", "phone_rejected"}
    assert region["phone_inference"]["record_id"] == followup["record_id"]

    report = assert_status(
        "generate inspection report",
        client.post(
            "/api/inspection-reports/generate",
            json={"field_id": field_id, "uav_task_id": task_id, "include_rag": True, "include_risk": True},
        ),
    )
    assert report["field_id"] == field_id
    assert report["uav_task_id"] == task_id
    assert report["abnormal_region_summary"]["total"] >= 1
    assert report["phone_followup_summary"]["total"] >= 1
    assert "risk_score" in report["risk_summary"]
    assert "不替代农技人员现场诊断" in report["model_safety_note"]
    assert report["payload"]["model_boundary"]["formal_metric_available"] is False

    detail = assert_status("get inspection report detail", client.get(f"/api/inspection-reports/{report['report_id']}"))
    assert detail["report_id"] == report["report_id"]

    print(
        json.dumps(
            {
                "field_id": field_id,
                "uav_task_id": task_id,
                "region_id": region_id,
                "followup_record_id": followup["record_id"],
                "report_id": report["report_id"],
                "safety_note_present": "不作为农药处方依据" in report["model_safety_note"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
