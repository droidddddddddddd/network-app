"""WebSocket hub.

Default (REALTIME_BACKEND unset/"local"): in-process, single web instance only.
REALTIME_BACKEND=postgres: every event is published with Postgres NOTIFY and each instance LISTENs and delivers to
its own sockets, so chat, DMs and notifications work across several instances with no extra service."""
import asyncio
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict

log = logging.getLogger("network.realtime")
CHANNEL = "network_rt"
MAX_PAYLOAD = 7900  # Postgres NOTIFY limit is 8000 bytes


def backend() -> str:
    return (os.getenv("REALTIME_BACKEND") or "local").strip().lower()


class Hub:
    def __init__(self):
        self.users: dict[int, set] = defaultdict(set)
        self.rooms: dict[int, set] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.sock_loop: dict = {}
        self.instance = uuid.uuid4().hex[:12]
        self.dsn: str | None = None
        self._pub = None
        self._pub_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.listening = threading.Event()

    # ---- socket bookkeeping
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

    def _deliver(self, kind: str, target, msg: dict):
        if kind == "user":
            self._send(self.users.get(int(target), set()), msg)
        elif kind == "room":
            self._send(self.rooms.get(int(target), set()), msg)
        else:
            self._send(set().union(*self.users.values()) if self.users else set(), msg)

    # ---- public API (unchanged for callers)
    def to_user(self, uid: int, msg: dict): self._publish("user", uid, msg)
    def to_room(self, nid: int, msg: dict): self._publish("room", nid, msg)
    def to_all(self, msg: dict): self._publish("all", None, msg)

    def _publish(self, kind, target, msg):
        if not self._thread:
            return self._deliver(kind, target, msg)
        payload = json.dumps({"k": kind, "t": target, "m": msg, "o": self.instance}, separators=(",", ":"), default=str)
        if len(payload.encode()) > MAX_PAYLOAD:
            log.warning("realtime payload too large for NOTIFY; delivered on this instance only")
            return self._deliver(kind, target, msg)
        try:
            with self._pub_lock:
                if self._pub is None or self._pub.closed:
                    import psycopg
                    self._pub = psycopg.connect(self.dsn, autocommit=True)
                self._pub.execute("SELECT pg_notify(%s, %s)", (CHANNEL, payload))
        except Exception as e:  # never break a request because realtime is down; deliver locally instead
            log.warning("NOTIFY failed (%s); delivering locally", type(e).__name__)
            self._pub = None
            self._deliver(kind, target, msg)

    # ---- Postgres LISTEN loop
    def start(self, database_url: str):
        if backend() != "postgres":
            return False
        if not database_url.startswith("postgresql"):
            raise RuntimeError("REALTIME_BACKEND=postgres needs a PostgreSQL DATABASE_URL")
        self.dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
        self._thread = threading.Thread(target=self._listen, name="realtime-listen", daemon=True)
        self._thread.start()
        self.listening.wait(10)
        return True

    def stop(self):
        self._stop.set()

    def _listen(self):
        import psycopg
        while not self._stop.is_set():
            try:
                with psycopg.connect(self.dsn, autocommit=True) as conn:
                    conn.execute(f"LISTEN {CHANNEL}")
                    self.listening.set()
                    while not self._stop.is_set():
                        for n in conn.notifies(timeout=1.0):
                            try:
                                d = json.loads(n.payload)
                                self._deliver(d["k"], d["t"], d["m"])
                            except Exception:
                                log.exception("bad realtime payload")
            except Exception as e:
                log.warning("LISTEN connection lost (%s); reconnecting", type(e).__name__)
                time.sleep(2)


hub = Hub()
