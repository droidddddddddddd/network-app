"""Release invariant check; supplements tests, not a complete security audit."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
errors = []


def check(ok, label):
    if not ok: errors.append(label)


main = (ROOT / "app/main.py").read_text()
security = (ROOT / "app/security.py").read_text()
db = (ROOT / "app/db.py").read_text()
js = (ROOT / "extension/sidepanel.js").read_text()
worker = (ROOT / "extension/background.js").read_text()
manifest = json.loads((ROOT / "extension/manifest.json").read_text())
render = yaml.safe_load((ROOT / "render.yaml").read_text())
service = render["services"][0]
env = {e["key"]: e for e in service["envVars"]}
check(not service.get("rootDir"), "Render must use repository root")
check("fromDatabase" in env["DATABASE_URL"], "Render requires managed PostgreSQL")
check(str(env["ENABLE_WALLET_FEATURES"].get("value")) == "0", "wallet features must remain off")
check("Production requires DATABASE_URL" in db, "production DB fail-closed guard")
check('if PROD and SECRET.startswith("dev-only")' in security, "production JWT guard")
check('resp.headers["X-Frame-Options"] = "DENY"' in main and "frame-ancestors 'none'" in main, "main anti-framing preserved")
check("<iframe" not in (ROOT / "extension/sidepanel.html").read_text(), "no extension iframe")
check("credentials: 'omit'" in worker and 'textContent' in js and 'innerHTML' not in js, "public credential-free text rendering")
check(manifest["permissions"] == ["sidePanel", "storage", "identity"], "least-privilege extension permissions")
check("TRUSTED_CONTEXTS" in worker and "chrome.storage.session.set({ auth })" in worker and "chrome.storage.local.set({ auth" not in worker, "trusted memory-only auth storage")
check("frame-src 'none'" in manifest["content_security_policy"]["extension_pages"], "extension CSP frames disabled")
check((ROOT / "extension/logo.svg").read_bytes() == (ROOT / "static/img/logo.svg").read_bytes(), "official node-N logo reused")
for folder in ("app", "static", "extension"):
    for path in (ROOT / folder).rglob("*"):
        if path.suffix not in (".py", ".js", ".html", ".json"): continue
        text = path.read_text()
        if path.suffix == ".py": ast.parse(text, filename=str(path))
        if path.suffix == ".js":
            result = subprocess.run(["node", "--check", str(path)], capture_output=True)
            check(result.returncode == 0, "JavaScript syntax: " + str(path.relative_to(ROOT)))
        # Report locations only, never values of suspected secrets.
        for n, line in enumerate(text.splitlines(), 1):
            check(not re.search(r"helius.*[?&]api-key=[A-Za-z0-9_-]{20,}", line, re.I),
                  f"possible embedded RPC key at {path.relative_to(ROOT)}:{n}")
check("not verified executed trades" in (ROOT / "README.md").read_text(), "verification scope documented")
if errors:
    print("RULES CHECK FAILED\n" + "\n".join(errors))
    sys.exit(1)
print("RULES CHECK PASSED: root/Postgres, wallet-off, JWT guard, anti-framing, native extension, least privilege, node-N, syntax and RPC-secret patterns")
