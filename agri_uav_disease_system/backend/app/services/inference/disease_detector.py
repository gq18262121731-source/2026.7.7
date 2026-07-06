from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.detection_result import Detection


class DiseaseDetector(ABC):
    name: str
    version: str
    model_stage: str = "mock"
    is_smoke: bool = False
    formal_metric_available: bool = False
    current_target_type: str | None = None
    fallback_to_mock: bool = False

    @abstractmethod
    def detect(self, image_path: str, image_width: int, image_height: int) -> list[Detection]:
        raise NotImplementedError
