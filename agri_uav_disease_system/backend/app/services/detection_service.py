from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.constants import DEFAULT_REGION_NAME, ERROR_MODEL
from app.core.exceptions import AppException
from app.schemas.detection_result import DetectionResult
from app.schemas.upload import DetectImageMetadata
from app.services.algorithm.detection_postprocessor import DetectionPostProcessor
from app.services.algorithm.risk_evaluator import RiskLevelEvaluator
from app.services.algorithm.severity_classifier import DiseaseSeverityClassifier
from app.services.algorithm.suggestion_engine import AgricultureSuggestionEngine
from app.services.alert_service import alert_service
from app.services.inference.image_preprocessor import ImagePreprocessor
from app.services.inference.model_display import get_model_display_info
from app.services.inference.model_manager import model_manager
from app.services.inference.result_renderer import ResultRenderer
from app.services.realtime.detection_result_publisher import detection_result_publisher
from app.services.storage.file_storage import file_storage_service
from app.services.storage.result_store import result_store


class DetectionService:
    def __init__(self) -> None:
        self.preprocessor = ImagePreprocessor()
        self.postprocessor = DetectionPostProcessor()
        self.severity_classifier = DiseaseSeverityClassifier()
        self.risk_evaluator = RiskLevelEvaluator()
        self.suggestion_engine = AgricultureSuggestionEngine()
        self.renderer = ResultRenderer()

    async def detect_upload(self, file: UploadFile, metadata: DetectImageMetadata) -> DetectionResult:
        image_id, image_path, image_url = await file_storage_service.save_upload(file)
        return await self.detect_saved_image(image_id, image_path, image_url, metadata)

    async def detect_saved_image(
        self,
        image_id: str,
        image_path: str,
        image_url: str,
        metadata: DetectImageMetadata,
        ) -> DetectionResult:
        width, height = self.preprocessor.inspect_image(image_path)
        source_type = metadata.normalized_source_type()
        detector = model_manager.get_detector(source_type, metadata.model_hint, metadata.target_type, metadata.model_stage_hint)
        model_display = get_model_display_info(detector.name, getattr(detector, "model_stage", None))

        try:
            raw_detections = detector.detect(image_path, width, height)
        except Exception as exc:
            raise AppException(ERROR_MODEL, "\u6a21\u578b\u63a8\u7406\u5931\u8d25", {"reason": str(exc)}) from exc

        detections = self.postprocessor.process(raw_detections)
        severity = self.severity_classifier.classify(detections)
        risk_level = self.risk_evaluator.evaluate(severity)
        main_disease = self._main_disease(detections)
        suggestion = self.suggestion_engine.generate(main_disease, severity)

        result_filename = f"{image_id}_result.jpg"
        result_path = settings.result_dir / result_filename
        result_image_url = f"/static/result/{result_filename}"
        if detections:
            self.renderer.render(image_path, str(result_path), detections, severity)
        else:
            file_storage_service.copy_as_result_when_no_detection(image_path, str(result_path))

        timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        effective_field_id = metadata.field_id or metadata.plot_id
        effective_plot_id = metadata.plot_id or effective_field_id
        result = DetectionResult(
            record_id=f"rec_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            image_id=image_id,
            field_id=effective_field_id,
            plot_id=effective_plot_id,
            plot_name=metadata.plot_name,
            region_name=metadata.region_name or DEFAULT_REGION_NAME,
            timestamp=timestamp,
            image_url=image_url,
            result_image_url=result_image_url,
            image_width=width,
            image_height=height,
            source_type=source_type,
            model_name=detector.name,
            model_version=detector.version,
            detector_mode=model_manager.actual_detector_mode(source_type, metadata.model_hint, metadata.target_type, metadata.model_stage_hint),
            is_smoke=getattr(detector, "is_smoke", False),
            model_stage=getattr(detector, "model_stage", "mock"),
            formal_metric_available=getattr(detector, "formal_metric_available", False),
            current_target_type=getattr(detector, "current_target_type", None),
            category_type=getattr(detector, "category_type", getattr(detector, "current_target_type", None)),
            fallback_to_mock=getattr(detector, "fallback_to_mock", False) or detector.name == "mock_disease_detector",
            model_hint=metadata.model_hint,
            target_type=metadata.target_type,
            model_stage_hint=metadata.model_stage_hint,
            uav_task_id=metadata.uav_task_id,
            abnormal_region_id=metadata.abnormal_region_id,
            model_display_name=getattr(detector, "model_display_name", None) or model_display.display_name,
            model_warning=getattr(detector, "model_warning", None) or model_display.warning,
            model_usage_scope=getattr(detector, "model_usage_scope", None) or model_display.usage_scope,
            model_capability_level=getattr(detector, "model_capability_level", None) or model_display.capability_level,
            geo={"lng": metadata.lng, "lat": metadata.lat},
            detections=detections,
            summary={
                "disease_count": len(detections),
                "main_disease": main_disease,
                "max_confidence": max((item.confidence for item in detections), default=0.0),
                "severity": severity,
                "risk_level": risk_level,
            },
            suggestion=suggestion,
        )
        result_store.save(result)
        if result.abnormal_region_id:
            from app.services.uav_service import uav_service

            uav_service.handle_phone_followup_result(result)
        await detection_result_publisher.publish(result)
        await alert_service.handle_detection_result(result)
        return result

    def _main_disease(self, detections) -> str | None:
        if not detections:
            return None
        return max(detections, key=lambda item: item.confidence).label


detection_service = DetectionService()

