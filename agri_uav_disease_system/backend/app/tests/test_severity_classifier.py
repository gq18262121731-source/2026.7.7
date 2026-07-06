from __future__ import annotations

from app.schemas.detection_result import Detection
from app.services.algorithm.severity_classifier import DiseaseSeverityClassifier


def test_severity_none_when_no_detection():
    assert DiseaseSeverityClassifier().classify([]) == "\u65e0\u75c5"


def test_severity_light_medium_heavy_by_area_ratio():
    classifier = DiseaseSeverityClassifier()
    assert classifier.classify([Detection(class_id=0, label="\u7a3b\u761f\u75c5", confidence=0.9, bbox=[0, 0, 10, 10], area_ratio=0.03)]) == "\u8f7b\u5ea6"
    assert classifier.classify([Detection(class_id=0, label="\u7a3b\u761f\u75c5", confidence=0.9, bbox=[0, 0, 10, 10], area_ratio=0.10)]) == "\u4e2d\u5ea6"
    assert classifier.classify([Detection(class_id=0, label="\u7a3b\u761f\u75c5", confidence=0.9, bbox=[0, 0, 10, 10], area_ratio=0.25)]) == "\u91cd\u5ea6"
