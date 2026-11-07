/* All tokens and authenticated fetches stay in this trusted MV3 worker. */
importScripts('config.js');
const base = NETWORK_BASE_URL.replace(/\/$/, '');
const own = chrome.runtime.getURL('sidepanel.html');
const locks = { auth: null };
const contextCache = new Map();
const ready = chrome.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' });
const b64 = bytes => btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const random = () => b64(crypto.getRandomValues(new Uint8Array(32)));
async function session() {
  await ready;
  const { auth } = await chrome.storage.session.get('auth');
  if (!auth) return null;
  if (Date.parse(auth.expires_at) <= Date.now()) { await chrome.storage.session.remove('auth'); return null; }
  return auth;
}
async function api(path, { method = 'GET', body, auth = true, requireAuth = false } = {}) {
  const saved = auth ? await session() : null;
  if (requireAuth && !saved) throw new Error('Sign in to NETWORK first.');
  const headers = { 'x-csrf': '1', 'x-network-extension': chrome.runtime.id };
  if (body !== undefined) headers['content-type'] = 'application/json';
  if (saved) headers.authorization = 'Bearer ' + saved.token;
  const response = await fetch(base + '/api/extension/' + path, {
    method, headers, credentials: 'omit', cache: 'no-store', redirect: 'error',
    body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(20000)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) await chrome.storage.session.remove('auth');
    throw new Error(typeof data.detail === 'string' ? data.detail : 'NETWORK request failed. Try again.');
  }
  return data;
}
async function signIn() {
  if (locks.auth) return locks.auth;
  locks.auth = (async () => {
    const verifier = random(), state = random();
    const challenge = b64(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))));
    const url = new URL(base + '/api/extension/auth/start');
    url.search = new URLSearchParams({ extension_id: chrome.runtime.id, challenge, state });
    // No automatic auth at startup: only an explicit click in the extension UI starts this top-level window.
    const result = await chrome.identity.launchWebAuthFlow({ url: url.href, interactive: true });
    if (!result) throw new Error('Sign-in was cancelled.');
    const redirect = new URL(result);
    if (redirect.origin + redirect.pathname !== chrome.identity.getRedirectURL('network') || redirect.searchParams.get('state') !== state)
      throw new Error('Invalid sign-in response. Start again.');
    if (redirect.searchParams.has('error')) throw new Error('X sign-in was cancelled or could not be completed. Try again.');
    const code = redirect.searchParams.get('code');
    if (!code) throw new Error('Sign-in did not return an authorization code.');
    const auth = await api('auth/exchange', { method: 'POST', body: { code, verifier }, auth: false });
    await chrome.storage.session.set({ auth });
    return auth.user; // Never return a token through runtime messages.
  })().finally(() => { locks.auth = null; });
  return locks.auth;
}
async function logOut() {
  let revoked = true;
  try { if (await session()) await api('auth/logout', { method: 'POST', requireAuth: true }); }
  catch (_) { revoked = false; }
  finally { await chrome.storage.session.remove('auth'); }
  return { revoked };
}
const positive = n => Number.isSafeInteger(n) && n > 0;
async function context(query) {
  const { contextEnabled } = await chrome.storage.local.get('contextEnabled');
  if (!contextEnabled) return { disabled: true };
  const q = {};
  if (/^[A-Za-z0-9_]{1,15}$/.test(query?.handle || '')) q.handle = query.handle;
  if (/^[A-Za-z0-9]{1,12}$/.test(query?.symbol || '')) q.symbol = query.symbol;
  if (/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(query?.mint || '')) q.mint = query.mint;
  if (!Object.keys(q).length) return { profiles: [], calls: [] };
  const key = new URLSearchParams(q).toString(), cached = contextCache.get(key);
  if (cached && cached.until > Date.now()) return cached.data;
  const data = await api('context?' + key, { auth: false }); // Public only: private data never enters X's DOM.
  if (contextCache.size >= 100) contextCache.delete(contextCache.keys().next().value);
  contextCache.set(key, { data, until: Date.now() + 60000 });
  return data;
}
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const panel = sender.id === chrome.runtime.id && sender.url === own;
  const x = sender.id === chrome.runtime.id && sender.tab && /^https:\/\/(x\.com|twitter\.com)\//.test(sender.url || '');
  if (!panel && !x) return;
  const run = async () => {
    if (message?.type === 'OPEN_NETWORK_PANEL' && x) {
      await chrome.sidePanel.open({ windowId: sender.tab.windowId }); return { ok: true };
    }
    if (message?.type === 'CONTEXT_ENABLED') return Boolean((await chrome.storage.local.get('contextEnabled')).contextEnabled);
    if (message?.type === 'CONTEXT') return context(message.query);
    if (!panel) throw new Error('This action is available only in the NETWORK extension UI.');
    switch (message?.type) {
      case 'AUTH_STATUS': return (await session()) ? await api('me', { requireAuth: true }) : null;
      case 'SIGN_IN': return signIn();
      case 'LOG_OUT': return logOut();
      case 'SET_CONTEXT': await chrome.storage.local.set({ contextEnabled: message.enabled === true }); contextCache.clear(); return true;
      case 'FEED': {
        const tab = ['discover', 'network', 'following', 'mine'].includes(message.tab) ? message.tab : 'discover';
        const q = new URLSearchParams({ tab });
        if (positive(message.before)) q.set('before', message.before);
        return api('feed?' + q);
      }
      case 'NETWORKS': return api('networks', { requireAuth: true });
      case 'POST': {
        if (typeof message.body !== 'string' || message.body.length > 2000) throw new Error('Write a post up to 2,000 characters.');
        return api('posts', { method: 'POST', requireAuth: true, body: { body: message.body,
          network_id: positive(message.networkId) ? message.networkId : null,
          parent_id: positive(message.parentId) ? message.parentId : null } });
      }
      case 'LIKE': if (positive(message.id)) return api(`posts/${message.id}/like`, { method: 'POST', requireAuth: true }); break;
      case 'THREAD': if (positive(message.id)) return api(`posts/${message.id}`, { requireAuth: true }); break;
    }
    throw new Error('Unknown NETWORK action.');
  };
  run().then(data => sendResponse({ ok: true, data }), error => sendResponse({ ok: false,
    error: error instanceof Error && !/https?:|code=|token/i.test(error.message) ? error.message : 'NETWORK could not complete that action. Try again.' }));
  return true;
});
