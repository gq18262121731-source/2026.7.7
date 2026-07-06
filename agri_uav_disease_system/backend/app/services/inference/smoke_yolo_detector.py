from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.schemas.detection_result import Detection
from app.services.inference.disease_detector import DiseaseDetector


class SmokeYoloDetector(DiseaseDetector):
    model_stage = "smoke"
    is_smoke = True
    formal_metric_available = False
    fallback_to_mock = False

    def __init__(
        self,
        model_name: str,
        weights_path: str,
        class_names: list[str],
        current_target_type: str,
        model_version: str = "smoke_epoch1_20260623",
        confidence: float | None = None,
        category_type: str | None = None,
        class_codes: list[str] | None = None,
        model_stage: str = "smoke",
        is_smoke: bool = True,
        model_display_name: str | None = None,
        model_warning: str | None = None,
        model_usage_scope: str | None = None,
        model_capability_level: str | None = None,
    ) -> None:
        self.name = model_name
        self.version = model_version
        self.weights_path = Path(weights_path)
        self.class_names = class_names
        self.class_codes = class_codes or class_names
        self.current_target_type = current_target_type
        self.category_type = category_type or current_target_type
        self.confidence = confidence if confidence is not None else settings.smoke_yolo_confidence
        self.model_stage = model_stage
        self.is_smoke = is_smoke
        self.formal_metric_available = False
        self.model_display_name = model_display_name
        self.model_warning = model_warning
        self.model_usage_scope = model_usage_scope
        self.model_capability_level = model_capability_level
        self.loaded = False
        self.load_error: str | None = None
        self._model: Any | None = None
        self._load()

    def _load(self) -> None:
        if not self.weights_path.exists():
            self.load_error = f"weights_not_found:{self.weights_path}"
            return
        try:
            from ultralytics import YOLO

            self._model = YOLO(str(self.weights_path))
            self.loaded = True
        except Exception as exc:  # noqa: BLE001 - smoke adapter must fall back cleanly
            self.load_error = f"{exc.__class__.__name__}:{exc}"
            logger.warning("Smoke YOLO model load failed for %s: %s", self.name, self.load_error)

    def detect(self, image_path: str, image_width: int, image_height: int) -> list[Detection]:
        if not self.loaded or self._model is None:
            raise RuntimeError(self.load_error or "smoke_yolo_not_loaded")

        results = self._model.predict(
            source=image_path,
            conf=self.confidence,
            save=False,
            verbose=False,
        )
        detections: list[Detection] = []
        for result in results:
            names = result.names or {}
            for box in result.boxes:
                class_id = int(box.cls[0].item())
                x1, y1, x2, y2 = [int(round(float(value))) for value in box.xyxy[0].tolist()]
                x1 = max(0, min(image_width, x1))
                y1 = max(0, min(image_height, y1))
                x2 = max(0, min(image_width, x2))
                y2 = max(0, min(image_height, y2))
                if x2 <= x1 or y2 <= y1:
                    continue
                area_ratio = round(((x2 - x1) * (y2 - y1)) / max(1, image_width * image_height), 4)
                label = str(names.get(class_id, self._fallback_class_name(class_id)))
                class_name = self._fallback_class_name(class_id)
                detections.append(
                    Detection(
                        class_id=class_id,
                        label=label,
                        class_name=class_name,
                        category_type=self.category_type,
                        class_code=self._fallback_class_code(class_id),
                        confidence=float(box.conf[0].item()),
                        bbox=[x1, y1, x2, y2],
                        area_ratio=area_ratio,
                    )
                )
        return detections

    def _fallback_class_name(self, class_id: int) -> str:
        if 0 <= class_id < len(self.class_names):
            return self.class_names[class_id]
        return str(class_id)

    def _fallback_class_code(self, class_id: int) -> str:
        if 0 <= class_id < len(self.class_codes):
            return self.class_codes[class_id]
        return self._fallback_class_name(class_id)
