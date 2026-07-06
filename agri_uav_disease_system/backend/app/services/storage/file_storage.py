from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.constants import ERROR_FILE_TOO_LARGE, ERROR_INVALID_IMAGE, ERROR_STORAGE
from app.core.exceptions import AppException


class FileStorageService:
    def ensure_dirs(self) -> None:
        settings.original_dir.mkdir(parents=True, exist_ok=True)
        settings.result_dir.mkdir(parents=True, exist_ok=True)

    def check_storage(self) -> str:
        try:
            self.ensure_dirs()
            test_file = settings.static_dir / ".storage_check"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            return "ok"
        except OSError:
            return "error"

    async def save_upload(self, file: UploadFile) -> tuple[str, str, str]:
        self.ensure_dirs()
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in settings.allowed_image_extensions:
            raise AppException(ERROR_INVALID_IMAGE, "\u4e0a\u4f20\u6587\u4ef6\u4e0d\u662f\u6709\u6548\u56fe\u7247", {"filename": file.filename})

        image_id = f"img_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        filename = f"{image_id}{suffix}"
        target_path = settings.original_dir / filename

        size = 0
        try:
            with target_path.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_size_bytes:
                        target_path.unlink(missing_ok=True)
                        raise AppException(
                            ERROR_FILE_TOO_LARGE,
                            "\u4e0a\u4f20\u6587\u4ef6\u8d85\u8fc7\u5927\u5c0f\u9650\u5236",
                            {"max_upload_size_mb": settings.max_upload_size_mb},
                        )
                    output.write(chunk)
            if size <= 0:
                target_path.unlink(missing_ok=True)
                raise AppException(ERROR_INVALID_IMAGE, "\u4e0a\u4f20\u6587\u4ef6\u4e0d\u662f\u6709\u6548\u56fe\u7247", {"reason": "empty_file"})
        except AppException:
            raise
        except OSError as exc:
            raise AppException(ERROR_STORAGE, "\u539f\u56fe\u4fdd\u5b58\u5931\u8d25", {"reason": str(exc)}) from exc
        finally:
            await file.close()

        return image_id, str(target_path), f"/static/original/{filename}"

    def copy_as_result_when_no_detection(self, original_path: str, output_path: str) -> None:
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original_path, output_path)
        except OSError as exc:
            raise AppException(ERROR_STORAGE, "\u65e0\u68c0\u6d4b\u7ed3\u679c\u56fe\u4fdd\u5b58\u5931\u8d25", {"reason": str(exc)}) from exc


file_storage_service = FileStorageService()
