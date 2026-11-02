import os, sys, tempfile, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp()
DB = os.path.join(TMP, "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{DB}"
os.environ["DISABLE_TRACKER"] = "1"
os.environ["UPLOAD_DIR"] = os.path.join(TMP, "uploads")
# migration check: the schema used by every test is built by Alembic, not create_all
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, check=True, env=os.environ.copy())
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import security  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_limits():
    security._hits.clear()
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
        u = c.ok("POST", "/api/auth/register", json={"username": name, "email": f"{name}@ex.com", "password": "password123", "display_name": name.title()})
        c.id = u["id"]
        security._hits.clear()
        return c
    return make


@pytest.fixture
def anon():
    c = C(); return c
