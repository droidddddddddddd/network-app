# Manual headless-Chrome installability check (not collected by pytest). Run against a local server on :8765.
import json, asyncio
from playwright.async_api import async_playwright
U='http://localhost:8765/'
O='/workspace/network-app/screenshots/pwa/'
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(args=['--enable-features=DesktopPWAsDefaultOfflineInstall'])
    ctx=await b.new_context(**p.devices['Pixel 7'])
    pg=await ctx.new_page(); errs=[]
    pg.on('console', lambda m: m.type=='error' and errs.append(m.text))
    await pg.goto(U); await pg.wait_for_timeout(1500)
    sw=await pg.evaluate("navigator.serviceWorker.ready.then(r=>({scope:r.scope,state:r.active&&r.active.state}))")
    await pg.reload(); await pg.wait_for_timeout(1500)
    ctrl=await pg.evaluate("!!navigator.serviceWorker.controller")
    cdp=await ctx.new_cdp_session(pg)
    inst=await cdp.send('Page.getInstallabilityErrors')
    man=await cdp.send('Page.getAppManifest')
    caches=await pg.evaluate("caches.keys().then(async ks=>{const o={};for(const k of ks){o[k]=(await (await caches.open(k)).keys()).map(r=>new URL(r.url).pathname)}return o})")
    # fire a synthetic beforeinstallprompt if Chrome headless didn't (headless never shows the real prompt UI)
    fired=await pg.evaluate("!!document.querySelector('#pwa-banner [data-pwa=install]')")
    if not fired:
      await pg.evaluate("(()=>{const e=new Event('beforeinstallprompt');e.prompt=()=>{};e.userChoice=Promise.resolve({outcome:'dismissed'});window.dispatchEvent(e)})()")
      await pg.wait_for_timeout(300)
    await pg.screenshot(path=O+'android_install_banner.png')
    # offline fallback
    await ctx.set_offline(True); await pg.goto(U+'?x=1'); await pg.wait_for_timeout(800)
    offline_title=await pg.title(); await pg.screenshot(path=O+'offline_navigation.png'); await ctx.set_offline(False)
    print(json.dumps(dict(sw=sw,controlled=ctrl,installability=inst,manifest_errors=man.get('errors'),manifest_url=man.get('url'),caches=caches,real_bip_fired=fired,offline_title=offline_title,console_errors=errs),indent=1))
    ctx2=await b.new_context(**p.devices['iPhone 14'])
    pg2=await ctx2.new_page(); await pg2.goto(U); await pg2.wait_for_timeout(1500)
    await pg2.screenshot(path=O+'ios_install_banner.png')
    print('ios banner:', await pg2.evaluate("(document.querySelector('#pwa-banner')||{}).innerText"))
    await b.close()
asyncio.run(main())
