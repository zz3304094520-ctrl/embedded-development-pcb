import asyncio
import logging
from typing import Any

from fastapi import WebSocket


logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        payload = {"event": event, "data": data}
        async with self._lock:
            connections = list(self._connections)

        dead_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.debug("清理已失效的 WebSocket 连接", exc_info=True)
                dead_connections.append(websocket)

        if dead_connections:
            async with self._lock:
                for websocket in dead_connections:
                    self._connections.discard(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


websocket_manager = WebSocketManager()

