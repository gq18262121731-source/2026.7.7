from __future__ import annotations

from app.core.logger import logger
from app.schemas.alert import AlertEvent
from app.services.realtime.websocket_manager import alert_websocket_manager


class AlertPublisher:
    async def publish(self, event: AlertEvent) -> None:
        try:
            await alert_websocket_manager.broadcast_json(event.model_dump())
        except Exception as exc:
            logger.warning("Alert publish failed: %s", exc)


alert_publisher = AlertPublisher()
