from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import AppException
from app.database.field_repositories import FieldRepository, field_repository
from app.schemas.field import FieldCreate, FieldInfo, FieldListResponse, FieldUpdate


class FieldService:
    def __init__(self, repository: FieldRepository | None = None) -> None:
        self.repository = repository or field_repository

    def create(self, request: FieldCreate) -> FieldInfo:
        return self.repository.create(request, self._now())

    def list_fields(self, page: int = 1, page_size: int = 50, status: str | None = None) -> FieldListResponse:
        return FieldListResponse(
            items=self.repository.list_fields(page=page, page_size=page_size, status=status),
            total=self.repository.count(status=status),
            page=page,
            page_size=page_size,
        )

    def get(self, field_id: str) -> FieldInfo:
        field = self.repository.get(field_id)
        if not field:
            raise AppException("FIELD_NOT_FOUND", "田块不存在", {"field_id": field_id})
        return field

    def update(self, field_id: str, request: FieldUpdate) -> FieldInfo:
        field = self.repository.update(field_id, request, self._now())
        if not field:
            raise AppException("FIELD_NOT_FOUND", "田块不存在", {"field_id": field_id})
        return field

    def archive(self, field_id: str) -> FieldInfo:
        field = self.repository.archive(field_id, self._now())
        if not field:
            raise AppException("FIELD_NOT_FOUND", "田块不存在", {"field_id": field_id})
        return field

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


field_service = FieldService()
