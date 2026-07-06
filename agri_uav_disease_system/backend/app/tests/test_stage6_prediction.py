from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import anyio
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.detection_result import DetectionResult
from app.services.alert_service import alert_service
from app.services.prediction.prediction_service import prediction_service
from app.services.realtime.websocket_manager import alert_websocket_manager
from app.services.storage.result_store import result_store


client = TestClient(app)


def make_record(plot_id: str, disease: str = "稻瘟病", risk_level: str = "medium") -> DetectionResult:
    suffix = uuid4().hex[:8]
    severity = "重度" if risk_level == "high" else "中度"
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return DetectionResult(
        record_id=f"rec_stage6_{suffix}",
        image_id=f"img_stage6_{suffix}",
        plot_id=plot_id,
        plot_name=f"{plot_id} name",
        region_name="未指定乡镇",
        timestamp=timestamp,
        image_url=f"/static/original/img_stage6_{suffix}.jpg",
        result_image_url=f"/static/result/img_stage6_{suffix}.jpg",
        image_width=320,
        image_height=240,
        source_type="manual_upload",
        model_name="mock_disease_detector",
        model_version="mock-v1",
        detector_mode="mock",
        current_target_type="disease",
        geo={"lng": 118.5, "lat": 33.5},
        detections=[
            {
                "class_id": 0,
                "label": disease,
                "confidence": 0.9,
                "bbox": [10, 10, 160, 160],
                "area_ratio": 0.2,
            }
        ],
        summary={
            "disease_count": 1,
            "main_disease": disease,
            "max_confidence": 0.9,
            "severity": severity,
            "risk_level": risk_level,
        },
        suggestion={
            "title": "test",
            "content": "test",
            "need_expert_confirm": True,
            "actions": ["人工复核"],
            "knowledge_tags": [disease],
            "disclaimer": "本建议为辅助参考，具体防治方案和用药剂量需由农技人员确认。",
        },
    )


def test_prediction_without_history_returns_normal_or_low():
    plot_id = f"plot_stage6_empty_{uuid4().hex[:8]}"
    response = client.get(f"/api/prediction/plots/{plot_id}", params={"save": False})
    assert response.status_code == 200
    payload = response.json()
    assert payload["risk_level"] in {"normal", "low"}
    assert payload["risk_probability_note"] == "当前为规则分数归一化值，不代表真实统计概率。"
    assert payload["model"]["metrics"]["prediction_accuracy"] == "未指定"


def test_history_weather_growth_raise_risk_and_operation_lowers_score():
    plot_id = f"plot_stage6_risk_{uuid4().hex[:8]}"
    result_store.save(make_record(plot_id, risk_level="high"))
    base = client.get(f"/api/prediction/plots/{plot_id}", params={"save": False}).json()

    client.post(
        "/api/weather/observations",
        json={"plot_id": plot_id, "observed_date": "2026-06-26", "humidity_avg": 90, "rainfall_mm": 20},
    )
    client.post(
        "/api/growth-stages",
        json={"plot_id": plot_id, "manual_growth_stage": "分蘖期"},
    )
    raised = client.get(f"/api/prediction/plots/{plot_id}", params={"save": False}).json()
    assert raised["risk_score"] > base["risk_score"]
    assert "近 3 天平均湿度较高" in raised["main_factors"]
    assert "当前处于易感生育期" in raised["main_factors"]

    client.post(
        "/api/farm-operations",
        json={
            "plot_id": plot_id,
            "operation_type": "排水管护",
            "operation_time": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        },
    )
    lowered = client.get(f"/api/prediction/plots/{plot_id}", params={"save": False}).json()
    assert lowered["risk_score"] < raised["risk_score"]
    assert "最近 7 天已有复查、排水或管护记录" in lowered["main_factors"]


