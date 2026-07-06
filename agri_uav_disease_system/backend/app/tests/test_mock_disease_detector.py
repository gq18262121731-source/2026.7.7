from __future__ import annotations

from app.services.inference.mock_disease_detector import MockDiseaseDetector


def test_mock_detector_returns_stable_schema():
    detector = MockDiseaseDetector(seed=1, classes=["\u7a3b\u761f\u75c5", "\u7eb9\u67af\u75c5"])
    detections = detector.detect("demo.jpg", 1280, 720)
    assert len(detections) <= 2
    for detection in detections:
        assert detection.label in ["\u7a3b\u761f\u75c5", "\u7eb9\u67af\u75c5"]
        assert len(detection.bbox) == 4
        assert 0 <= detection.area_ratio <= 1
