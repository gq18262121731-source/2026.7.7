from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.platform import DetectionRequest
from app.services.data_store import detect_by_id, get_task, list_samples
from app.services.dataset_index_service import build_samples

router = APIRouter(tags=["detect"])


@router.post("/detect")
def detect(payload: DetectionRequest) -> dict:
    try:
        return detect_by_id(payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "IMAGE_NOT_FOUND", "message": str(exc)}) from exc


@router.get("/samples")
def samples() -> dict:
    return list_samples()


@router.post("/detect/upload")
async def detect_upload(model_key: str, file: UploadFile = File(...)) -> dict:
    filename = file.filename or ""
    stem = filename.rsplit(".", 1)[0]
    sample = next((item for item in build_samples() if stem.lower() in item["display_name"].lower()), None)
    try:
        payload = {"model_key": model_key, "operator": "upload_user"}
        if sample:
            payload["sample_key"] = sample["sample_key"]
        return detect_by_id(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "UPLOAD_NO_MATCH", "message": str(exc)}) from exc


@router.get("/tasks/{task_id}")
def task(task_id: str) -> dict:
    result = get_task(task_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": task_id})
    return result

