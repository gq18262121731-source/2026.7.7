from datetime import datetime

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "0.1.0",
        "mode": "production",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

