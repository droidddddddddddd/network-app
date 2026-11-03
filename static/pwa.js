/* NETWORK PWA: service worker registration, install prompt, iOS instructions. */
(() => {
  const standalone = () => window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const ua = navigator.userAgent;
  const isIOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isIOSSafari = isIOS && /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  const DISMISS = 'pwa-banner-dismissed';
  let deferred = null;

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      let reloaded = false;
      const hadController = !!navigator.serviceWorker.controller;
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        // a new deploy's worker took over: reload once so the new shell is used
        if (hadController && !reloaded) { reloaded = true; location.reload(); }
      });
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).then(reg => {
        setInterval(() => reg.update().catch(() => {}), 60 * 60 * 1000);
      }).catch(() => {});
    });
  }

  const mode = () => standalone() ? 'installed' : deferred ? 'prompt' : isIOSSafari ? 'ios' : null;
  const IOS_TEXT = 'Tap the Share button in Safari, then <b>Add to Home Screen</b>.';

  async function install() {
    if (!deferred) return;
    const d = deferred; deferred = null;
    d.prompt();
    try { await d.userChoice; } catch (_) {}
    render();
  }

  function banner() {
    let el = document.getElementById('pwa-banner');
    const m = mode();
    const show = (m === 'prompt' || m === 'ios') && !localStorage.getItem(DISMISS);
    if (!show) { if (el) el.remove(); return; }
    if (!el) { el = document.createElement('div'); el.id = 'pwa-banner'; el.className = 'pwa-banner'; el.setAttribute('role', 'region'); el.setAttribute('aria-label', 'Install app'); document.body.appendChild(el); }
    el.innerHTML = `<img src="/static/icons/icon-192.png" alt="" width="40" height="40"><div class="grow"><b>Install NETWORK</b><div class="tiny muted">${m === 'prompt' ? 'Add the app to your home screen.' : IOS_TEXT}</div></div>`
      + (m === 'prompt' ? '<button class="btn primary sm" data-pwa="install">Install</button>' : '')
      + '<button class="iconbtn" data-pwa="dismiss" aria-label="Dismiss">✕</button>';
  }

  function card() {
    const slot = document.getElementById('pwa-card');
    if (!slot) return;
    const m = mode();
    if (!m) { slot.innerHTML = ''; return; }
    slot.innerHTML = `<div class="card"><h2 style="margin-top:0">Install app</h2>${m === 'installed' ? '<p class="tiny muted">You are using the installed NETWORK app.</p>'
      : m === 'prompt' ? '<p class="tiny muted">Install NETWORK on this device for a full-screen app with its own icon.</p><button class="btn primary sm" data-pwa="install">Install app</button>'
      : `<p class="tiny muted">On iPhone or iPad: ${IOS_TEXT}</p>`}</div>`;
  }

  function render() { banner(); card(); }

  window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e; render(); });
  window.addEventListener('appinstalled', () => { deferred = null; render(); });
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-pwa]');
    if (!b) return;
    if (b.dataset.pwa === 'install') install();
    if (b.dataset.pwa === 'dismiss') { localStorage.setItem(DISMISS, '1'); banner(); }
  });
  // the Settings page is rendered by the SPA router; fill its slot whenever it appears
  new MutationObserver(() => { const s = document.getElementById('pwa-card'); if (s && !s.dataset.done) { s.dataset.done = '1'; card(); } })
    .observe(document.getElementById('app') || document.body, { childList: true, subtree: true });
  window.addEventListener('DOMContentLoaded', render);
  render();
})();
