from fastapi import APIRouter, HTTPException

from app.services.local_image_service import image_response

router = APIRouter(tags=["assets"])


@router.get("/assets/images/{image_key}")
def local_image(image_key: str):
    try:
        return image_response(image_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"code": "IMAGE_NOT_FOUND", "message": image_key}) from exc

