from __future__ import annotations

from fastapi import WebSocket

from app.core.logger import logger


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    @property
    def client_count(self) -> int:
        return len(self.active_connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. clients=%s", self.client_count)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected. clients=%s", self.client_count)

    async def broadcast_json(self, payload: dict) -> None:
        failed: list[WebSocket] = []
        for websocket in list(self.active_connections):
            try:
                await websocket.send_json(payload)
            except Exception as exc:
                logger.warning("WebSocket push failed: %s", exc)
                failed.append(websocket)
        for websocket in failed:
            self.disconnect(websocket)


websocket_manager = WebSocketManager()
task_websocket_manager = WebSocketManager()
alert_websocket_manager = WebSocketManager()
