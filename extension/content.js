/* Public contextual cards only. No tweet text, private feed or session token crosses this boundary. */
(() => {
  if (document.getElementById('network-overlay-launcher')) return;
  const host = document.createElement('div'); host.id = 'network-overlay-launcher';
  host.style.cssText = 'position:fixed;right:18px;bottom:96px;z-index:2147483647';
  const shadow = host.attachShadow({ mode: 'closed' });
  const style = document.createElement('style');
  style.textContent = 'button{border:1px solid #22f08a;background:#09130f;color:#eafff3;border-radius:999px;padding:12px 16px;font:700 13px system-ui;box-shadow:0 8px 28px #0008;cursor:pointer}';
  const button = document.createElement('button'); button.type = 'button'; button.title = 'Open NETWORK beside X';
  const mark = document.createElement('img'); mark.src = chrome.runtime.getURL('logo.svg'); mark.alt = ''; mark.width = 22; mark.height = 22;
  mark.style.cssText = 'vertical-align:middle;margin-right:7px'; button.append(mark, document.createTextNode('NETWORK'));
  button.addEventListener('click', async () => { try {
    const result = await chrome.runtime.sendMessage({ type: 'OPEN_NETWORK_PANEL' });
    host.dataset.panelState = result?.ok ? 'opened' : 'unavailable';
    if (!result?.ok) button.title = 'Use the NETWORK toolbar icon to open the companion';
  } catch (_) { host.dataset.panelState = 'error'; button.title = 'Reload X after updating NETWORK'; } });
  shadow.append(style, button); document.documentElement.append(host);
  let enabled = false, timer = null, seen = new WeakMap(), active = 0;
  const el = (tag, text) => { const n = document.createElement(tag); n.textContent = text; return n; };
  function queryFor(article) {
    const textNode = article.querySelector('[data-testid="tweetText"]') || article.querySelector('[lang]');
    let text = textNode?.textContent?.slice(0, 4000) || '';
    if (!textNode) {
      const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
      let current, count = 0;
      while ((current = walker.nextNode()) && text.length < 4000 && count++ < 500) {
        if (!current.parentElement?.closest('[data-network-card],script,style')) text += current.textContent + ' ';
      }
      text = text.slice(0, 4000);
    }
    let handle = '';
    for (const a of article.querySelectorAll('[data-testid="User-Name"] a[href], a[href*="/status/"]')) {
      const match = a.getAttribute('href')?.match(/^\/([A-Za-z0-9_]{1,15})(?:\/status\/\d+)?$/);
      if (match && !['home', 'search', 'explore', 'notifications'].includes(match[1])) { handle = match[1]; break; }
    }
    const symbol = text.match(/(?:^|[^\w])\$([A-Za-z][A-Za-z0-9]{0,11})\b/)?.[1] || '';
    const mint = text.match(/(?:^|[^1-9A-HJ-NP-Za-km-z])([1-9A-HJ-NP-Za-km-z]{32,44})(?![1-9A-HJ-NP-Za-km-z])/)?.[1] || '';
    return { handle, symbol, mint };
  }
  function cardFor(data, query) {
    const card = el('aside', ''); card.dataset.networkCard = 'true';
    card.addEventListener('click', event => event.stopPropagation());
    const root = card.attachShadow({ mode: 'open' });
    const css = el('style', ':host{display:block;margin:10px 0}section{border:1px solid #28523a;border-radius:12px;padding:12px;background:#08110c;color:#dfeee5;font:12px/1.5 system-ui;overflow-wrap:anywhere}header{color:#22f08a;font-weight:800;display:flex;align-items:center;gap:8px}a{color:#22f08a;text-decoration:none}p{margin:7px 0}small{color:#a3b5aa}img{width:20px;height:20px}');
    const section = el('section', ''), header = el('header', '');
    const logo = document.createElement('img'); logo.src = chrome.runtime.getURL('logo.svg'); logo.alt = 'NETWORK';
    header.append(logo, el('span', 'NETWORK · Public context')); section.append(header);
    section.append(el('p', [query.handle && '@' + query.handle, query.symbol && '$' + query.symbol, query.mint && 'Address mention: ' + query.mint].filter(Boolean).join(' · ')));
    const link = (text, hash) => { const a = el('a', text); a.href = NETWORK_BASE_URL.replace(/\/$/, '') + '/' + hash; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; };
    for (const profile of data.profiles || []) {
      if (!/^[A-Za-z0-9_]{3,40}$/.test(profile.username)) continue;
      section.append(link('@' + profile.username + ' · X account linked' + (profile.is_demo ? ' · DEMO' : ''), '#/u/' + profile.username));
    }
    for (const call of data.calls || []) {
      if (!Number.isSafeInteger(call.post_id)) continue;
      const p = el('p', ''); p.append(link('$' + call.symbol + ' · Published call by @' + call.author + (call.is_demo ? ' · DEMO' : ''), '#/post/' + call.post_id));
      p.append(el('br', ''), el('small', 'Mint: ' + call.token_address + ' · ' + (call.independently_tracked ? 'Market snapshots tracked' : 'Not independently tracked'))); section.append(p);
    }
    if (!(data.profiles?.length || data.calls?.length)) section.append(el('p', 'No matching public NETWORK records.'));
    section.append(el('small', data.notice || 'Published calls are not executed trades or verified trading performance.'));
    root.append(css, section); return card;
  }
  function schedule() { if (!timer) timer = setTimeout(() => { timer = null; scan(); }, 350); }
  async function scan() {
    if (!enabled || active >= 3) return;
    const articles = [...document.querySelectorAll('article[data-testid="tweet"], article[role="article"], article:has(a[href*="/status/"])')].slice(0, 100);
    for (const article of articles) {
      if (active >= 3) break;
      const rect = article.getBoundingClientRect(); if (rect.bottom < -800 || rect.top > innerHeight + 800) continue;
      const query = queryFor(article); if (!Object.values(query).some(Boolean)) continue;
      const key = JSON.stringify(query); if (seen.get(article) === key) continue;
      seen.set(article, key); article.querySelector('[data-network-card]')?.remove(); active++;
      chrome.runtime.sendMessage({ type: 'CONTEXT', query }).then(result => {
        if (!enabled || !article.isConnected || JSON.stringify(queryFor(article)) !== key || !result?.ok || result.data.disabled) return;
        article.append(cardFor(result.data, query));
      }).catch(() => {}).finally(() => { active--; schedule(); });
    }
  }
  const observer = new MutationObserver(records => {
    if (enabled && records.some(r => !r.target.parentElement?.closest('[data-network-card]'))) schedule();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  window.addEventListener('scroll', schedule, { passive: true });
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === 'local' && changes.contextEnabled) {
      enabled = changes.contextEnabled.newValue === true; seen = new WeakMap();
      document.querySelectorAll('[data-network-card]').forEach(n => n.remove()); if (enabled) schedule();
    }
  });
  chrome.runtime.sendMessage({ type: 'CONTEXT_ENABLED' }).then(r => { enabled = r?.ok && r.data === true; if (enabled) schedule(); }).catch(() => {});
})();
