"""Isolated real unpacked-extension smoke check; not collected by pytest.
Run: python tests/extension_browser_check.py --shots /workspace/network-new/shots
Requires Playwright + bundled full Chromium. Never reads deployment credentials.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def run(shots):
    shots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="network-extension-") as tmp:
        work = Path(tmp)
        ext = work / "extension"
        shutil.copytree(ROOT / "extension", ext)
        base = f"http://127.0.0.1:{port()}"
        (ext / "config.js").write_text(f"const NETWORK_BASE_URL = {json.dumps(base)};\n")
        manifest = json.loads((ext / "manifest.json").read_text())
        manifest["host_permissions"] = [base + "/*"]
        manifest["content_security_policy"]["extension_pages"] = manifest["content_security_policy"]["extension_pages"].replace("https://network-app-65f6.onrender.com", base)
        (ext / "manifest.json").write_text(json.dumps(manifest))
        # Deliberately construct a small env instead of inheriting server/provider secrets.
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "VIRTUAL_ENV")}
        env.update(DATABASE_URL=f"sqlite:///{work}/test.db", DISABLE_TRACKER="1", ENABLE_WALLET_FEATURES="0",
                   ENV="development", UPLOAD_DIR=str(work / "uploads"), JWT_SECRET="local-browser-test-only-" + "x" * 32)
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)
        seed = """
from app.db import SessionLocal
from app.models import User, Network, Membership, Post
with SessionLocal() as db:
    u = User(username='extension_demo', email='local@example.invalid', password_hash='', display_name='Demo', is_demo=True)
    db.add(u); db.flush()
    n = Network(slug='private-browser-test', name='Private test', type='Personal', founder_id=u.id, is_private=True)
    db.add(n); db.flush()
    db.add_all([Post(author_id=u.id, body='NETWORK extension local API smoke test', is_demo=True),
                Post(author_id=u.id, body='<img src=x onerror=window.XSS=true> rendered as plain text', is_demo=True),
                Post(author_id=u.id, body='PRIVATE_BROWSER_SECRET', network_id=n.id),
                Post(author_id=u.id, body='HIDDEN_BROWSER_SECRET', hidden=True),
                Post(author_id=u.id, body='REMOVED_BROWSER_SECRET', removed=True)])
    db.commit()
