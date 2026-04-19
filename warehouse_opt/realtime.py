from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import WebSocket


class RealtimeHub:
    """In-process pub/sub hub for websocket and polling clients."""

    def __init__(self) -> None:
        self._clients: Dict[str, List[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients[job_id].append(websocket)

    async def disconnect(self, job_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._clients[job_id]:
                self._clients[job_id].remove(websocket)

    async def publish(self, job_id: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            clients = list(self._clients[job_id])

        stale = []
        for ws in clients:
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)

        if stale:
            async with self._lock:
                for ws in stale:
                    if ws in self._clients[job_id]:
                        self._clients[job_id].remove(ws)
