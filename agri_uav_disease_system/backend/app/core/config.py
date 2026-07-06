from __future__ import annotations

import os
from pathlib import Path


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _env_or_default(name: str, default: str) -> str:
    return os.getenv(name) or default


class Settings:
    app_name: str = "\u4e09\u4e0b\u4e61\u65e0\u4eba\u673a\u6c34\u7a3b\u75c5\u866b\u5bb3\u8bc6\u522b\u7cfb\u7edf"
    app_version: str = "mvp-1"

    app_dir: Path = Path(__file__).resolve().parents[1]
    backend_dir: Path = Path(__file__).resolve().parents[2]
    workspace_dir: Path = backend_dir.parent.parent
    training_dir: Path = workspace_dir / "ai_model_training"

    static_dir: Path = app_dir / "static"
    original_dir: Path = static_dir / "original"
    result_dir: Path = static_dir / "result"
    database_path: Path = Path(os.getenv("DATABASE_PATH", str(backend_dir / "agri_uav_disease_mvp.sqlite3")))

    max_upload_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    allowed_image_extensions: set[str] = {
        item.strip().lower()
        for item in os.getenv("ALLOWED_IMAGE_EXTENSIONS", ".jpg,.jpeg,.png,.webp").split(",")
        if item.strip()
    }

    mock_seed: int = int(os.getenv("MOCK_SEED", "20260622"))
    detector_mode: str = os.getenv("DETECTOR_MODE", "mock")
    model_path: str = os.getenv("MODEL_PATH", "")
    uav_model_path: str = _env_or_default("UAV_MODEL_PATH", "")
    uav_blb_model_path: str = _env_or_default("UAV_BLB_MODEL_PATH", "")
    uav_blb_model_name: str = os.getenv("UAV_BLB_MODEL_NAME", "uav_blb_disease_yolo")
    uav_blb_model_version: str = os.getenv("UAV_BLB_MODEL_VERSION", "smoke_epoch1_blb_20260623")
    enable_uav_blb_smoke: bool = os.getenv("ENABLE_UAV_BLB_SMOKE", "false").lower() == "true"
    uav_blb_smoke_confidence: float = float(os.getenv("UAV_BLB_SMOKE_CONFIDENCE", "0.25"))
    uav_blb_experimental_model_path: str = _env_or_default("UAV_BLB_EXPERIMENTAL_MODEL_PATH", "")
    uav_blb_experimental_model_name: str = os.getenv("UAV_BLB_EXPERIMENTAL_MODEL_NAME", "uav_blb_disease_yolo")
    uav_blb_experimental_model_version: str = os.getenv(
        "UAV_BLB_EXPERIMENTAL_MODEL_VERSION", "experimental_preview408_epoch5_20260623"
    )
    enable_uav_blb_experimental: bool = os.getenv("ENABLE_UAV_BLB_EXPERIMENTAL", "false").lower() == "true"
    uav_blb_experimental_confidence: float = float(os.getenv("UAV_BLB_EXPERIMENTAL_CONFIDENCE", "0.25"))
    phone_model_path: str = _env_or_default("PHONE_MODEL_PATH", "")
    phone_experimental_model_path: str = _env_or_default("PHONE_EXPERIMENTAL_MODEL_PATH", "")
    phone_experimental_model_name: str = os.getenv("PHONE_EXPERIMENTAL_MODEL_NAME", "phone_rice_disease_yolo")
    phone_experimental_model_version: str = os.getenv(
        "PHONE_EXPERIMENTAL_MODEL_VERSION", "experimental_riceleafdiseasebd_3epoch_20260623"
    )
    enable_phone_experimental: bool = os.getenv("ENABLE_PHONE_EXPERIMENTAL", "false").lower() == "true"
    phone_experimental_confidence: float = float(os.getenv("PHONE_EXPERIMENTAL_CONFIDENCE", "0.25"))
    smoke_yolo_confidence: float = float(os.getenv("SMOKE_YOLO_CONFIDENCE", "0.25"))
    default_source_type: str = os.getenv("DEFAULT_SOURCE_TYPE", "manual_upload")
    alert_cooldown_seconds: int = int(os.getenv("ALERT_COOLDOWN_SECONDS", "3600"))

    severity_light_max_area_ratio: float = float(os.getenv("SEVERITY_LIGHT_MAX_AREA_RATIO", "0.05"))
    severity_medium_max_area_ratio: float = float(os.getenv("SEVERITY_MEDIUM_MAX_AREA_RATIO", "0.20"))
    severity_many_detections_threshold: int = int(os.getenv("SEVERITY_MANY_DETECTIONS_THRESHOLD", "3"))

    mock_classes: list[str] = _split_csv(
        os.getenv(
            "MOCK_CLASSES",
            "\u7a3b\u761f\u75c5,\u7eb9\u67af\u75c5,\u7a3b\u66f2\u75c5,\u7a3b\u98de\u8671,\u7a3b\u7eb5\u5377\u53f6\u879f",
        )
    )

    cors_origins: list[str] = _split_csv(
        os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
        )
    )
    cors_allow_credentials: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
    cors_allow_methods: list[str] = _split_csv(os.getenv("CORS_ALLOW_METHODS", "GET,POST,OPTIONS"))
    cors_allow_headers: list[str] = _split_csv(os.getenv("CORS_ALLOW_HEADERS", "*"))

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


settings = Settings()
