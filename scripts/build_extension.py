"""Build a credential-free Chrome Web Store upload archive; never publishes it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "extension"
RUNTIME = ["manifest.json", "config.js", "background.js", "content.js", "sidepanel.html", "sidepanel.js", "sidepanel.css", "privacy.html", "logo.svg"]
RUNTIME += ["icons/" + name for name in ("favicon-32.png", "icon-16.png", "icon-48.png", "icon-128.png", "icon-192.png")]


def build(output):
    manifest = json.loads((EXT / "manifest.json").read_text())
    if manifest["permissions"] != ["sidePanel", "storage", "identity"]: raise ValueError("Unexpected permissions")
    if len(manifest["description"]) > 132: raise ValueError("Store short description exceeds 132 characters")
    if manifest["host_permissions"] != ["https://network-app-65f6.onrender.com/*"]: raise ValueError("Build must target the production public host, not test servers")
    if (EXT / "logo.svg").read_bytes() != (ROOT / "static/img/logo.svg").read_bytes(): raise ValueError("Official logo changed")
    for name in RUNTIME:
        path = EXT / name
        if not path.is_file(): raise ValueError("Missing runtime asset: " + name)
        if path.suffix in (".js", ".json", ".html"):
            text = path.read_text()
            if any(value in text for value in ("localhost", "127.0.0.1", "__mock_x", "X_CLIENT_SECRET", "HELIUS_API_KEY", "JWT_SECRET")):
                raise ValueError("Forbidden development/secret configuration in " + name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(RUNTIME):
            info = zipfile.ZipInfo(name, (2026, 11, 7, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (EXT / name).read_bytes())
    return {"archive": str(output), "version": manifest["version"], "files": len(RUNTIME), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, default=ROOT / "dist/network-x-companion.zip")
    print(json.dumps(build(p.parse_args().output.resolve()), indent=2))
