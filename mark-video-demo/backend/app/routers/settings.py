from fastapi import APIRouter

from app.schemas.platform import SettingsPayload
from app.services.data_store import get_settings, update_settings

router = APIRouter(tags=["settings"])


@router.get("/settings")
def settings() -> dict:
    return get_settings()


@router.post("/settings")
def save_settings(payload: SettingsPayload) -> dict:
    return update_settings(payload.model_dump())

