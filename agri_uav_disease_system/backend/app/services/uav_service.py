from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageDraw

from app.core.config import settings
from app.core.exceptions import AppException
from app.database.uav_repositories import UavRepository, uav_repository
from app.schemas.detection_result import DetectionResult
from app.schemas.upload import DetectImageMetadata
from app.schemas.uav import (
    AbnormalRegion,
    AbnormalRegionListResponse,
    UavDryRunRequest,
    UavDryRunResponse,
    UavImage,
    UavIndexListResponse,
    UavIndexResult,
    UavTask,
    UavTaskCreate,
    UavTaskListResponse,
)


PROFILE_VALUES = {
    "mild_abnormal": ("mild", 0.08, 0.06),
    "moderate_abnormal": ("moderate", 0.18, 0.14),
    "severe_abnormal": ("severe", 0.32, 0.26),
}


class UavService:
    def __init__(self, repository: UavRepository | None = None) -> None:
        self.repository = repository or uav_repository

    def create_task(self, request: UavTaskCreate) -> UavTask:
        now = self._now()
        task = UavTask(
            uav_task_id=f"UAV_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
            field_id=request.field_id,
            task_name=request.task_name,
            flight_date=request.flight_date,
            sensor_type=request.sensor_type,
            data_mode=request.data_mode,
            growth_stage=request.growth_stage,
            weather_text=request.weather_text,
            status="created",
            summary="UAV 任务已创建，等待 dry-run 或数据处理。",
            is_mock=request.data_mode == "dry_run",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_task(task)
        return task

    def list_tasks(self, field_id: str | None = None, page: int = 1, page_size: int = 50) -> UavTaskListResponse:
        return UavTaskListResponse(
            items=self.repository.list_tasks(field_id=field_id, page=page, page_size=page_size),
            total=self.repository.count_tasks(field_id=field_id),
            page=page,
            page_size=page_size,
        )

    def get_task(self, uav_task_id: str) -> UavTask:
        task = self.repository.get_task(uav_task_id)
        if not task:
            raise AppException("UAV_TASK_NOT_FOUND", "UAV 任务不存在", {"uav_task_id": uav_task_id})
        return task

    def dry_run(self, uav_task_id: str, request: UavDryRunRequest) -> UavDryRunResponse:
        task = self.repository.get_task(uav_task_id)
        if not task:
            task = self.create_task(
                UavTaskCreate(
                    field_id=request.field_id,
                    task_name=request.task_name or f"{request.field_id or '未指定田块'} UAV dry-run",
                    sensor_type=request.sensor_type,
                    data_mode="dry_run",
                    growth_stage=request.growth_stage,
                    weather_text=request.weather_text,
                )
            )
            uav_task_id = task.uav_task_id

        now = self._now()
        level, ndvi_ratio, ndre_ratio = PROFILE_VALUES.get(request.dry_run_profile, PROFILE_VALUES["moderate_abnormal"])
        task.status = "completed"
        task.data_mode = "dry_run"
        task.is_mock = True
        task.field_id = request.field_id or task.field_id
        task.growth_stage = request.growth_stage or task.growth_stage
        task.weather_text = request.weather_text or task.weather_text
        task.summary = "dry-run 已生成 NDVI/NDRE 占位指数结果和待手机复查异常区域。"
        task.updated_at = now
        self.repository.save_task(task)

        task_dir = settings.static_dir / "uav" / uav_task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        ndvi_url = self._write_placeholder(task_dir / "ndvi.png", "NDVI dry-run", "#2f9e44", "#f59f00")
        ndre_url = self._write_placeholder(task_dir / "ndre.png", "NDRE dry-run", "#1971c2", "#ffd43b")
        region_url = self._write_placeholder(task_dir / "region_001.png", "Abnormal region", "#495057", "#fa5252")

        indices = [
            UavIndexResult(
                index_result_id=f"idx_{uuid4().hex[:10]}",
                uav_task_id=uav_task_id,
                field_id=task.field_id,
                index_type="ndvi",
                index_image_url=ndvi_url,
                min_value=0.21,
                max_value=0.82,
                mean_value=0.58,
                threshold_used=0.42,
                abnormal_area_ratio=ndvi_ratio,
                data_mode="dry_run",
                is_mock=True,
                created_at=now,
            ),
            UavIndexResult(
                index_result_id=f"idx_{uuid4().hex[:10]}",
                uav_task_id=uav_task_id,
                field_id=task.field_id,
                index_type="ndre",
                index_image_url=ndre_url,
                min_value=0.12,
                max_value=0.61,
                mean_value=0.39,
                threshold_used=0.28,
                abnormal_area_ratio=ndre_ratio,
                data_mode="dry_run",
                is_mock=True,
                created_at=now,
            ),
        ]
        for item in indices:
            self.repository.save_index(item)
            self.repository.save_image(
                UavImage(
                    uav_image_id=f"uav_img_{uuid4().hex[:10]}",
                    uav_task_id=uav_task_id,
                    field_id=task.field_id,
                    image_url=item.index_image_url,
                    image_type="index",
                    index_type=item.index_type,
                    created_at=now,
                )
            )

        region = AbnormalRegion(
            region_id=f"REGION_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
            uav_task_id=uav_task_id,
            field_id=task.field_id,
            region_name="dry-run 异常区域 1",
            region_image_url=region_url,
            center_lat=None,
            center_lng=None,
            abnormal_type="vegetation_stress",
            abnormal_level=level,
            abnormal_area_ratio=max(ndvi_ratio, ndre_ratio),
            source_index_type="dry_run",
            confirm_status="phone_followup_pending",
            created_at=now,
            updated_at=now,
        )
        self.repository.save_region(region)
        return UavDryRunResponse(
            uav_task_id=uav_task_id,
            field_id=task.field_id,
            status=task.status,
            indices=indices,
            abnormal_regions=[region],
        )

    def list_indices(self, uav_task_id: str) -> UavIndexListResponse:
        items = self.repository.list_indices(uav_task_id)
        return UavIndexListResponse(items=items, total=len(items))

    def list_regions(self, uav_task_id: str | None = None, field_id: str | None = None) -> AbnormalRegionListResponse:
        items = [self._with_phone_inference(region) for region in self.repository.list_regions(uav_task_id, field_id)]
        return AbnormalRegionListResponse(items=items, total=len(items))

    def get_region(self, region_id: str) -> AbnormalRegion:
        region = self.repository.get_region(region_id)
        if not region:
            raise AppException("ABNORMAL_REGION_NOT_FOUND", "异常区域不存在", {"region_id": region_id})
        return self._with_phone_inference(region)

    async def phone_followup(self, region_id: str, file: UploadFile, metadata: DetectImageMetadata) -> DetectionResult:
        region = self.get_region(region_id)
        metadata.field_id = metadata.field_id or region.field_id
        metadata.uav_task_id = metadata.uav_task_id or region.uav_task_id
        metadata.abnormal_region_id = region_id
        metadata.source_type = metadata.source_type or "phone_followup"
        metadata.target_type = metadata.target_type or "disease"
        from app.services.detection_service import detection_service

        return await detection_service.detect_upload(file, metadata)

    def handle_phone_followup_result(self, result: DetectionResult) -> None:
        if not result.abnormal_region_id:
            return
        region = self.repository.get_region(result.abnormal_region_id)
        if not region:
            return
        confidence = result.summary.max_confidence
        disease = result.summary.main_disease
        if not disease:
            status = "phone_rejected"
        elif confidence < 0.5:
            status = "phone_uncertain"
        else:
            status = "phone_confirmed"
        region.linked_phone_image_id = result.image_id
        region.linked_record_id = result.record_id
        region.confirmed_disease_type = disease
        region.confirm_confidence = confidence
        region.confirm_status = status
        region.confirm_source = "phone_model"
        region.confirmed_at = result.timestamp
        region.updated_at = self._now()
        self.repository.save_region(region)

    def _with_phone_inference(self, region: AbnormalRegion) -> AbnormalRegion:
        if region.linked_record_id:
            from app.services.storage.result_store import result_store

            record = result_store.get(region.linked_record_id)
            if record:
                region.phone_inference = {
                    "record_id": record.record_id,
                    "image_id": record.image_id,
                    "disease_type": record.summary.main_disease,
                    "confidence": record.summary.max_confidence,
                    "severity_level": record.summary.severity,
                    "risk_level": record.summary.risk_level,
                    "result_image_url": record.result_image_url,
                }
        return region

    def _write_placeholder(self, path, title: str, background: str, accent: str) -> str:
        image = Image.new("RGB", (640, 360), color=background)
        draw = ImageDraw.Draw(image)
        draw.rectangle([360, 80, 560, 250], outline=accent, width=8)
        draw.rectangle([390, 110, 530, 220], fill=accent)
        draw.text((32, 28), title, fill="white")
        draw.text((32, 310), "dry-run/mock visualization", fill="white")
        image.save(path)
        relative = path.relative_to(settings.static_dir).as_posix()
        return f"/static/{relative}"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


uav_service = UavService()
