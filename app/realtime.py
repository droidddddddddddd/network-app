"""In-memory WebSocket hub (single web instance — matches Render free tier)."""
import asyncio
from collections import defaultdict
from fastapi import WebSocket


class Hub:
    def __init__(self):
        self.users: dict[int, set[WebSocket]] = defaultdict(set)
        self.rooms: dict[int, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

        self.sock_loop: dict = {}  # websocket -> the event loop that owns it

    def register(self, ws):
        self.sock_loop[ws] = asyncio.get_running_loop()

    def unregister(self, ws):
        self.sock_loop.pop(ws, None)

    async def _send_one(self, sockets, ws, msg):
        try:
            await ws.send_json(msg)
        except Exception:
            sockets.discard(ws)

    def _send(self, sockets, msg):
        # safe to call from sync route handlers (threadpool) or async code
        for ws in list(sockets):
            loop = self.sock_loop.get(ws) or self.loop
            if not loop or loop.is_closed():
                sockets.discard(ws); continue
            coro = self._send_one(sockets, ws, msg)
            try:
                if asyncio.get_running_loop() is loop:
                    loop.create_task(coro); continue
            except RuntimeError:
                pass
            asyncio.run_coroutine_threadsafe(coro, loop)

    def to_user(self, uid: int, msg: dict):
        self._send(self.users.get(uid, set()), msg)

    def to_room(self, nid: int, msg: dict):
        self._send(self.rooms.get(nid, set()), msg)

    def to_all(self, msg: dict):
        allws = set().union(*self.users.values()) if self.users else set()
        self._send(allws, msg)


hub = Hub()
