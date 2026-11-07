"""Exact-ID, cookie-free CORS for scoped companion APIs, never site framing."""
import os
import re
from starlette.middleware.cors import CORSMiddleware


def extension_origins():
    origins = [v.strip() for v in os.getenv("EXTENSION_ORIGINS", "").split(",") if v.strip()]
    if any(not re.fullmatch(r"chrome-extension://[a-p]{32}", v) for v in origins):
        raise ValueError("EXTENSION_ORIGINS must contain exact chrome-extension:// IDs (32 letters a-p), not wildcards or web origins")
    return origins


class ExtensionCORSMiddleware:
    def __init__(self, app):
        self.app = app
        self.cors = CORSMiddleware(app, allow_origins=extension_origins(),
                                   allow_methods=["GET", "POST"], allow_headers=["authorization", "content-type", "x-csrf", "x-network-extension"], allow_credentials=False)

    async def __call__(self, scope, receive, send):
        target = self.cors if scope["type"] == "http" and scope["path"].startswith("/api/extension/") else self.app
        await target(scope, receive, send)


class WebCORSMiddleware:
    """Do not let credentialed web CORS broaden the companion's separate surface."""
    def __init__(self, app, **kwargs):
        self.app = app
        self.cors = CORSMiddleware(app, **kwargs)

    async def __call__(self, scope, receive, send):
        target = self.app if scope["type"] == "http" and scope["path"].startswith("/api/extension/") else self.cors
        await target(scope, receive, send)
