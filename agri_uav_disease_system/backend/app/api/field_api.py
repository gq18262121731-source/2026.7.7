from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.field import FieldCreate, FieldInfo, FieldListResponse, FieldUpdate
from app.services.field_service import field_service

router = APIRouter(prefix="/api/fields", tags=["fields"])


@router.post("", response_model=FieldInfo)
async def create_field(request: FieldCreate) -> FieldInfo:
    return field_service.create(request)


@router.get("", response_model=FieldListResponse)
async def list_fields(
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> FieldListResponse:
    return field_service.list_fields(page=page, page_size=page_size, status=status)


@router.get("/{field_id}", response_model=FieldInfo)
async def get_field(field_id: str) -> FieldInfo:
    return field_service.get(field_id)


@router.put("/{field_id}", response_model=FieldInfo)
async def update_field(field_id: str, request: FieldUpdate) -> FieldInfo:
    return field_service.update(field_id, request)


@router.delete("/{field_id}", response_model=FieldInfo)
async def archive_field(field_id: str) -> FieldInfo:
    return field_service.archive(field_id)
