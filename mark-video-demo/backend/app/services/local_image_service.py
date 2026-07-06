from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

from fastapi.responses import FileResponse
from PIL import Image


LOCAL_PHONE_DATASET_DIR = Path("F:/学校/病虫害识别/ai_model_training/datasets/phone_riceseg_v35m_holdout_applied")
LOCAL_UAV_DATASET_DIR = Path("F:/学校/病虫害识别/ai_model_training/datasets/rice_uav_ms_blb_cleaned408_v2")

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

_image_registry: Dict[str, Path] = {}


def iter_images(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)


def image_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            return image.size
    except Exception:
        return (1280, 960)


def source_roots() -> Dict[str, Path]:
    return {
        "phone_closeup": LOCAL_PHONE_DATASET_DIR,
        "uav_multispectral": LOCAL_UAV_DATASET_DIR,
    }


def build_image_key(path: Path) -> str:
    key = f"img_{abs(hash(str(path.resolve()).lower())):x}"
    _image_registry[key] = path
    return key


def get_image_path(image_key: str) -> Optional[Path]:
    if image_key in _image_registry:
        return _image_registry[image_key]
    for root in source_roots().values():
        for path in iter_images(root):
            if build_image_key(path) == image_key:
                return path
    return None


def image_response(image_key: str) -> FileResponse:
    path = get_image_path(image_key)
    if path is None or not path.exists():
        raise FileNotFoundError(image_key)
    return FileResponse(path)


def pick_images(scene_type: str, limit: int = 4) -> List[Path]:
    root = source_roots().get(scene_type)
    if root is None:
        return []
    images = list(iter_images(root))
    if scene_type == "phone_closeup":
        preferred = [path for path in images if any(token in path.stem.lower() for token in ["brown", "blast", "bacterial"])]
        images = preferred or images
    if scene_type == "uav_multispectral":
        preferred = [path for path in images if "blb" in path.stem.lower()]
        images = preferred or images
    return images[:limit]


def public_image_url(path: Path) -> str:
    return f"/api/assets/images/{build_image_key(path)}"


def dataset_status() -> dict:
    phone_count = len(list(iter_images(LOCAL_PHONE_DATASET_DIR)))
    uav_count = len(list(iter_images(LOCAL_UAV_DATASET_DIR)))
    return {
        "phone_dataset_path": str(LOCAL_PHONE_DATASET_DIR),
        "uav_dataset_path": str(LOCAL_UAV_DATASET_DIR),
        "phone_image_count": phone_count,
        "uav_image_count": uav_count,
        "index_status": "ready" if phone_count and uav_count else "partial",
    }

