from __future__ import annotations

from io import BytesIO
from uuid import uuid4

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


def test_p1_field_crud_and_p2_p3_p4_inspection_loop():
    field_id = f"SQ_FIELD_{uuid4().hex[:8]}"

    created = client.post(
        "/api/fields",
        json={
            "field_id": field_id,
            "field_name": "宿迁一号田",
            "location_district": "宿城区",
            "location_town": "示范镇",
            "center_lat": 33.51,
            "center_lng": 118.48,
            "current_growth_stage": "分蘖期",
        },
    )
    assert created.status_code == 200
    assert created.json()["field_id"] == field_id

    listed = client.get("/api/fields", params={"status": "active"})
    assert listed.status_code == 200
    assert any(item["field_id"] == field_id for item in listed.json()["items"])

    detail = client.get(f"/api/fields/{field_id}")
    assert detail.status_code == 200
    assert detail.json()["field_name"] == "宿迁一号田"

    updated = client.put(
        f"/api/fields/{field_id}",
        json={"field_name": "宿迁一号田-更新", "current_growth_stage": "拔节期"},
    )
    assert updated.status_code == 200
    assert updated.json()["field_name"] == "宿迁一号田-更新"
    assert updated.json()["current_growth_stage"] == "拔节期"

    task = client.post(
        "/api/uav/tasks",
        json={
            "field_id": field_id,
            "task_name": "宿迁一号田多光谱巡检 dry-run",
            "sensor_type": "multispectral",
            "data_mode": "dry_run",
            "growth_stage": "拔节期",
            "weather_text": "阴天，湿度较高",
        },
    )
    assert task.status_code == 200
    uav_task_id = task.json()["uav_task_id"]

    dry_run = client.post(
        f"/api/uav/tasks/{uav_task_id}/dry-run",
        json={
            "field_id": field_id,
            "dry_run_profile": "moderate_abnormal",
            "growth_stage": "拔节期",
            "weather_text": "阴天，湿度较高",
        },
    )
    assert dry_run.status_code == 200
    dry_payload = dry_run.json()
    assert dry_payload["data_mode"] == "dry_run"
    assert dry_payload["is_mock"] is True
    assert len(dry_payload["indices"]) == 2
    assert {item["index_type"] for item in dry_payload["indices"]} == {"ndvi", "ndre"}
    assert len(dry_payload["abnormal_regions"]) >= 1
    region_id = dry_payload["abnormal_regions"][0]["region_id"]
    assert dry_payload["abnormal_regions"][0]["confirm_status"] == "phone_followup_pending"

    indices = client.get(f"/api/uav/tasks/{uav_task_id}/indices")
    assert indices.status_code == 200
    assert indices.json()["total"] == 2

    regions = client.get(f"/api/uav/tasks/{uav_task_id}/abnormal-regions")
    assert regions.status_code == 200
    assert regions.json()["total"] >= 1

    followup = client.post(
        f"/api/uav/abnormal-regions/{region_id}/phone-followup",
        files={"file": ("rice.jpg", make_image_bytes(), "image/jpeg")},
        data={"field_id": field_id, "source_type": "phone_followup", "target_type": "disease"},
    )
    assert followup.status_code == 200
    follow_payload = followup.json()
    assert follow_payload["field_id"] == field_id
    assert follow_payload["uav_task_id"] == uav_task_id
    assert follow_payload["abnormal_region_id"] == region_id
    assert follow_payload["source_type"] == "phone_followup"

    region_detail = client.get(f"/api/uav/abnormal-regions/{region_id}")
    assert region_detail.status_code == 200
    region_payload = region_detail.json()
    assert region_payload["linked_record_id"] == follow_payload["record_id"]
    assert region_payload["confirm_status"] in {"phone_confirmed", "phone_uncertain", "phone_rejected"}
    assert region_payload["phone_inference"]["record_id"] == follow_payload["record_id"]

    report = client.post(
        "/api/inspection-reports/generate",
        json={"field_id": field_id, "uav_task_id": uav_task_id, "include_rag": True, "include_risk": True},
    )
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["field_id"] == field_id
    assert report_payload["uav_task_id"] == uav_task_id
    assert report_payload["abnormal_region_summary"]["total"] >= 1
    assert report_payload["phone_followup_summary"]["total"] >= 1
    assert "risk_score" in report_payload["risk_summary"]
    assert report_payload["risk_model_detail"]["model_type"] == "rule_weighted_score"
    assert report_payload["risk_model_detail"]["probability_claim"] is False
    assert report_payload["risk_summary"]["risk_probability_note"] == "当前为规则分数归一化值，不代表真实统计概率。"
    assert "不替代农技人员现场诊断" in report_payload["model_safety_note"]
    assert report_payload["payload"]["model_boundary"]["formal_metric_available"] is False

    report_id = report_payload["report_id"]
    assert client.get(f"/api/inspection-reports/{report_id}").status_code == 200
    report_list = client.get("/api/inspection-reports", params={"field_id": field_id})
    assert report_list.status_code == 200
    assert any(item["report_id"] == report_id for item in report_list.json()["items"])


def test_normal_phone_detect_still_works_without_abnormal_region():
    response = client.post(
        "/api/detect/image",
        files={"file": ("rice.jpg", make_image_bytes(), "image/jpeg")},
        data={"source_type": "phone_rgb"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["abnormal_region_id"] is None
    assert payload["source_type"] == "phone_rgb"
