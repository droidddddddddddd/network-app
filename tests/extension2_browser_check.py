"""Real unpacked MV3 auth + actions + X context against an isolated local server/mock X.
No production secrets or logged-in browser profiles. Optional real public X read only.
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
import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


async def run(shots, real_x=True):
    shots.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="network-ext2-") as tmp:
        work = Path(tmp); ext = work / "extension"; shutil.copytree(ROOT / "extension", ext)
        base = f"http://127.0.0.1:{port()}"
        (ext / "config.js").write_text(f"const NETWORK_BASE_URL = {json.dumps(base)};\n")
        manifest = json.loads((ext / "manifest.json").read_text())
        manifest["host_permissions"] = [base + "/*"]
        manifest["content_security_policy"]["extension_pages"] = manifest["content_security_policy"]["extension_pages"].replace("https://network-app-65f6.onrender.com", base)
        # Test-only isolated-world probe: content scripts must not access token storage or member APIs.
        (ext / "probe.js").write_text("""(async()=>{let blocked=true;try{if(chrome.storage.session){await chrome.storage.session.get('auth');blocked=false;}}catch(_){}const result=await chrome.runtime.sendMessage({type:'AUTH_STATUS'});document.documentElement.dataset.networkProbe=(blocked&&!result?.ok)?'blocked':'FAILED';})();""")
        manifest["content_scripts"].append({"matches": ["https://x.com/network-fixture"], "js": ["probe.js"], "run_at": "document_idle"})
        (ext / "manifest.json").write_text(json.dumps(manifest))
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "VIRTUAL_ENV")}
        env.update(DATABASE_URL=f"sqlite:///{work}/test.db", DISABLE_TRACKER="1", ENABLE_WALLET_FEATURES="0", ENV="development",
                   UPLOAD_DIR=str(work / "uploads"), JWT_SECRET="local-extension-test-only-" + "x" * 32,
                   PUBLIC_BASE_URL=base, PORT=base.rsplit(":", 1)[1], X_CLIENT_ID="local-x-client", X_CLIENT_SECRET="local-mock-secret")
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)
        seed = """
from app.db import SessionLocal
from app.models import User, Network, Membership, Post, LinkedAccount, Call
from app.services import utcnow
from datetime import timedelta
with SessionLocal() as db:
    u=User(username='network_member',email='local@example.invalid',password_hash='',display_name='Network member',created_at=utcnow()-timedelta(days=3),is_demo=True)
    other=User(username='other_member',email='other@example.invalid',password_hash='',display_name='Other')
    db.add_all([u,other]);db.flush()
    db.add(LinkedAccount(user_id=u.id,provider='x',subject='ext2-browser-user',handle='network_member'))
    own=Network(slug='member-private',name='Member private network',type='Trading',founder_id=u.id,is_private=True)
    forbidden=Network(slug='other-private',name='Other private network',type='Trading',founder_id=other.id,is_private=True)
    db.add_all([own,forbidden]);db.flush()
    db.add(Membership(network_id=own.id,user_id=u.id,role='founder',status='active'))
    public=Post(author_id=u.id,body='Public NETWORK research $CTX',is_demo=True)
    private=Post(author_id=u.id,network_id=own.id,body='MEMBER_PRIVATE_ALLOWED',is_demo=True)
    blocked=Post(author_id=other.id,network_id=forbidden.id,body='FORBIDDEN_PRIVATE_SECRET')
    db.add_all([public,private,blocked,Post(author_id=u.id,body='<img src=x onerror=window.EXT2_XSS=true>',is_demo=True)]);db.flush()
    db.add(Call(user_id=u.id,post_id=public.id,symbol='CTX',token_address='1'*32,is_demo=True))
    db.add(Call(user_id=u.id,post_id=private.id,network_id=own.id,symbol='CTX',token_address='1'*32,is_demo=True))
    db.commit()
