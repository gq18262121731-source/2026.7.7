from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.realtime.websocket_manager import alert_websocket_manager, task_websocket_manager, websocket_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/results")
async def ws_results(websocket: WebSocket) -> None:
    await websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(websocket)
    except Exception:
        websocket_manager.disconnect(websocket)


@router.websocket("/ws/tasks")
async def ws_tasks(websocket: WebSocket) -> None:
    await task_websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        task_websocket_manager.disconnect(websocket)
    except Exception:
        task_websocket_manager.disconnect(websocket)


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket) -> None:
    await alert_websocket_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_websocket_manager.disconnect(websocket)
    except Exception:
        alert_websocket_manager.disconnect(websocket)
