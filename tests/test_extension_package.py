"""The Store archive is reproducible, contains runtime only, and preserves branding."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def test_store_archive_and_policy(tmp_path, anon):
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    for out in (a, b):
        subprocess.run([sys.executable, "scripts/build_extension.py", "--output", str(out)], cwd=ROOT, check=True, capture_output=True)
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as z:
        names = z.namelist()
        assert "manifest.json" in names and "privacy.html" in names
        assert not any(part in name.lower() for name in names for part in ("test", "mock", "probe", ".env", "store_listing", "node_modules"))
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["manifest_version"] == 3 and manifest["permissions"] == ["sidePanel", "storage", "identity"]
        for size in (16, 48, 128):
            png = z.read(f"icons/icon-{size}.png")
            assert struct.unpack(">II", png[16:24]) == (size, size)
        assert z.read("logo.svg") == (ROOT / "static/img/logo.svg").read_bytes()
        assert b"TRUSTED_CONTEXTS" in z.read("background.js")
    policy = anon.get("/extension-privacy")
    assert policy.status_code == 200 and "Privacy Policy" in policy.text
    assert "not an httpOnly cookie" in policy.text and "not the full tweet text" in policy.text