"""
        subprocess.run([sys.executable, "-c", seed], cwd=ROOT, env=env, check=True, capture_output=True)
        async with async_playwright() as pw:
            ctx = await pw.chromium.launch_persistent_context(str(work / "profile"), channel="chromium", headless=True,
                args=[f"--disable-extensions-except={ext}", f"--load-extension={ext}", "--no-sandbox"], viewport={"width": 520, "height": 1000})
            try:
                worker = ctx.service_workers[0] if ctx.service_workers else await ctx.wait_for_event("serviceworker")
                eid = worker.url.split("/")[2]; origin = "chrome-extension://" + eid
                env["EXTENSION_ORIGINS"] = origin
                with (work / "server.log").open("w") as log:
                    server = subprocess.Popen([sys.executable, "tests/extension_mock_server.py"], cwd=ROOT, env=env, stdout=log, stderr=log)
                    try:
                        for _ in range(80):
                            if server.poll() is not None: raise RuntimeError("Local OAuth mock server exited")
                            try:
                                if httpx.get(base + "/health").status_code == 200: break
                            except httpx.HTTPError: pass
                            await asyncio.sleep(.15)
                        else: raise RuntimeError("Local server startup timed out")
                        pg = await ctx.new_page(); errors=[]
                        pg.on('pageerror', lambda error: errors.append(str(error)))
                        await pg.goto(origin + '/sidepanel.html')
                        await pg.get_by_text('Public updates · sign in to participate', exact=True).wait_for()
                        assert 'MEMBER_PRIVATE_ALLOWED' not in await pg.locator('body').inner_text()
                        assert await pg.locator('#feed img').count()==0
                        await pg.get_by_text('<img src=x onerror=window.EXT2_XSS=true>',exact=True).wait_for()
                        await pg.screenshot(path=str(shots / 'ext2-public.png'), full_page=True)
                        await pg.locator('#panel').click()
                        await pg.get_by_role('button',name='Side panel opened',exact=True).wait_for()
                        peer=await ctx.new_page(); await peer.goto(origin+'/sidepanel.html')
                        await peer.get_by_text('Public updates · sign in to participate',exact=True).wait_for()
                        # Real Chrome identity API and redirect interception; only provider transport is mocked locally.
                        await pg.locator('#signin').click()
                        await pg.locator("#member:not([hidden]), #status.error").first.wait_for(state="visible", timeout=45000)
                        if await pg.locator('#member').is_hidden():
                            await pg.screenshot(path=str(shots/'ext2-auth-debug.png'),full_page=True)
                            raise AssertionError('Sign-in UI: ' + await pg.locator('#status').inner_text())
                        await pg.get_by_text('Signed in as @network_member', exact=True).wait_for()
                        await pg.get_by_text('Your permission-filtered feed', exact=True).wait_for()
                        await peer.get_by_text('Signed in as @network_member',exact=True).wait_for()
                        await peer.get_by_text('MEMBER_PRIVATE_ALLOWED',exact=True).wait_for()
                        text=await pg.locator('body').inner_text()
                        assert 'MEMBER_PRIVATE_ALLOWED' in text and 'FORBIDDEN_PRIVATE_SECRET' not in text
                        assert await worker.evaluate("(async()=>Boolean((await chrome.storage.session.get('auth')).auth?.token))()")
                        # Token used only inside trusted worker; keep its value out of test output and screenshots.
                        await worker.evaluate("(async()=>{globalThis.savedTestToken=(await chrome.storage.session.get('auth')).auth.token})()")
                        await pg.locator('#context').check()
                        await pg.locator('#post-body').fill('Published from the authenticated companion')
                        await pg.locator('#post-form button').click()
                        await pg.get_by_text('Post published.',exact=True).wait_for()
                        post=pg.locator('article').filter(has=pg.get_by_text('Published from the authenticated companion', exact=True)).first
                        await post.locator('.like').click()
                        await post.get_by_role('button',name='Unlike · 1',exact=True).wait_for()
                        await post.get_by_role('button',name='Replies · 0',exact=True).click()
                        await post.get_by_role('textbox',name='Reply',exact=True).fill('Reply from the companion')
                        await post.get_by_role('button',name='Publish reply',exact=True).click()
                        await post.get_by_text('Reply from the companion',exact=True).wait_for()
                        await post.get_by_role('button',name='Replies · 1',exact=True).wait_for()
                        await pg.screenshot(path=str(shots / 'ext2-auth-actions.png'),full_page=True)
                        await pg.locator('#audience').select_option(label='Member private network · Private')
                        await pg.locator('#post-body').fill('Private companion post for members')
                        await pg.locator('#post-form button').click()
                        await pg.get_by_text('Post published.',exact=True).wait_for()
                        await pg.get_by_text('Private companion post for members',exact=True).wait_for()
                        await pg.screenshot(path=str(shots / 'ext2-private-feed.png'),full_page=True)
                        # Saved realistic X fixture: both legacy test-id and current public SSR article adapters.
                        fixture=(ROOT/'tests/fixtures/x-context.html').read_text()
                        await ctx.route('https://x.com/network-fixture',lambda route:route.fulfill(status=200,content_type='text/html',body=fixture))
                        x=await ctx.new_page();await x.goto('https://x.com/network-fixture')
                        await x.locator('[data-network-card]').nth(1).wait_for(timeout=20000)
                        await x.locator('#network-overlay-launcher').click()
                        await x.locator('#network-overlay-launcher[data-panel-state=opened]').wait_for()
                        await x.wait_for_function("document.documentElement.dataset.networkProbe==='blocked'")
                        assert await x.locator('[data-network-card]').count()==2
                        assert 'MEMBER_PRIVATE_ALLOWED' not in await x.locator('body').inner_text()
                        assert await x.locator('[data-network-card]').first.get_by_text('$CTX · Published call by @network_member · DEMO',exact=True).count()==1
                        await x.screenshot(path=str(shots/'ext2-context-fixture.png'),full_page=True)
                        # Dynamic/recycled tweet mutation; no duplicate cards on the same article.
                        await x.evaluate("document.querySelector('[data-testid=tweetText]').textContent='New token mention $NEW'")
                        await x.locator('[data-network-card]').first.get_by_text('@network_member · $NEW',exact=True).wait_for()
                        assert await x.locator('[data-network-card]').count()==2
                        live={'attempted':real_x,'source':'saved realistic DOM fixture'}
                        if real_x:
                            livepage=await ctx.new_page()
                            try:
                                response=await livepage.goto('https://x.com/solana',wait_until='domcontentloaded',timeout=25000)
                                await livepage.locator('[data-network-card]').first.wait_for(timeout=15000)
                                live={'attempted':True,'http_status':response.status if response else None,'url':'https://x.com/solana','article_cards':await livepage.locator('[data-network-card]').count(),'source':'live public X, unsigned browser'}
                            except Exception as error:
                                live={'attempted':True,'source':'saved realistic DOM fixture','live_result':'No usable live public article within timeout','error_type':type(error).__name__,'error':str(error).splitlines()[0][:250]}
                            await livepage.screenshot(path=str(shots/'ext2-real-x-attempt.png'),full_page=True)
                            await livepage.close()
                        await peer.locator('#feed-tab').select_option('mine')
                        await peer.get_by_text('Your permission-filtered feed',exact=True).wait_for()
                        await pg.locator('#logout').click()
                        await pg.locator('#signin').wait_for(state='visible')
                        await peer.locator('#signin').wait_for(state='visible')
                        await peer.get_by_text('Public updates · sign in to participate',exact=True).wait_for()
                        assert 'MEMBER_PRIVATE_ALLOWED' not in await peer.locator('body').inner_text()
                        await pg.get_by_text('Public updates · sign in to participate',exact=True).wait_for()
                        assert 'MEMBER_PRIVATE_ALLOWED' not in await pg.locator('body').inner_text()
                        assert not await worker.evaluate("(async()=>Boolean((await chrome.storage.session.get('auth')).auth))()")
                        status=await worker.evaluate("""async(base)=>{const r=await fetch(base+'/api/extension/me',{headers:{authorization:'Bearer '+globalThis.savedTestToken,'x-network-extension':chrome.runtime.id},credentials:'omit'});globalThis.savedTestToken=null;return r.status;}""",base)
                        assert status==401
                        await pg.screenshot(path=str(shots/'ext2-logout.png'),full_page=True)
                        assert not errors,errors
                        log.flush()
                        logs=(work/'server.log').read_text()
                        assert '/api/auth/oauth/x/callback?' not in logs and '/api/extension/auth/start?' not in logs
                        print(json.dumps({'result':'passed','chromium':ctx.browser.version,'auth':'real chrome.identity.launchWebAuthFlow; local mock X provider; one-time PKCE exchange',
                            'verified':['trusted-only session storage','member/private allowed feed','public post','private post','like','reply/count update','untrusted post markup stays text','context opt-in','both X DOM adapters','mutation refresh/no duplicates','content-script token and member-API denial','popup and launcher native sidePanel.open','cross-view sign-in/logout sync','server logout revocation','auth query redaction'],
                            'real_x':live,'page_errors':errors,'screenshots':[str(p) for p in sorted(shots.glob('ext2-*.png'))],
                            'unverified':['production X OAuth credentials and consent','Chrome Web Store review/install','native toolbar/panel chrome visual rendering','production PostgreSQL/Render deployment']},indent=2))
                    finally:
                        server.terminate();server.wait(timeout=10)
            finally: await ctx.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--shots',type=Path,default=ROOT/'screenshots/extension');parser.add_argument('--skip-real-x',action='store_true')
    args=parser.parse_args();asyncio.run(run(args.shots.resolve(),not args.skip_real_x))