"""
        subprocess.run([sys.executable, "-c", seed], cwd=ROOT, env=env, check=True, capture_output=True)
        async with async_playwright() as pw:
            ctx = await pw.chromium.launch_persistent_context(str(work / "profile"), channel="chromium", headless=True,
                args=[f"--disable-extensions-except={ext}", f"--load-extension={ext}", "--no-sandbox"],
                viewport={"width": 420, "height": 900})
            try:
                worker = ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event("serviceworker")
                eid = worker.url.split("/")[2]
                origin = "chrome-extension://" + eid
                env["EXTENSION_ORIGINS"] = origin
                with (work / "server.log").open("w") as log:
                    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", base.rsplit(":", 1)[1], "--no-access-log"], cwd=ROOT, env=env, stdout=log, stderr=log)
                    try:
                        for _ in range(80):
                            if server.poll() is not None: raise RuntimeError("Local test server exited")
                            try:
                                if httpx.get(base + "/health").status_code == 200: break
                            except httpx.HTTPError: pass
                            await asyncio.sleep(.15)
                        else: raise RuntimeError("Local test server startup timed out")
                        h = httpx.get(base + "/", headers={"Origin": origin})
                        assert h.headers["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in h.headers["content-security-policy"]
                        api = httpx.get(base + "/api/extension/feed", headers={"Origin": origin})
                        assert api.headers["access-control-allow-origin"] == origin
                        assert "access-control-allow-credentials" not in api.headers
                        assert "access-control-allow-origin" not in httpx.get(base + "/api/extension/feed", headers={"Origin": "chrome-extension://" + "a" * 32}).headers
                        pg = await ctx.new_page()
                        errors = []
                        pg.on("pageerror", lambda error: errors.append(str(error)))
                        async with pg.expect_response(lambda r: r.url == base + "/api/extension/feed" and r.status == 200):
                            await pg.goto(origin + "/sidepanel.html")
                        await pg.locator("#feed article").first.wait_for()
                        assert await pg.locator("#feed article").count() == 2
                        text = await pg.locator("body").inner_text()
                        assert 'NETWORK extension local API smoke test' in text and 'DEMO' in text
                        assert not any(s in text for s in ('PRIVATE_BROWSER_SECRET', 'HIDDEN_BROWSER_SECRET', 'REMOVED_BROWSER_SECRET'))
                        assert await pg.locator("iframe").count() == 0
                        assert await pg.locator("#feed img").count() == 0 and not await pg.evaluate("!!window.XSS")
                        assert await pg.locator("#workspace").get_attribute("href") == base + "/"
                        assert await pg.locator("#workspace").get_attribute("target") == "_blank"
                        await pg.screenshot(path=str(shots / "ext-feed.png"), full_page=True)
                        await pg.locator("#panel").click()
                        await pg.get_by_role("button", name="Side panel opened", exact=True).wait_for()
                        # Real link opens top-level NETWORK; the extension never receives a session.
                        async with ctx.expect_page() as opened:
                            await pg.locator("#workspace").click()
                        tab = await opened.value
                        await tab.wait_for_load_state()
                        assert tab.url.startswith(base + "/")
                        await tab.close()
                        # Fixture-only empty response: keep this distinct from the successful real API request.
                        await pg.route("**/api/extension/feed", lambda route: route.fulfill(status=200, content_type="application/json", body='{"scope":"public","posts":[],"read_only":true}'))
                        await pg.locator("#refresh").click()
                        await pg.get_by_text("No public updates yet.", exact=False).wait_for()
                        await pg.screenshot(path=str(shots / "ext-empty.png"), full_page=True)
                        await pg.unroute("**/api/extension/feed")
                        await ctx.set_offline(True)
                        await pg.locator("#refresh").click()
                        await pg.locator("#status.error").wait_for()
                        await pg.screenshot(path=str(shots / "ext-offline.png"), full_page=True)
                        await ctx.set_offline(False)
                        await pg.locator("#refresh").click()
                        await pg.locator("#feed article").first.wait_for()
                        assert not errors, errors
                        # Mock only the X document, never sign in or scrape real X.
                        await ctx.route("https://x.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body='<!doctype html><title>X launcher test fixture</title><body style="background:#101619;color:white;font:20px system-ui"><h1>X document fixture</h1><p>No real X content or login is used.</p></body>'))
                        x = await ctx.new_page()
                        await x.goto("https://x.com/home")
                        launcher = x.locator("#network-overlay-launcher")
                        await launcher.wait_for()
                        await launcher.click()
                        await x.wait_for_function("document.getElementById('network-overlay-launcher').dataset.panelState")
                        launcher_state = await launcher.get_attribute("data-panel-state")
                        assert launcher_state == "opened", "Native sidePanel.open failed: " + str(launcher_state)
                        await x.screenshot(path=str(shots / "ext-x-launcher.png"), full_page=True)
                        print(json.dumps({"result": "passed", "extension_id": eid, "chromium": ctx.browser.version,
                            "verified": ["real unpacked MV3 worker", "extension-owned popup/panel document renders", "popup Open side panel button resolves native sidePanel.open", "local API fetched and rendered two public DEMO posts", "private/hidden/removed excluded", "untrusted markup stays text", "top-level workspace link opens", "exact-ID credential-free CORS", "main anti-framing retained", "empty fixture", "offline error and retry", "X launcher injected/clicked in mocked X document; native sidePanel.open resolved"],
                            "page_errors": errors, "screenshots": [str(p) for p in sorted(shots.glob("ext-*.png"))],
                            "unverified": ["native toolbar/side-panel browser chrome", "real X page", "real X OAuth", "store installation"]}, indent=2))
                    finally:
                        server.terminate(); server.wait(timeout=10)
            finally:
                await ctx.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", type=Path, default=ROOT / "screenshots" / "extension")
    asyncio.run(run(parser.parse_args().shots.resolve()))
