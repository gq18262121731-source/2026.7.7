from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.constants import DEFAULT_REGION_NAME, RISK_NORMAL
from app.schemas.detection_result import DetectionResult
from app.services.experimental.uav_blb_segmentation_dry_run_service import (
    EXPECTED_SHA256,
    FIELD_TRIAL_WARNING,
    INPUT_CONFIG,
    MIN_AREA,
    MODEL_NAME,
    MODEL_STAGE,
    PATCH_SIZE,
    STRIDE,
    THRESHOLD,
    DryRunError,
    uav_blb_segmentation_dry_run_service,
)
from app.services.storage.result_store import result_store


RELEASE_VERSION = "uav_blb_ms_seg_v1.0"
RELEASE_STAGE = "initial_release_testing"
PRODUCTION_SCOPE = "record_and_visualization_only"
MODEL_DISPLAY_NAME = "UAV BLB multispectral segmentation v1.0"
MODEL_WARNING = "Initial release testing; requires human review; alerting disabled."
DISEASE_NAME = "bacterial_leaf_blight"
TASK_TYPE = "blb_segmentation"
RESULT_TYPE = "segmentation_mask"
CURRENT_TARGET_TYPE = "blb_segmentation"
ALLOWED_REVIEW_STATUS = {"pending", "reviewed"}
ALLOWED_REVIEW_LABELS = {
    "acceptable",
    "over_segmentation",
    "under_segmentation",
    "noise_false_positive",
    "background_false_positive",
    "alignment_error",
    "major_failure",
    "uncertain",
}


class UavBlbSegmentationV1ReleaseError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str, detail: dict | None = None) -> None:
        self.status_code = status_code
        self.payload = {
            "success": False,
            "error_code": error_code,
            "message": message,
            "detail": detail or {},
            "production_ready": True,
            "production_scope": PRODUCTION_SCOPE,
            "alerting_enabled": False,
            "latest_alerts_enabled": False,
            "model_stage": RELEASE_STAGE,
            "model_version": RELEASE_VERSION,
            "fallback_to_rgb_or_yolo": False,
        }
        super().__init__(message)


