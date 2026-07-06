from fastapi import APIRouter

from app.services.data_store import get_models

router = APIRouter(tags=["models"])


@router.get("/models")
def models() -> dict:
    return get_models()

