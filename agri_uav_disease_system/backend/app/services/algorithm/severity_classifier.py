from __future__ import annotations

from app.core.config import settings
from app.core.constants import SEVERITY_HEAVY, SEVERITY_LIGHT, SEVERITY_MEDIUM, SEVERITY_NONE
from app.schemas.detection_result import Detection


class DiseaseSeverityClassifier:
    order = [SEVERITY_NONE, SEVERITY_LIGHT, SEVERITY_MEDIUM, SEVERITY_HEAVY]

    def classify(self, detections: list[Detection]) -> str:
        if not detections:
            return SEVERITY_NONE

        max_area_ratio = max(item.area_ratio for item in detections)
        if max_area_ratio < settings.severity_light_max_area_ratio:
            severity = SEVERITY_LIGHT
        elif max_area_ratio < settings.severity_medium_max_area_ratio:
            severity = SEVERITY_MEDIUM
        else:
            severity = SEVERITY_HEAVY

        if len(detections) >= settings.severity_many_detections_threshold:
            severity = self._upgrade(severity)
        return severity

    def _upgrade(self, severity: str) -> str:
        index = self.order.index(severity)
        return self.order[min(index + 1, len(self.order) - 1)]
