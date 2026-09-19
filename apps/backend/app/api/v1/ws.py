import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# Connection manager
class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        if device_id not in self._connections:
            self._connections[device_id] = []
        self._connections[device_id].append(websocket)
        logger.info(f"WS connected: device={device_id}, total={len(self._connections[device_id])}")

    def disconnect(self, device_id: str, websocket: WebSocket):
        if device_id in self._connections:
            self._connections[device_id].discard(websocket) if hasattr(self._connections[device_id], 'discard') else None
            try:
                self._connections[device_id].remove(websocket)
            except ValueError:
                pass
            if not self._connections[device_id]:
                del self._connections[device_id]
        logger.info(f"WS disconnected: device={device_id}")

    async def send_to_device(self, device_id: str, message: dict):
        """Send JSON message to all connections for a device."""
        if device_id not in self._connections:
            return
        dead = []
        for ws in self._connections[device_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(device_id, ws)

    async def broadcast(self, message: dict):
        """Broadcast to all connected devices."""
        for device_id in list(self._connections.keys()):
            await self.send_to_device(device_id, message)


manager = ConnectionManager()


@router.websocket("/ws/signals/{device_id}")
async def websocket_signals(websocket: WebSocket, device_id: str):
    """
    WebSocket endpoint for real-time signal updates.
    Client connects once and receives signal events as they occur.
    """
    await manager.connect(device_id, websocket)
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "device_id": device_id,
            "message": "Signal scanner connected"
        })

        # Keep connection alive, listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(data)

                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        manager.disconnect(device_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error for {device_id}: {e}")
        manager.disconnect(device_id, websocket)


def get_ws_manager() -> ConnectionManager:
    return manager
