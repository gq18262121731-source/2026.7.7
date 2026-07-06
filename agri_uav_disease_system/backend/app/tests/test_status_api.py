from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_status_contains_detector_mode():
    response = TestClient(app).get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service_status"] == "running"
    assert payload["model_name"] in {"mock_disease_detector", "phone_rice_disease_yolo"}
    assert payload["model_version"] in {"mock-v1", "smoke_epoch1_20260623"}
    assert payload["detector_mode"] in {"mock", "smoke"}
