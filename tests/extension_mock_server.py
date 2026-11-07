"""LOCAL TEST RUNNER ONLY. Mock X provider transport; never imported by app startup."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from urllib.parse import urlencode
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
import uvicorn
from app.main import app
from app import oauth
from app.extension_auth import challenge_for

codes = {}
base = os.environ["PUBLIC_BASE_URL"]
oauth.PROVIDERS["x"]["authorize"] = base + "/__mock_x/authorize"


@app.get("/__mock_x/authorize")
def authorize(request: Request):
    q = dict(request.query_params)
    if q.get("client_id") != "local-x-client" or q.get("code_challenge_method") != "S256":
        raise HTTPException(400, "Mock PKCE authorization invalid")
    import secrets
    code = secrets.token_urlsafe(24)
    codes[code] = q
    return RedirectResponse(q["redirect_uri"] + "?" + urlencode({"code": code, "state": q["state"]}), status_code=302)


def exchange(provider, code, verifier, redirect):
    q = codes.pop(code, None)
    if not q or q["redirect_uri"] != redirect or q["code_challenge"] != challenge_for(verifier):
        raise ValueError("Mock provider rejected PKCE")
    return {"access_token": "local-mock-provider-token-not-stored"}


def info(provider, token):
    return {"data": {"id": "ext2-browser-user", "username": "network_member", "name": "Extension member"}}


oauth.exchange_code = exchange
oauth.fetch_userinfo = info
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["PORT"]), access_log=True)
