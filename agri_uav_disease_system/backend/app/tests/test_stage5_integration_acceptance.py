from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient

from app.main import app
from app.scripts.seed_demo_data import seed_demo_data
from app.scripts.system_smoke_test import main as smoke_main
from app.schemas.detection_result import DetectionResult
from app.services.alert_service import alert_service
from app.services.storage.result_store import result_store


client = TestClient(app)


def make_high_record() -> DetectionResult:
    suffix = uuid4().hex[:8]
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return DetectionResult(
        record_id=f"rec_stage5_{suffix}",
        image_id=f"img_stage5_{suffix}",
        plot_id=f"plot_stage5_{suffix}",
        plot_name="stage5 plot",
        region_name="未指定乡镇",
        timestamp=timestamp,
        image_url=f"/static/original/img_stage5_{suffix}.jpg",
        result_image_url=f"/static/result/img_stage5_{suffix}.jpg",
        image_width=320,
        image_height=240,
        source_type="manual_upload",
        model_name="mock_disease_detector",
        model_version="mock-v1",
        detector_mode="mock",
        current_target_type="disease",
        geo={"lng": 118.5, "lat": 33.5},
        detections=[{"class_id": 0, "label": "稻飞虱", "confidence": 0.9, "bbox": [10, 10, 160, 160], "area_ratio": 0.2}],
        summary={"disease_count": 1, "main_disease": "稻飞虱", "max_confidence": 0.9, "severity": "重度", "risk_level": "high"},
        suggestion={
            "title": "test",
            "content": "test",
            "need_expert_confirm": True,
            "actions": ["现场复查"],
            "knowledge_tags": ["稻飞虱"],
            "disclaimer": "本建议为辅助参考，具体用药和处置方案需由农技人员确认。",
        },
    )


def test_status_capabilities_and_models_status_fallback():
    status = client.get("/api/status")
    assert status.status_code == 200
    payload = status.json()
    assert payload["capabilities"]["single_image_detection"] is True
    assert payload["capabilities"]["batch_detection"] is True
    assert payload["capabilities"]["ws_alerts"] is True
    assert payload["capabilities"]["mock_mode"] in {True, False}
    assert payload["models"]["current_model"] in {"mock_disease_detector", "phone_rice_disease_yolo"}
    assert payload["storage"]["database_status"] == "ok"

    models = client.get("/api/models/status")
    assert models.status_code == 200
    model_payload = models.json()
    assert model_payload["detector_mode"] in {"mock", "smoke"}
    assert model_payload["fallback_to_mock"] in {True, False}
    assert model_payload["uav_model"]["name"] == "uav_rice_disease_yolo"
    assert model_payload["phone_model"]["name"] == "phone_rice_disease_yolo"


def test_seed_demo_data_populates_dashboard_mobile_heatmap_and_alerts():
    result = anyio.run(seed_demo_data, True)
    assert result["plots"] >= 5
    assert result["records"] >= 20
    assert result["alerts_created_or_updated"] >= 3

    summary = client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    assert summary.json()["total_record_count"] >= 20

    heatmap = client.get("/api/dashboard/heatmap")
    assert heatmap.status_code == 200
    assert heatmap.json()["points"]

    overview = client.get("/api/mobile/overview", params={"user_id": "demo_user"})
    assert overview.status_code == 200
    assert overview.json()["today_detect_count"] >= 20

    plots = client.get("/api/mobile/plots", params={"user_id": "demo_user"})
    assert plots.status_code == 200
    assert plots.json()["total"] >= 5

    alerts = client.get("/api/alerts")
    assert alerts.status_code == 200
    assert alerts.json()["total"] >= 3


def test_resolve_alert_writes_action_and_actions_are_queryable():
    record = make_high_record()
    result_store.save(record)
    alert = anyio.run(alert_service.handle_detection_result, record)
    assert alert is not None

    resolved = client.post(
        f"/api/alerts/{alert.alert_id}/resolve",
        json={"operator_id": "demo_user", "operator_name": "演示用户", "note": "已通知农技人员复核"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    actions = client.get(f"/api/alerts/{alert.alert_id}/actions")
    assert actions.status_code == 200
    payload = actions.json()
    assert payload["total"] >= 2
    assert any(item["action_type"] == "created" for item in payload["items"])
    resolved_actions = [item for item in payload["items"] if item["action_type"] == "resolved"]
    assert resolved_actions
    assert resolved_actions[-1]["operator_name"] == "演示用户"
    assert resolved_actions[-1]["note"] == "已通知农技人员复核"


def test_system_smoke_test_script_runs(capsys):
    smoke_main()
    output = capsys.readouterr().out
    assert "[PASS] healthz" in output
    assert "[PASS] detect image" in output
    assert "[PASS] ws alerts" in output
