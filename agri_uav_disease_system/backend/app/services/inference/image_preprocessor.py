from __future__ import annotations

from PIL import Image

from app.core.constants import ERROR_INVALID_IMAGE
from app.core.exceptions import AppException


class ImagePreprocessor:
    def inspect_image(self, image_path: str) -> tuple[int, int]:
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                return image.size
        except Exception as exc:
            raise AppException(ERROR_INVALID_IMAGE, "\u4e0a\u4f20\u6587\u4ef6\u4e0d\u662f\u6709\u6548\u56fe\u7247", {"path": image_path}) from exc
