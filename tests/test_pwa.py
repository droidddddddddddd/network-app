import json, re
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parent.parent
c = TestClient(app)


def test_manifest_served():
    r = c.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    m = r.json()
    assert m["name"] == m["short_name"] == "NETWORK"
    assert m["start_url"] == "/" and m["scope"] == "/" and m["display"] == "standalone"
    assert "Build your Network. Build your Net Worth." in m["description"]
    sizes = {(i["sizes"], i.get("purpose", "any")) for i in m["icons"]}
    assert ("192x192", "any") in sizes and ("512x512", "any") in sizes and ("512x512", "maskable") in sizes
    for i in m["icons"]:
        ir = c.get(i["src"])
        assert ir.status_code == 200 and ir.headers["content-type"] == "image/png"


def test_icons_exist_and_sizes():
    import struct
    for name, size in [("icon-192.png", 192), ("icon-512.png", 512), ("icon-maskable-512.png", 512), ("apple-touch-icon.png", 180)]:
        b = (ROOT / "static" / "icons" / name).read_bytes()
        assert b[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", b[16:24]) == (size, size)
    assert c.get("/favicon.ico").status_code == 200


def test_sw_headers_and_no_api_cache():
    r = c.get("/sw.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/javascript")
    assert "no-cache" in r.headers["cache-control"] and "no-store" in r.headers["cache-control"]
    assert r.headers["service-worker-allowed"] == "/"
    src = r.text
    assert "__BUILD__" not in src and re.search(r"network-shell-", src)
    assert "p.startsWith('/api/')" in src and "if (NEVER(url.pathname)) return;" in src
    assert "/api" not in "".join(re.findall(r"const SHELL = \[(.*?)\];", src, re.S))
    assert "skipWaiting" in src and "clients.claim" in src


def test_index_pwa_tags_and_csp():
    r = c.get("/")
    h = r.text
    for s in ['rel="manifest"', 'name="theme-color"', 'apple-mobile-web-app-capable', 'apple-mobile-web-app-status-bar-style',
              'apple-mobile-web-app-title', 'rel="apple-touch-icon"', 'viewport-fit=cover', '/static/pwa.js']:
        assert s in h
    csp = r.headers["content-security-policy"]
    assert "worker-src 'self'" in csp and "manifest-src 'self'" in csp and "script-src 'self';" in csp


def test_api_not_affected():
    r = c.get("/api/meta")
    assert r.status_code in (200, 401, 404)
