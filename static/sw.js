/* NETWORK service worker. __BUILD__ is replaced by the server with a hash of static/, so every deploy gets a new cache. */
const VERSION = '__BUILD__';
const CACHE = 'network-shell-' + VERSION;
const SHELL = ['/static/offline.html', '/static/app.css', '/static/app.js', '/static/trust.js', '/static/pwa.js',
  '/manifest.webmanifest', '/static/icons/icon-192.png', '/static/icons/icon-512.png', '/static/icons/apple-touch-icon.png', '/static/icons/favicon-32.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL.map(u => new Request(u, { cache: 'reload', credentials: 'omit' })))).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('network-') && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// Never cached: API, auth, websockets, user uploads, the SW itself. These always go to the network.
const NEVER = p => p.startsWith('/api/') || p === '/api' || p.startsWith('/ws') || p.startsWith('/uploads/') || p.startsWith('/auth') || p === '/sw.js';

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (NEVER(url.pathname)) return;               // default browser handling, no cache
  if (req.mode === 'navigate') {
    // network-first; offline -> branded offline page (the SPA needs the API, so a cached shell would just show errors)
    e.respondWith(fetch(req).catch(() => caches.match('/static/offline.html')));
    return;
  }
  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    // stale-while-revalidate for static assets
    e.respondWith(caches.open(CACHE).then(c => c.match(req).then(hit => {
      const net = fetch(req).then(r => { if (r.ok && r.type === 'basic') c.put(req, r.clone()); return r; });
      return hit ? (net.catch(() => {}), hit) : net;
    })));
  }
});

self.addEventListener('message', e => { if (e.data === 'skipWaiting') self.skipWaiting(); });
