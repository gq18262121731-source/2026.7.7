from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.core.config import settings
from app.database.database import check_database
from app.schemas.status import DemoSafetyStatus, ModelPathStatus, ModelsCatalog, ModelsStatusResponse, StatusResponse
from app.services.inference.model_display import get_model_display_info
from app.services.inference.model_manager import model_manager
from app.services.realtime.websocket_manager import websocket_manager
from app.services.storage.file_storage import file_storage_service

router = APIRouter(tags=["status"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/status", response_model=StatusResponse)
async def system_status() -> StatusResponse:
    detector = model_manager.get_detector(settings.default_source_type)
    models_status = build_models_status()
    database_status = check_database()
    return StatusResponse(
        service_status="running",
        model_loaded=model_manager.is_loaded(),
        model_name=detector.name,
        model_version=detector.version,
        detector_mode=model_manager.actual_detector_mode(settings.default_source_type),
        database_status=database_status,
        storage_status=file_storage_service.check_storage(),
        websocket_clients=websocket_manager.client_count,
        capabilities={
            "single_image_detection": True,
            "batch_detection": True,
            "dashboard_api": True,
            "mobile_api": True,
            "alert_governance": True,
            "ws_results": True,
            "ws_tasks": True,
            "ws_alerts": True,
            "real_model_ready": not models_status.fallback_to_mock,
            "mock_mode": model_manager.actual_detector_mode(settings.default_source_type) == "mock",
        },
        models={
            "detector_mode": model_manager.actual_detector_mode(settings.default_source_type),
            "current_model": detector.name,
            "uav_model_path_configured": bool(settings.uav_model_path),
            "phone_model_path_configured": bool(settings.phone_model_path),
        },
        storage={
            "database_status": database_status,
            "static_original_writable": _path_writable(settings.original_dir),
            "static_result_writable": _path_writable(settings.result_dir),
        },
        error_message=None,
    )


@router.get("/api/models/status", response_model=ModelsStatusResponse)
async def models_status() -> ModelsStatusResponse:
    return build_models_status()


@router.get("/api/models/demo-safety", response_model=DemoSafetyStatus)
async def models_demo_safety() -> DemoSafetyStatus:
    return build_demo_safety_status()


def build_models_status() -> ModelsStatusResponse:
    detector = model_manager.get_detector(settings.default_source_type)
    smoke_status = model_manager.smoke_status()
    uav_crop_model = _model_path_status(
        "uav_rice_disease_yolo",
        settings.uav_model_path,
        loaded=smoke_status["uav_smoke_loaded"],
        model_stage="smoke",
        is_smoke=True,
        current_target_type="crop_object",
        formal_metric_available=False,
    )
    uav_blb_model = _model_path_status(
        settings.uav_blb_model_name,
        settings.uav_blb_model_path,
        loaded=smoke_status["uav_blb_smoke_loaded"],
        model_stage="smoke",
        is_smoke=True,
        current_target_type="disease",
        formal_metric_available=False,
    )
    uav_blb_experimental_model = _model_path_status(
        settings.uav_blb_experimental_model_name,
        settings.uav_blb_experimental_model_path,
        loaded=smoke_status["uav_blb_experimental_loaded"],
        model_stage="experimental",
        is_smoke=False,
        current_target_type="disease",
        formal_metric_available=False,
        dataset_actual_images=408,
        dataset_target_name="preview_1000",
        is_true_multichannel_model=False,
    )
    phone_model = _model_path_status(
        "phone_rice_disease_yolo",
        settings.phone_model_path,
        loaded=smoke_status["phone_smoke_loaded"],
        model_stage="smoke",
        is_smoke=True,
        current_target_type="disease",
        formal_metric_available=False,
    )
    phone_experimental_model = _model_path_status(
        settings.phone_experimental_model_name,
        settings.phone_experimental_model_path,
        loaded=smoke_status["phone_experimental_loaded"],
        model_stage="experimental",
        is_smoke=False,
        current_target_type="disease",
        formal_metric_available=False,
        dataset_images=7575,
        dataset_bbox=69769,
        healthy_excluded=True,
        class_mapping_strategy="source_directory_based_remap",
    )
    mock_model = _model_path_status(
        "mock_disease_detector",
        "",
        loaded=True,
        model_stage="mock",
        is_smoke=False,
        current_target_type=None,
        formal_metric_available=False,
    )
    models = ModelsCatalog(
        phone_model=phone_model,
        phone_experimental_model=phone_experimental_model,
        uav_crop_model=uav_crop_model,
        uav_blb_model=uav_blb_model,
        uav_blb_experimental_model=uav_blb_experimental_model,
        mock_model=mock_model,
    )
    return ModelsStatusResponse(
        detector_mode=model_manager.actual_detector_mode(settings.default_source_type),
        active_model_name=detector.name,
        active_model_version=detector.version,
        uav_model=uav_crop_model,
        uav_crop_model=uav_crop_model,
        uav_blb_model=uav_blb_model,
        uav_blb_experimental_model=uav_blb_experimental_model,
        phone_model=phone_model,
        phone_experimental_model=phone_experimental_model,
        mock_model=mock_model,
        models=models,
        active_routing={
            "phone_rgb": "phone_rice_disease_yolo smoke",
            "manual_upload": "phone_rice_disease_yolo smoke",
            "phone_rgb_with_model_hint_phone_exp": f"{settings.phone_experimental_model_name} disease experimental",
            "manual_upload_with_model_stage_hint_experimental": f"{settings.phone_experimental_model_name} disease experimental",
            "uav_default": "uav_rice_disease_yolo crop_object smoke",
            "uav_without_hint": "uav_rice_disease_yolo crop_object smoke",
            "uav_with_model_hint_uav_blb": f"{settings.uav_blb_model_name} disease smoke",
            "uav_with_target_type_disease": f"{settings.uav_blb_model_name} disease smoke",
            "uav_with_model_hint_uav_blb_exp": f"{settings.uav_blb_experimental_model_name} disease experimental",
            "uav_with_model_stage_hint_experimental": f"{settings.uav_blb_experimental_model_name} disease experimental",
            "experimental_unavailable": "mock_disease_detector fallback; no silent downgrade to smoke",
            "unavailable": "mock_disease_detector fallback",
            "unknown": "mock_disease_detector fallback",
        },
        fallback_to_mock=all(
            [
                smoke_status["phone_fallback_to_mock"],
                smoke_status["phone_experimental_fallback_to_mock"],
                smoke_status["uav_fallback_to_mock"],
                smoke_status["uav_blb_fallback_to_mock"],
                smoke_status["uav_blb_experimental_fallback_to_mock"],
            ]
        ),
        demo_safety=build_demo_safety_status(),
    )


def build_demo_safety_status() -> DemoSafetyStatus:
    smoke_status = model_manager.smoke_status()
    has_smoke_models = any(
        [
            smoke_status["phone_smoke_loaded"],
            smoke_status["uav_smoke_loaded"],
            smoke_status["uav_blb_smoke_loaded"],
        ]
    )
    return DemoSafetyStatus(
        demo_safe=True,
        has_smoke_models=has_smoke_models,
        has_formal_models=False,
        formal_metric_available=False,
        warnings=[
            "All connected YOLO weights are smoke or experimental artifacts, not formal models.",
            "UAV rice_panicle route is crop_object only and must not be shown as disease detection.",
            "UAV BLB 408 is experimental_only and based on constrained-408 RGB preview renders.",
            "Phone RiceLeafDiseaseBD 3 epoch is experimental_only and not formal model performance.",
            "Healthy is excluded from phone experimental disease detection classes.",
            "RiceLeafDiseaseBD source_directory_based_remap is a documented data-risk boundary.",
            "Mock fallback is simulated output for integration safety.",
            "Do not display precision/recall/mAP/F1 as formal performance.",
        ],
        display_rules=[
            "When is_smoke=true, show smoke-only engineering verification.",
            "When model_stage=experimental, show experimental-only verification and no formal metrics.",
            "phone experimental model is experimental_only and must display an experimental warning.",
            "Healthy must not be shown as a disease detection class.",
            "source_directory_based_remap must be displayed as a data-risk note for phone experimental results.",
            "When dataset_target_name=preview_1000, also show actual_samples=408.",
            "RGB preview render must not be displayed as a true multi-channel multispectral model.",
            "When current_target_type=crop_object, never label the result as disease detection.",
            "When fallback_to_mock=true, show Mock fallback clearly.",
        ],
    )


def _model_path_status(
    name: str,
    path_value: str,
    loaded: bool | None = None,
    model_stage: str | None = None,
    is_smoke: bool | None = None,
    current_target_type: str | None = None,
    formal_metric_available: bool | None = None,
    dataset_actual_images: int | None = None,
    dataset_target_name: str | None = None,
    is_true_multichannel_model: bool | None = None,
    dataset_images: int | None = None,
    dataset_bbox: int | None = None,
    healthy_excluded: bool | None = None,
    class_mapping_strategy: str | None = None,
) -> ModelPathStatus:
    path = Path(path_value) if path_value else None
    path_exists = bool(path and path.exists())
    display = get_model_display_info(name, model_stage)
    return ModelPathStatus(
        name=name,
        display_name=display.display_name,
        path=str(path) if path else None,
        path_exists=path_exists,
        ready=bool(path and path.is_file()),
        loaded=loaded,
        model_stage=model_stage,
        is_smoke=is_smoke,
        current_target_type=current_target_type,
        category_type=current_target_type,
        formal_metric_available=formal_metric_available,
        class_codes=display.class_codes,
        source_types=display.source_types,
        route_condition=display.route_condition,
        warning=display.warning,
        usage_scope=display.usage_scope,
        capability_level=display.capability_level,
        dataset_actual_images=dataset_actual_images,
        dataset_target_name=dataset_target_name,
        is_true_multichannel_model=is_true_multichannel_model,
        dataset_images=dataset_images,
        dataset_bbox=dataset_bbox,
        healthy_excluded=healthy_excluded,
        class_mapping_strategy=class_mapping_strategy,
    )


def _path_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".write_check"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False
