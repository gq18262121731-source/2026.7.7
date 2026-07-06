from __future__ import annotations

from app.core.logger import logger
from app.schemas.detection_result import DetectionResult
from app.services.realtime.websocket_manager import websocket_manager


class DetectionResultPublisher:
    async def publish(self, result: DetectionResult) -> None:
        try:
            await websocket_manager.broadcast_json(result.model_dump())
        except Exception as exc:
            logger.warning("Detection result publish failed: %s", exc)


detection_result_publisher = DetectionResultPublisher()
