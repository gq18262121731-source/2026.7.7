from __future__ import annotations

from pathlib import Path

from app.schemas.detection_result import Detection
from app.services.inference.disease_detector import DiseaseDetector


class RealDiseaseDetector(DiseaseDetector):
    name = "real_disease_detector"
    version = "unloaded"

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self.loaded = bool(model_path) and Path(model_path).exists()
        if self.loaded:
            self.version = Path(model_path).stem

    def detect(self, image_path: str, image_width: int, image_height: int) -> list[Detection]:
        if not self.loaded:
            raise RuntimeError("真实模型权重不存在，不能执行真实推理")
        # Future YOLO adapter:
        # model = YOLO(self.model_path)
        # raw_results = model.predict(image_path)
        # return convert_yolo_results_to_detection_schema(raw_results)
        raise NotImplementedError("真实 YOLO 适配器预留，MVP 默认使用 MockDiseaseDetector")
