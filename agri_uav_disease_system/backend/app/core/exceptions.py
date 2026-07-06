from __future__ import annotations

from typing import Any


class AppException(Exception):
    def __init__(self, error_code: str, message: str, detail: dict[str, Any] | None = None) -> None:
        self.error_code = error_code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)
