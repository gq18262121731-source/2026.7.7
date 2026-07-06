from __future__ import annotations

from app.core.config import settings
from app.core.constants import (
    SOURCE_MANUAL_UPLOAD,
    SOURCE_PHONE_RGB,
    SOURCE_UAV_MS,
    SOURCE_UAV_MULTISPECTRAL,
    SOURCE_UAV_RGB,
    SOURCE_UAV_VIDEO_FRAME,
)
from app.core.logger import logger
from app.services.inference.disease_detector import DiseaseDetector
from app.services.inference.mock_disease_detector import MockDiseaseDetector
from app.services.inference.real_disease_detector import RealDiseaseDetector
from app.services.inference.smoke_yolo_detector import SmokeYoloDetector


UAV_SOURCE_TYPES = {SOURCE_UAV_RGB, SOURCE_UAV_MS, SOURCE_UAV_MULTISPECTRAL, SOURCE_UAV_VIDEO_FRAME}
PHONE_SOURCE_TYPES = {SOURCE_PHONE_RGB, SOURCE_MANUAL_UPLOAD}
UAV_BLB_MODEL_HINTS = {"uav_blb", "uav_blb_disease_yolo", "blb", "bacterial_leaf_blight"}
UAV_BLB_EXPERIMENTAL_HINTS = {"uav_blb_exp", "uav_blb_experimental", "blb_exp", "experimental_408"}
PHONE_EXPERIMENTAL_HINTS = {"phone_exp", "phone_experimental", "riceleafdiseasebd", "riceleafdiseasebd_exp"}
DISEASE_TARGET_TYPES = {"disease", "rice_disease", "blb"}
EXPERIMENTAL_STAGE_HINTS = {"experimental", "exp"}


