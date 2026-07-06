from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.get("/capabilities")
async def upload_capabilities() -> dict:
    return {
        "single_image_upload": True,
        "batch_upload": False,
        "video_upload": False,
        "note": "第一阶段 MVP 仅开放单图识别主链路。",
    }
