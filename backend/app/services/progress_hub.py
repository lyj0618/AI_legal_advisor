"""文档处理进度 WebSocket 广播中心。"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ProgressHub:
    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms.setdefault(room, set()).add(ws)

    async def disconnect(self, room: str, ws: WebSocket) -> None:
        async with self._lock:
            peers = self._rooms.get(room)
            if not peers:
                return
            peers.discard(ws)
            if not peers:
                self._rooms.pop(room, None)

    async def broadcast(self, room: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            peers = list(self._rooms.get(room, set()))
        if not peers:
            return
        text = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in peers:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                room_set = self._rooms.get(room)
                if room_set:
                    for ws in dead:
                        room_set.discard(ws)


progress_hub = ProgressHub()
