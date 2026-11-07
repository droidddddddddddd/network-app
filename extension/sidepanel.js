/* Extension-owned UI. API text is always textContent, never HTML. */
const base = NETWORK_BASE_URL.replace(/\/$/, '');
const workspace = document.getElementById('workspace');
workspace.href = base + '/';
const status = document.getElementById('status');
const feed = document.getElementById('feed');
const refresh = document.getElementById('refresh');
function node(tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  return el;
}
async function loadFeed() {
  refresh.disabled = true;
  status.className = '';
  status.textContent = 'Loading public updates…';
  feed.replaceChildren();
  try {
    const response = await fetch(base + '/api/extension/feed', {
      credentials: 'omit', cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(15000)
    });
    if (!response.ok) throw new Error('Feed unavailable');
    const data = await response.json();
    if (data.scope !== 'public' || !Array.isArray(data.posts)) throw new Error('Invalid feed');
    for (const post of data.posts.slice(0, 12)) {
      if (!Number.isSafeInteger(post.id) || post.id <= 0) continue;
      const card = document.createElement('article');
      card.append(node('b', '@' + String(post.author)), node('p', String(post.body)));
      const date = new Date(post.created_at);
      card.append(node('div', Number.isNaN(date.valueOf()) ? '' : date.toLocaleString(), 'meta'));
      if (post.is_demo) card.append(node('div', 'DEMO · example content', 'demo'));
      const link = node('a', 'View on NETWORK');
      link.href = base + '/#/post/' + post.id;
      link.target = '_blank'; link.rel = 'noopener noreferrer';
      card.append(link); feed.append(card);
    }
    status.textContent = feed.children.length ? 'Public updates · refresh to check for more' : 'No public updates yet. Open NETWORK to start your network.';
  } catch (_) {
    status.className = 'error';
    status.textContent = 'Could not load public updates. The server may be waking up. Try Refresh or open NETWORK.';
  } finally { refresh.disabled = false; }
}
refresh.addEventListener('click', loadFeed);
document.getElementById('panel').addEventListener('click', () => {
  if (!chrome.sidePanel) { status.textContent = 'Side panels need a recent Chrome browser. Use Open NETWORK instead.'; return; }
  chrome.windows.getCurrent(win => {
    chrome.sidePanel.open({ windowId: win.id }).then(() => {
      document.getElementById('panel').textContent = 'Side panel opened';
    }).catch(() => {
      status.textContent = 'Use the NETWORK launcher on X to open the side panel, or open NETWORK in a tab.';
    });
  });
});
loadFeed();
