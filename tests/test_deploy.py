import os, subprocess, sys

def test_seed_refuses_in_production(tmp_path):
    env = {**os.environ, "ENV": "production", "SEED_DEMO": "", "JWT_SECRET": "x" * 48, "DATABASE_URL": "postgresql://localhost/network_unused"}
    r = subprocess.run([sys.executable, "-m", "app.seed"], env=env, capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
    assert r.returncode != 0 and "Refusing to load demo data" in (r.stderr + r.stdout)

def test_render_yaml_shape():
    import yaml  # noqa: dev-only (tests)
    y = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "..", "render.yaml")))
    svc = y["services"][0]; env = {e["key"]: e for e in svc["envVars"]}
    assert svc["plan"] == "free" and y["databases"][0]["plan"] == "free" and svc["numInstances"] == 1
    assert svc["healthCheckPath"] == "/health" and env["JWT_SECRET"]["generateValue"] is True
    assert "fromDatabase" in env["DATABASE_URL"] and env["PYTHON_VERSION"]["value"].count(".") == 2
    for k in ("ADMIN_USERNAMES", "HELIUS_API_KEY", "S3_SECRET_ACCESS_KEY"):
        assert env[k]["sync"] is False and "value" not in env[k]

def test_no_api_schema_or_docs_in_production(tmp_path):
    code = ("from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app);"
            "assert c.get('/openapi.json').status_code==404 and c.get('/api/docs').status_code==404; print('ok')")
    env = {**os.environ, "ENV": "production", "JWT_SECRET": "x" * 48, "DATABASE_URL": "postgresql://localhost/network_unused", "DISABLE_TRACKER": "1"}
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-500:]


def test_production_requires_postgres(tmp_path):
    for url in ("", f"sqlite:///{tmp_path}/bad.db"):
        env = {**os.environ, "ENV": "production", "DATABASE_URL": url}
        r = subprocess.run([sys.executable, "-c", "import app.db"], env=env, capture_output=True, text=True)
        assert r.returncode != 0 and "Production requires DATABASE_URL" in r.stderr
