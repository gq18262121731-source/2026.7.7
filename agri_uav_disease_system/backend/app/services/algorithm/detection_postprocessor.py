from __future__ import annotations

from app.schemas.detection_result import Detection


class DetectionPostProcessor:
    def __init__(self, confidence_threshold: float = 0.5) -> None:
        self.confidence_threshold = confidence_threshold

    def process(self, detections: list[Detection]) -> list[Detection]:
        return [item for item in detections if item.confidence >= self.confidence_threshold]
