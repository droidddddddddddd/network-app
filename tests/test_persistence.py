"""Data persists across a real server restart (separate uvicorn processes on the same DB)."""
import os, sys, time, socket, subprocess, tempfile
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parent.parent


def _port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _start(env, port):
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=ROOT, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health").status_code == 200: return p
        except httpx.HTTPError: pass
        time.sleep(0.25)
    p.kill(); raise RuntimeError("server did not start")


def test_persists_after_restart():
    d = tempfile.mkdtemp()
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{d}/p.db", "DISABLE_TRACKER": "1", "UPLOAD_DIR": f"{d}/up"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
    port = _port(); H = {"x-csrf": "1"}
    p = _start(env, port)
    try:
        c = httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=H)
        assert c.post("/api/auth/register", json={"username": "persist1", "email": "p@ex.com", "password": "password123"}).status_code == 200
        assert c.post("/api/networks", json={"name": "Persistent Net", "type": "Personal"}).status_code == 200
        assert c.post("/api/posts", json={"body": "survives restarts"}).status_code == 200
    finally:
        p.terminate(); p.wait()
    p = _start(env, port)
    try:
        c = httpx.Client(base_url=f"http://127.0.0.1:{port}", headers=H)
        assert c.post("/api/auth/login", json={"login": "persist1", "password": "password123"}).status_code == 200
        assert "survives restarts" in c.get("/api/users/persist1/posts").text
        assert any(n["name"] == "Persistent Net" for n in c.get("/api/networks?mine=1").json())
    finally:
        p.terminate(); p.wait()