class UavBlbSegmentationV1ReleaseService:
    def __init__(self) -> None:
        self.output_root = settings.static_dir / "result" / "uav_blb_ms_seg_v1_0"
        self.artifact_lock_path = uav_blb_segmentation_dry_run_service.artifact_lock_path

    async def detect_upload(
        self,
        file: UploadFile,
        plot_id: str | None = None,
        plot_name: str | None = None,
        region_name: str | None = None,
        field_id: str | None = None,
        lng: float | None = None,
        lat: float | None = None,
        human_review_status: str = "pending",
        human_review_label: str | None = None,
        issue_tags: str | None = None,
        reviewer_note: str | None = None,
    ) -> DetectionResult:
        self._validate_filename(file.filename)
        self._validate_review(human_review_status, human_review_label)
        lock = self._load_and_verify_artifact_lock()

        created_at = datetime.now(timezone.utc)
        image_id = f"uav_blb_ms_seg_v1_{created_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        job_dir = self.output_root / image_id
        job_dir.mkdir(parents=True, exist_ok=True)
        input_path = job_dir / f"input{Path(file.filename or '').suffix.lower()}"
        await uav_blb_segmentation_dry_run_service._save_upload(file, input_path)

        start = time.perf_counter()
        try:
            probability, binary, preview = uav_blb_segmentation_dry_run_service._run_inference(input_path, lock)
        except DryRunError as exc:
            raise self._from_dry_run_error(exc) from exc
        except Exception as exc:
            raise UavBlbSegmentationV1ReleaseError(
                500,
                "UAV_BLB_SEGMENTATION_V1_INFERENCE_FAILED",
                "UAV BLB segmentation v1.0 inference failed.",
                {"reason": str(exc)},
            ) from exc
        inference_time_ms = int((time.perf_counter() - start) * 1000)

        probability_url = uav_blb_segmentation_dry_run_service._save_probability(job_dir, probability)
        mask_url = uav_blb_segmentation_dry_run_service._save_mask(job_dir, binary)
        preview_url, overlay_url = uav_blb_segmentation_dry_run_service._save_preview_and_overlay(job_dir, preview, binary, True)
        disease_area_ratio = float(binary.mean())
        max_probability = float(probability.max()) if probability.size else 0.0
        timestamp = created_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        effective_field_id = field_id or plot_id
        effective_plot_id = plot_id or effective_field_id
        issue_tag_list = self._parse_issue_tags(issue_tags)

        result = DetectionResult(
            record_id=f"rec_uav_blb_ms_seg_v1_{created_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}",
            image_id=image_id,
            field_id=effective_field_id,
            plot_id=effective_plot_id,
            plot_name=plot_name,
            region_name=region_name or DEFAULT_REGION_NAME,
            timestamp=timestamp,
            image_url=preview_url,
            result_image_url=overlay_url,
            image_width=int(binary.shape[1]),
            image_height=int(binary.shape[0]),
            source_type="uav_multispectral",
            model_name=MODEL_NAME,
            model_version=RELEASE_VERSION,
            detector_mode="segmentation_v1_0",
            is_smoke=False,
            model_stage=RELEASE_STAGE,
            formal_metric_available=True,
            current_target_type=CURRENT_TARGET_TYPE,
            category_type="segmentation_mask",
            fallback_to_mock=False,
            model_hint="uav_blb_ms_seg_v1_0",
            target_type=TASK_TYPE,
            model_stage_hint=RELEASE_STAGE,
            model_display_name=MODEL_DISPLAY_NAME,
            model_warning=MODEL_WARNING,
            model_usage_scope="uav_multispectral 5-band TIF only; record and visualization; alerting disabled",
            model_capability_level=RELEASE_STAGE,
            task_type=TASK_TYPE,
            result_type=RESULT_TYPE,
            disease_name=DISEASE_NAME,
            model_sha256=EXPECTED_SHA256,
            input_config=INPUT_CONFIG,
            threshold=THRESHOLD,
            min_area=MIN_AREA,
            disease_area_ratio=disease_area_ratio,
            mask_url=mask_url,
            overlay_url=overlay_url,
            probability_map_url=probability_url,
            production_scope=PRODUCTION_SCOPE,
            human_review_required=True,
            human_review_status=human_review_status,
            human_review_label=human_review_label,
            issue_tags=issue_tag_list,
            reviewer_note=reviewer_note,
            alerting_enabled=False,
            latest_alerts_enabled=False,
            active_model_version=RELEASE_VERSION,
            geo={"lng": lng, "lat": lat},
            detections=[
                {
                    "class_id": 0,
                    "label": DISEASE_NAME,
                    "class_name": DISEASE_NAME,
                    "category_type": "segmentation_mask",
                    "class_code": DISEASE_NAME,
                    "confidence": max_probability,
                    "bbox": [0, 0, int(binary.shape[1]), int(binary.shape[0])],
                    "area_ratio": disease_area_ratio,
                }
            ],
            summary={
                "disease_count": 1,
                "main_disease": DISEASE_NAME,
                "max_confidence": max_probability,
                "severity": "human_review_pending",
                "risk_level": RISK_NORMAL,
            },
            suggestion={
                "title": "UAV BLB multispectral segmentation v1.0 requires human review",
                "content": (
                    f"Predicted BLB area ratio is {disease_area_ratio:.4f}. "
                    "This initial release is limited to records and visualization; it does not generate treatment advice or alerts."
                ),
                "need_expert_confirm": True,
                "actions": [],
                "knowledge_tags": ["UAV BLB", "multispectral segmentation", RELEASE_VERSION],
                "disclaimer": "Initial release testing; alerting disabled; requires human review.",
            },
        )
        result_store.save(result)
        return result

    def _validate_filename(self, filename: str | None) -> None:
        suffix = Path(filename or "").suffix.lower()
        if suffix not in {".tif", ".tiff"}:
            raise UavBlbSegmentationV1ReleaseError(
                400,
                "INVALID_MULTISPECTRAL_TIF",
                "UAV BLB segmentation v1.0 requires a readable 5-band multispectral TIF.",
                {"filename": filename, "reason": "unsupported_extension", "fallback_to_rgb_or_yolo": False},
            )

    def _validate_review(self, status: str, label: str | None) -> None:
        if status not in ALLOWED_REVIEW_STATUS:
            raise UavBlbSegmentationV1ReleaseError(
                400,
                "INVALID_HUMAN_REVIEW_STATUS",
                "human_review_status must be pending or reviewed.",
                {"human_review_status": status},
            )
        if label and label not in ALLOWED_REVIEW_LABELS:
            raise UavBlbSegmentationV1ReleaseError(
                400,
                "INVALID_HUMAN_REVIEW_LABEL",
                "human_review_label is not supported for UAV BLB segmentation v1.0 review.",
                {"human_review_label": label, "allowed_labels": sorted(ALLOWED_REVIEW_LABELS)},
            )

    def _load_and_verify_artifact_lock(self) -> dict:
        if not self.artifact_lock_path.exists():
            raise UavBlbSegmentationV1ReleaseError(
                503,
                "UAV_BLB_SEGMENTATION_V1_MODEL_UNAVAILABLE",
                "UAV BLB segmentation v1.0 artifact lock is missing.",
                {"artifact_lock": str(self.artifact_lock_path)},
            )
        lock = json.loads(self.artifact_lock_path.read_text(encoding="utf-8"))
        if lock.get("sha256", "").lower() != EXPECTED_SHA256:
            raise UavBlbSegmentationV1ReleaseError(
                503,
                "UAV_BLB_SEGMENTATION_V1_MODEL_UNAVAILABLE",
                "Artifact lock sha256 does not match the v1.0 release candidate.",
                {},
            )
        weight_path = settings.training_dir / lock["weight_path"]
        if not weight_path.exists():
            raise UavBlbSegmentationV1ReleaseError(
                503,
                "UAV_BLB_SEGMENTATION_V1_MODEL_UNAVAILABLE",
                "UAV BLB segmentation v1.0 weight is missing.",
                {"weight_path": str(weight_path)},
            )
        actual_sha = self._sha256_file(weight_path)
        if actual_sha.lower() != EXPECTED_SHA256:
            raise UavBlbSegmentationV1ReleaseError(
                503,
                "UAV_BLB_SEGMENTATION_V1_MODEL_UNAVAILABLE",
                "UAV BLB segmentation v1.0 weight sha256 verification failed.",
                {"actual_sha256": actual_sha},
            )
        return lock

    def _from_dry_run_error(self, exc: DryRunError) -> UavBlbSegmentationV1ReleaseError:
        error_code = exc.payload.get("error_code", "UAV_BLB_SEGMENTATION_V1_INFERENCE_FAILED")
        if error_code in {"DRY_RUN_MODEL_UNAVAILABLE"}:
            error_code = "UAV_BLB_SEGMENTATION_V1_MODEL_UNAVAILABLE"
        return UavBlbSegmentationV1ReleaseError(
            exc.status_code,
            error_code,
            exc.payload.get("message", "UAV BLB segmentation v1.0 failed."),
            {**exc.payload.get("detail", {}), "fallback_to_rgb_or_yolo": False},
        )

    def _parse_issue_tags(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


uav_blb_segmentation_v1_release_service = UavBlbSegmentationV1ReleaseService()
