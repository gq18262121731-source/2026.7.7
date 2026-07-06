from __future__ import annotations

import hashlib
import random

from app.core.config import settings
from app.schemas.detection_result import Detection
from app.services.inference.disease_detector import DiseaseDetector


class MockDiseaseDetector(DiseaseDetector):
    name = "mock_disease_detector"
    version = "mock-v1"

    def __init__(
        self,
        seed: int | None = None,
        classes: list[str] | None = None,
        fallback_to_mock: bool = False,
        current_target_type: str | None = None,
    ) -> None:
        self.seed = seed if seed is not None else settings.mock_seed
        self.classes = classes or settings.mock_classes
        self.fallback_to_mock = fallback_to_mock
        self.current_target_type = current_target_type

    def detect(self, image_path: str, image_width: int, image_height: int) -> list[Detection]:
        rng = self._rng_for_image(image_path)
        count = rng.randint(0, 2)
        detections: list[Detection] = []
        for index in range(count):
            box_width = max(32, int(image_width * rng.uniform(0.14, 0.32)))
            box_height = max(32, int(image_height * rng.uniform(0.12, 0.30)))
            max_x = max(1, image_width - box_width)
            max_y = max(1, image_height - box_height)
            x1 = rng.randint(0, max_x)
            y1 = rng.randint(0, max_y)
            x2 = min(image_width, x1 + box_width)
            y2 = min(image_height, y1 + box_height)
            label = self.classes[(rng.randint(0, 9999) + index) % len(self.classes)]
            area_ratio = round(((x2 - x1) * (y2 - y1)) / max(1, image_width * image_height), 4)
            detections.append(
                Detection(
                    class_id=self.classes.index(label),
                    label=label,
                    confidence=round(rng.uniform(0.62, 0.94), 2),
                    bbox=[x1, y1, x2, y2],
                    area_ratio=area_ratio,
                )
            )
        return detections

    def _rng_for_image(self, image_path: str) -> random.Random:
        digest = hashlib.sha256(f"{self.seed}:{image_path}".encode("utf-8")).hexdigest()
        return random.Random(int(digest[:12], 16))