def test_prediction_windows_invalid_window_and_saved_result():
    plot_id = f"plot_stage6_window_{uuid4().hex[:8]}"
    for window in [3, 7, 14]:
        response = client.get(f"/api/prediction/plots/{plot_id}", params={"window_days": window})
        assert response.status_code == 200
        assert response.json()["prediction_window_days"] == window
        assert response.json()["prediction_id"]

    invalid = client.get(f"/api/prediction/plots/{plot_id}", params={"window_days": 5})
    assert invalid.status_code == 400
    assert invalid.json()["error_code"] == "INVALID_PREDICTION_WINDOW"

    detail = client.get(f"/api/mobile/plots/{plot_id}/prediction")
    assert detail.status_code == 200
    assert detail.json()["plot_id"] == plot_id


def test_prediction_alert_api_and_websocket_include_source():
    plot_id = f"plot_stage6_alert_{uuid4().hex[:8]}"
    result_store.save(make_record(plot_id, risk_level="high"))
    with client.websocket_connect("/ws/alerts") as websocket:
        assert alert_websocket_manager.client_count >= 1
        prediction = client.get(
            f"/api/prediction/plots/{plot_id}",
            params={"window_days": 7, "save": True, "create_alert": True},
        )
        assert prediction.status_code == 200
        event = websocket.receive_json()
        assert event["alert_source"] == "prediction"
        assert event["prediction_id"] == prediction.json()["prediction_id"]
        assert event["prediction_window_days"] == 7

    alerts = client.get("/api/alerts", params={"plot_id": plot_id, "page_size": 20})
    assert alerts.status_code == 200
    items = alerts.json()["items"]
    assert any(item["alert_source"] == "prediction" for item in items)
    assert any(item["alert_source"] == "detection" for item in items) is False or all("alert_source" in item for item in items)


def test_detection_alert_keeps_detection_source():
    record = make_record(f"plot_stage6_detection_{uuid4().hex[:8]}", risk_level="high")
    result_store.save(record)
    alert = anyio.run(alert_service.handle_detection_result, record)
    assert alert.alert_source == "detection"
    response = client.get(f"/api/alerts/{alert.alert_id}")
    assert response.status_code == 200
    assert response.json()["alert_source"] == "detection"


def test_stage6_recording_dashboard_mobile_endpoints():
    plot_id = f"plot_stage6_endpoints_{uuid4().hex[:8]}"
    weather = client.post(
        "/api/weather/observations",
        json={"plot_id": plot_id, "observed_date": "2026-06-26", "humidity_avg": 86, "rainfall_mm": 12},
    )
    assert weather.status_code == 200
    assert client.get("/api/weather/observations", params={"plot_id": plot_id}).json()["total"] >= 1

    growth = client.post("/api/growth-stages", json={"plot_id": plot_id, "sowing_date": "2026-05-20"})
    assert growth.status_code == 200
    assert client.get(f"/api/growth-stages/plots/{plot_id}").json()["total"] >= 1

    operation = client.post(
        "/api/farm-operations",
        json={"plot_id": plot_id, "operation_type": "田间巡查", "operation_time": "2026-06-26T00:00:00Z"},
    )
    assert operation.status_code == 200
    assert client.get("/api/farm-operations", params={"plot_id": plot_id}).json()["total"] >= 1
    assert client.get(f"/api/farm-operations/plots/{plot_id}").json()["total"] >= 1

    client.get(f"/api/prediction/plots/{plot_id}", params={"save": True})
    assert client.get("/api/prediction/dashboard/summary").status_code == 200
    assert client.get("/api/prediction/risk-map").status_code == 200
    mobile = client.get("/api/mobile/predictions")
    assert mobile.status_code == 200
    assert "items" in mobile.json()


def test_prediction_suggestion_has_no_dosage_or_real_metrics_claims():
    plot_id = f"plot_stage6_safe_{uuid4().hex[:8]}"
    payload = client.get(f"/api/prediction/plots/{plot_id}", params={"save": False}).json()
    text = str(payload)
    assert "毫升" not in text
    assert "克/亩" not in text
    assert payload["model"]["metrics"]["auc"] == "未指定"
