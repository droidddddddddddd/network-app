import os, sys, tempfile, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp()
DB = os.path.join(TMP, "test.db")
PG = os.getenv("TEST_DATABASE_URL", "")  # e.g. postgresql://net@127.0.0.1:55432/network_test
if PG:
    import psycopg
    with psycopg.connect(PG, autocommit=True) as _c:
        _c.execute("DROP SCHEMA public CASCADE"); _c.execute("CREATE SCHEMA public")
os.environ["DATABASE_URL"] = PG or f"sqlite:///{DB}"
os.environ["DISABLE_TRACKER"] = "1"
os.environ["RANKINGS_TTL"] = "0"
os.environ["ADMIN_USERNAMES"] = "padmin"
os.environ["ENABLE_WALLET_FEATURES"] = "1"  # opt in only for legacy wallet-feature tests
os.environ["UPLOAD_DIR"] = os.path.join(TMP, "uploads")
# migration check: the schema used by every test is built by Alembic, not create_all
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True, env=os.environ.copy())
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import security  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_limits():
    security.reset_rate_limits()
    yield


class C:
    """A logged-in browser: own cookie jar, CSRF header set."""
    def __init__(self, username=None):
        self.c = TestClient(app)
        self.c.headers["x-csrf"] = "1"
        self.username = username
        self.id = None

    def __getattr__(self, k):
        return getattr(self.c, k)

    def ok(self, method, url, status=200, **kw):
        r = self.c.request(method, url, **kw)
        assert r.status_code == status, f"{method} {url} -> {r.status_code} {r.text}"
        return r.json() if r.content and r.headers.get("content-type", "").startswith("application/json") else r


_n = [0]


@pytest.fixture
def mk():
    def make(name=None):
        _n[0] += 1
        name = name or f"user{_n[0]}"
        c = C(name)
        # These are pre-existing legacy accounts, not public password signups.
        from app.db import SessionLocal
        from app.models import User
        with SessionLocal() as db:
            db.add(User(username=name, email=f"{name}@ex.com", password_hash=security.hash_pw("password123"), display_name=name.title()))
            db.commit()
        u = c.ok("POST", "/api/auth/login", json={"login": name, "password": "password123"})
        c.id = u["id"]
        security.reset_rate_limits()
        return c
    return make


@pytest.fixture
def anon():
    c = C(); return c
