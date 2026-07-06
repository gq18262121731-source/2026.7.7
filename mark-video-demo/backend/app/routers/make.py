from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.services.data_store import get_make_status, trigger_make

router = APIRouter(tags=["make"])


class MakeTriggerPayload(BaseModel):
    task_id: Optional[str] = None


@router.get("/make/status")
def make_status() -> dict:
    return get_make_status()


@router.post("/make/trigger")
def make_trigger(payload: MakeTriggerPayload) -> dict:
    return trigger_make(payload.task_id)