class ModelManager:
    def __init__(self) -> None:
        self.mock_detector: DiseaseDetector = MockDiseaseDetector()
        self.default_detector: DiseaseDetector = self._build_detector(settings.model_path)
        self.phone_detector = self._build_smoke_detector(
            "phone_rice_disease_yolo",
            settings.phone_model_path,
            ["bacterial_leaf_blight", "brown_spot", "rice_blast"],
            "disease",
        )
        self.uav_detector = self._build_smoke_detector(
            "uav_rice_disease_yolo",
            settings.uav_model_path,
            ["rice_panicle"],
            "crop_object",
        )
        self.phone_experimental_detector = self._build_phone_experimental_detector()
        self.uav_blb_detector = self._build_uav_blb_detector()
        self.uav_blb_experimental_detector = self._build_uav_blb_experimental_detector()
        self.detector_mode = self._resolve_detector_mode()
        logger.info("Disease detector mode: %s", self.detector_mode)

    def _build_detector(self, model_path: str) -> DiseaseDetector:
        if settings.detector_mode.lower() == "real" and model_path:
            real_detector = RealDiseaseDetector(model_path)
            if real_detector.loaded:
                return real_detector
            logger.warning("Real model path is missing or invalid. Falling back to mock detector.")
        return self.mock_detector

    def _build_smoke_detector(
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
    ) -> DiseaseDetector:
        if settings.detector_mode.lower() not in {"smoke", "auto"}:
            return self.mock_detector
        detector = SmokeYoloDetector(
            model_name=model_name,
            weights_path=weights_path,
            class_names=class_names,
            current_target_type=current_target_type,
            model_version=model_version,
            confidence=confidence,
            category_type=category_type,
            class_codes=class_codes,
            model_stage=model_stage,
            is_smoke=is_smoke,
            model_display_name=model_display_name,
            model_warning=model_warning,
            model_usage_scope=model_usage_scope,
            model_capability_level=model_capability_level,
        )
        if detector.loaded:
            return detector
        logger.warning("%s %s weights unavailable. Falling back to mock detector.", model_name, model_stage)
        return MockDiseaseDetector(fallback_to_mock=True, current_target_type=current_target_type)

    def _build_phone_experimental_detector(self) -> DiseaseDetector:
        if not settings.enable_phone_experimental:
            return MockDiseaseDetector(fallback_to_mock=True, current_target_type="disease")
        return self._build_smoke_detector(
            settings.phone_experimental_model_name,
            settings.phone_experimental_model_path,
            ["brown_spot", "rice_blast", "leaf_smut", "tungro", "sheath_blight"],
            "disease",
            model_version=settings.phone_experimental_model_version,
            confidence=settings.phone_experimental_confidence,
            category_type="disease",
            class_codes=["brown_spot", "rice_blast", "leaf_smut", "tungro", "sheath_blight"],
            model_stage="experimental",
            is_smoke=False,
            model_display_name="Phone RiceLeafDiseaseBD experimental model",
            model_warning=(
                "Experimental 3 epoch RiceLeafDiseaseBD phone RGB expanded weight; for experiment "
                "verification only and not formal model performance."
            ),
            model_usage_scope="phone_rgb/manual_upload + model_hint=phone_exp",
            model_capability_level="experimental_only",
        )

    def _build_uav_blb_detector(self) -> DiseaseDetector:
        if not settings.enable_uav_blb_smoke:
            return MockDiseaseDetector(fallback_to_mock=True, current_target_type="disease")
        return self._build_smoke_detector(
            settings.uav_blb_model_name,
            settings.uav_blb_model_path,
            ["bacterial_leaf_blight"],
            "disease",
            model_version=settings.uav_blb_model_version,
            confidence=settings.uav_blb_smoke_confidence,
            category_type="disease",
            class_codes=["bacterial_leaf_blight"],
        )

    def _build_uav_blb_experimental_detector(self) -> DiseaseDetector:
        if not settings.enable_uav_blb_experimental:
            return MockDiseaseDetector(fallback_to_mock=True, current_target_type="disease")
        return self._build_smoke_detector(
            settings.uav_blb_experimental_model_name,
            settings.uav_blb_experimental_model_path,
            ["bacterial_leaf_blight"],
            "disease",
            model_version=settings.uav_blb_experimental_model_version,
            confidence=settings.uav_blb_experimental_confidence,
            category_type="disease",
            class_codes=["bacterial_leaf_blight"],
            model_stage="experimental",
            is_smoke=False,
            model_display_name="UAV BLB experimental model",
            model_warning=(
                "Experimental BLB UAV constrained-408 RGB preview weight; for experiment verification only, "
                "not formal model performance."
            ),
            model_usage_scope="uav_multispectral + model_hint=uav_blb_exp",
            model_capability_level="experimental_only",
        )

    def _resolve_detector_mode(self) -> str:
        detectors = [
            self.phone_detector,
            self.phone_experimental_detector,
            self.uav_detector,
            self.uav_blb_detector,
            self.uav_blb_experimental_detector,
        ]
        if any(isinstance(detector, SmokeYoloDetector) for detector in detectors):
            return "smoke"
        if isinstance(self.default_detector, RealDiseaseDetector) and self.default_detector.loaded:
            return "real"
        return "mock"

    def get_detector(
        self,
        source_type: str | None = None,
        model_hint: str | None = None,
        target_type: str | None = None,
        model_stage_hint: str | None = None,
    ) -> DiseaseDetector:
        if source_type in UAV_SOURCE_TYPES:
            if self._wants_uav_blb_experimental(model_hint, model_stage_hint):
                return self.uav_blb_experimental_detector
            if self._wants_uav_blb(model_hint, target_type):
                return self.uav_blb_detector
            return self.uav_detector
        if source_type in PHONE_SOURCE_TYPES:
            if self._wants_phone_experimental(model_hint, model_stage_hint):
                return self.phone_experimental_detector
            return self.phone_detector
        return self.default_detector

    def _wants_uav_blb_experimental(self, model_hint: str | None, model_stage_hint: str | None) -> bool:
        normalized_hint = (model_hint or "").strip().lower()
        normalized_stage = (model_stage_hint or "").strip().lower()
        return normalized_hint in UAV_BLB_EXPERIMENTAL_HINTS or normalized_stage in EXPERIMENTAL_STAGE_HINTS

    def _wants_phone_experimental(self, model_hint: str | None, model_stage_hint: str | None) -> bool:
        normalized_hint = (model_hint or "").strip().lower()
        normalized_stage = (model_stage_hint or "").strip().lower()
        return normalized_hint in PHONE_EXPERIMENTAL_HINTS or normalized_stage in EXPERIMENTAL_STAGE_HINTS

    def _wants_uav_blb(self, model_hint: str | None, target_type: str | None) -> bool:
        normalized_hint = (model_hint or "").strip().lower()
        normalized_target = (target_type or "").strip().lower()
        return normalized_hint in UAV_BLB_MODEL_HINTS or normalized_target in DISEASE_TARGET_TYPES

    def planned_model_name(
        self,
        source_type: str | None,
        model_hint: str | None = None,
        target_type: str | None = None,
        model_stage_hint: str | None = None,
    ) -> str:
        if source_type in UAV_SOURCE_TYPES:
            if self._wants_uav_blb_experimental(model_hint, model_stage_hint):
                return settings.uav_blb_experimental_model_name
            if self._wants_uav_blb(model_hint, target_type):
                return settings.uav_blb_model_name
            return "uav_rice_disease_yolo"
        if source_type in PHONE_SOURCE_TYPES:
            if self._wants_phone_experimental(model_hint, model_stage_hint):
                return settings.phone_experimental_model_name
            return "phone_rice_disease_yolo"
        return self.default_detector.name

    def actual_detector_mode(
        self,
        source_type: str | None = None,
        model_hint: str | None = None,
        target_type: str | None = None,
        model_stage_hint: str | None = None,
    ) -> str:
        detector = self.get_detector(source_type, model_hint, target_type, model_stage_hint)
        if getattr(detector, "model_stage", None) == "experimental":
            return "experimental"
        if getattr(detector, "is_smoke", False):
            return "smoke"
        if detector is self.mock_detector or detector.name == "mock_disease_detector":
            return "mock"
        return self.detector_mode

    def is_loaded(self) -> bool:
        return True

    def smoke_status(self) -> dict[str, bool]:
        return {
            "phone_smoke_loaded": isinstance(self.phone_detector, SmokeYoloDetector) and self.phone_detector.loaded,
            "phone_experimental_loaded": (
                isinstance(self.phone_experimental_detector, SmokeYoloDetector)
                and self.phone_experimental_detector.loaded
                and getattr(self.phone_experimental_detector, "model_stage", None) == "experimental"
            ),
            "uav_smoke_loaded": isinstance(self.uav_detector, SmokeYoloDetector) and self.uav_detector.loaded,
            "uav_blb_smoke_loaded": isinstance(self.uav_blb_detector, SmokeYoloDetector) and self.uav_blb_detector.loaded,
            "uav_blb_experimental_loaded": (
                isinstance(self.uav_blb_experimental_detector, SmokeYoloDetector)
                and self.uav_blb_experimental_detector.loaded
                and getattr(self.uav_blb_experimental_detector, "model_stage", None) == "experimental"
            ),
            "phone_fallback_to_mock": self.phone_detector.name == "mock_disease_detector",
            "phone_experimental_fallback_to_mock": self.phone_experimental_detector.name == "mock_disease_detector",
            "uav_fallback_to_mock": self.uav_detector.name == "mock_disease_detector",
            "uav_blb_fallback_to_mock": self.uav_blb_detector.name == "mock_disease_detector",
            "uav_blb_experimental_fallback_to_mock": self.uav_blb_experimental_detector.name == "mock_disease_detector",
        }


model_manager = ModelManager()
