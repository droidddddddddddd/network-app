"""Two real app processes against Postgres with REALTIME_BACKEND=postgres: a DM/notification sent through instance B
must reach a WebSocket connected to instance A. Runs only when TEST_DATABASE_URL points at Postgres."""
import json, os, socket, subprocess, sys, time
import httpx, pytest

PG = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not PG.startswith("postgres"), reason="needs TEST_DATABASE_URL=postgresql://...")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="module")
def two_instances():
    import psycopg
    base, _, _ = PG.rpartition("/")
    dbname = "network_rt_test"
    with psycopg.connect(base + "/postgres", autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {dbname} WITH (FORCE)"); c.execute(f"CREATE DATABASE {dbname}")
    url = f"{base}/{dbname}"
    env = {**os.environ, "DATABASE_URL": url, "REALTIME_BACKEND": "postgres", "DISABLE_TRACKER": "1", "ENV": "development"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)
    procs, ports = [], [free_port(), free_port()]
    for p in ports:
        procs.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(p)], cwd=ROOT, env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for p in ports:
        for _ in range(60):
            try:
                if httpx.get(f"http://127.0.0.1:{p}/health").json()["realtime"] == "postgres": break
            except Exception: pass
            time.sleep(0.25)
        else: raise RuntimeError("instance did not start")
    yield ports
    for pr in procs: pr.terminate(); pr.wait(10)


def signup(port, name):
    c = httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"x-csrf": "1"})
    r = c.post("/api/auth/register", json={"username": name, "email": f"{name}@example.invalid", "password": "Sup3rSecret!pw", "display_name": name})
    assert r.status_code == 200, r.text
    return c


def test_dm_crosses_instances(two_instances):
    from websockets.sync.client import connect
    a_port, b_port = two_instances
    alice, bob = signup(a_port, "rt_alice"), signup(b_port, "rt_bob")
    assert alice.post("/api/users/rt_bob/follow").status_code == 200  # lets bob DM alice
    ck = "; ".join(f"{k}={v}" for k, v in alice.cookies.items())
    with connect(f"ws://127.0.0.1:{a_port}/ws", additional_headers={"Cookie": ck}) as ws:
        time.sleep(0.3)
        assert bob.post("/api/users/rt_alice/follow").status_code == 200  # notification to alice, via instance B
        r = bob.post("/api/messages/rt_alice", json={"body": "hello across instances"})
        assert r.status_code == 200, r.text
        got = []
        deadline = time.time() + 5
        while time.time() < deadline and not (any(m.get("type") == "dm" for m in got) and any(m.get("type") == "notification" for m in got)):
            try: got.append(json.loads(ws.recv(timeout=1)))
            except TimeoutError: pass
        dm = [m for m in got if m.get("type") == "dm"]
        assert dm and dm[0]["message"]["body"] == "hello across instances" and dm[0]["from"] == "rt_bob"
        assert any(m.get("type") == "notification" and "rt_bob" in m["text"] for m in got)
