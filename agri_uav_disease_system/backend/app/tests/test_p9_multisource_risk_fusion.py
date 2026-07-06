from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.risk_fusion_scorer import risk_fusion_scorer
from app.services.uav_index_analyzer import uav_index_analyzer


client = TestClient(app)


def _create_field_and_uav(profile: str = "moderate_abnormal") -> tuple[str, str, str]:
    field_id = f"P9_FIELD_{uuid4().hex[:8]}"
    created = client.post(
        "/api/fields",
        json={
            "field_id": field_id,
            "field_name": "P9 test field",
            "current_growth_stage": "tillering",
        },
    )
    assert created.status_code == 200

    task = client.post(
        "/api/uav/tasks",
        json={
            "field_id": field_id,
            "task_name": "P9 UAV dry-run",
            "data_mode": "dry_run",
            "growth_stage": "tillering",
        },
    )
    assert task.status_code == 200
    uav_task_id = task.json()["uav_task_id"]

    dry_run = client.post(
        f"/api/uav/tasks/{uav_task_id}/dry-run",
        json={
            "field_id": field_id,
            "dry_run_profile": profile,
            "growth_stage": "tillering",
        },
    )
    assert dry_run.status_code == 200
    region_id = dry_run.json()["abnormal_regions"][0]["region_id"]
    return field_id, uav_task_id, region_id


def test_uav_index_analyzer_statistics_zscore_and_level():
    stats = uav_index_analyzer.calculate_zscore_anomaly([0.62, 0.61, 0.6, 0.35, 0.34], z_threshold=-1.0)
    assert stats["mean"] is not None
    assert stats["std"] is not None
    assert stats["abnormal_ratio"] > 0

    field_id, uav_task_id, _ = _create_field_and_uav("severe_abnormal")
    response = client.post(f"/api/uav/tasks/{uav_task_id}/analyze-indices")
    assert response.status_code == 200
    payload = response.json()
    assert payload["field_id"] == field_id
    assert payload["data_mode"] == "dry_run"
    assert payload["is_mock"] is True
    assert payload["probability_claim"] is False
    assert payload["uav_risk_score"] > 0
    assert payload["uav_abnormal_level"] in {"mild_abnormal", "moderate_abnormal", "severe_abnormal"}
    assert {item["index_type"] for item in payload["analysis"]} == {"ndvi", "ndre"}
    assert all(item["std_value"] is not None for item in payload["analysis"])

    detail = client.get(f"/api/uav/tasks/{uav_task_id}/index-analysis")
    assert detail.status_code == 200
    assert detail.json()["uav_risk_score"] == payload["uav_risk_score"]


def test_risk_fusion_component_scores_are_bounded_and_safe():
    assert risk_fusion_scorer.score_image_risk(
        {"disease_type": "rice_blast", "phone_confidence": 0.86, "severity_level": "medium"}
    ) == 24
    assert risk_fusion_scorer.score_environment_risk(
        {
            "weather": [],
        }
    ) == 0
    result, snapshot = risk_fusion_scorer.calculate_total_risk(
        {
            "field_id": "P9_UNIT",
            "uav_task_id": None,
            "uav_index_analysis": [],
            "uav_risk_score": 20,
            "uav_abnormal_level": "moderate_abnormal",
            "disease_type": "rice_blast",
            "phone_confidence": 0.86,
            "severity_level": "medium",
            "weather": [],
            "growth_stage": "tillering",
            "history_records": [],
            "operations": [],
            "include_weather": True,
            "include_history": True,
            "include_treatment": True,
        }
    )
    assert result.total_risk_score == 52
    assert result.risk_level == "medium"
    assert result.probability_claim is False
    assert snapshot.factor_scores["image"] == 24


def test_risk_fusion_api_and_report_detail():
    field_id, uav_task_id, region_id = _create_field_and_uav("moderate_abnormal")
    weather = client.post(
        "/api/weather/observations",
        json={
            "plot_id": field_id,
            "observed_date": "2026-07-05",
            "humidity_avg": 91,
            "rainfall_mm": 20,
            "weather_text": "rain",
        },
    )
    assert weather.status_code == 200

    analysis = client.post(f"/api/uav/tasks/{uav_task_id}/analyze-indices")
    assert analysis.status_code == 200

    fusion = client.post(
        "/api/risk/fusion/evaluate",
        json={
            "field_id": field_id,
            "uav_task_id": uav_task_id,
            "abnormal_region_id": region_id,
            "include_weather": True,
            "include_history": True,
            "include_treatment": True,
        },
    )
    assert fusion.status_code == 200
    payload = fusion.json()
    assert payload["field_id"] == field_id
    assert payload["factor_scores"]["uav"] > 0
    assert payload["factor_scores"]["environment"] > 0
    assert payload["risk_level"] in {"low", "medium", "high"}
    assert payload["probability_claim"] is False
    assert payload["experimental_only"] is True
    assert payload["not_for_production"] is True
    assert "probability" in payload["safety_note"]

    detail = client.get(f"/api/risk/fusion/{payload['prediction_id']}")
    assert detail.status_code == 200
    assert detail.json()["prediction_id"] == payload["prediction_id"]

    history = client.get(f"/api/risk/fusion/field/{field_id}")
    assert history.status_code == 200
    assert history.json()["total"] >= 1

    report = client.post(
        "/api/inspection-reports/generate",
        json={
            "field_id": field_id,
            "uav_task_id": uav_task_id,
            "include_rag": False,
            "include_risk": False,
        },
    )
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["risk_model_detail"]["model_type"] == "rule_weighted_score"
    assert report_payload["risk_model_detail"]["model_stage"] == "experimental"
    assert report_payload["risk_model_detail"]["probability_claim"] is False
    assert report_payload["payload"]["model_boundary"]["formal_metric_available"] is False
    assert "rule_weighted_risk_note" in report_payload["payload"]["model_boundary"]
