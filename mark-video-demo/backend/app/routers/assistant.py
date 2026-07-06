from fastapi import APIRouter

from app.schemas.platform import AssistantRequest
from app.services.data_store import assistant_reply

router = APIRouter(tags=["assistant"])


@router.post("/assistant")
def assistant(payload: AssistantRequest) -> dict:
    return assistant_reply(payload.message, payload.mode, payload.context)

