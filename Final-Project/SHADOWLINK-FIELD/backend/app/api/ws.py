import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
from app.core.database import SessionLocal
from app.services.message_engine import MessageEngine
from app.adapters.simulation import simulation_adapter

router = APIRouter(tags=["Live WebSocket Feed"])


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


@router.websocket("/ws/updates")
async def websocket_updates(websocket: WebSocket):
    """Provides real-time queue statistics and transport status to connected clients."""
    await manager.connect(websocket)
    try:
        while True:
            # Query current queue stats
            session = SessionLocal()
            try:
                stats = MessageEngine.get_queue_stats(session)
                stats["transport"] = simulation_adapter.get_status()
                await websocket.send_json({"type": "QUEUE_STATS", "data": stats})
            finally:
                session.close()

            await asyncio.sleep(1.5)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
