/* Trusted extension UI; content is rendered with textContent, never HTML. */
const base = NETWORK_BASE_URL.replace(/\/$/, '');
const $ = id => document.getElementById(id);
$('workspace').href = base + '/';
let user = null, lastId = null, authGeneration = 0, feedGeneration = 0;
const status = $('status'), feed = $('feed');
function node(tag, text, className) { const e = document.createElement(tag); e.textContent = text; if (className) e.className = className; return e; }
async function send(type, data = {}) {
  const result = await chrome.runtime.sendMessage({ type, ...data });
  if (!result?.ok) throw new Error(result?.error || 'NETWORK is unavailable. Try again.');
  return result.data;
}
function fail(error) { status.className = 'error'; status.textContent = error.message; }
async function authStatus() {
  const generation = ++authGeneration;
  const nextUser = await send('AUTH_STATUS').catch(() => null);
  if (generation !== authGeneration) return;
  user = nextUser;
  $('signin').hidden = Boolean(user); $('logout').hidden = !user; $('member').hidden = !user; $('compose').hidden = !user;
  $('member').textContent = user ? 'Signed in as @' + user.username : '';
  $('audience').replaceChildren(new Option('Public profile', ''));
  if (user) {
    const nets = await send('NETWORKS');
    if (generation !== authGeneration) return;
    $('audience').replaceChildren(new Option('Public profile', ''));
    for (const net of nets) $('audience').add(new Option(net.name + (net.is_private ? ' · Private' : ''), net.id));
  }
}
function renderPost(post, reply = false) {
  const card = document.createElement('article'); card.dataset.post = post.id;
  card.append(node('b', '@' + post.author), node('p', post.body));
  if (post.renetwork) card.append(node('p', 'Re-Networked @' + post.renetwork.author.username + ': ' + post.renetwork.body));
  if (post.image_url || post.renetwork?.image_url) card.append(node('div', 'Attachment · open the post on NETWORK to view', 'meta'));
  if (post.network) card.append(node('div', post.network.name + (post.network.is_private ? ' · Private' : ''), 'meta'));
  const date = new Date(post.created_at);
  card.append(node('div', Number.isNaN(date.valueOf()) ? '' : date.toLocaleString(), 'meta'));
  if (post.is_demo) card.append(node('div', 'DEMO · example content', 'demo'));
  if (post.call) card.append(node('div', '$' + post.call.symbol + ' · Published call, not an executed trade', 'meta'));
  const link = node('a', 'View on NETWORK'); link.href = base + '/#/post/' + post.id; link.target = '_blank'; link.rel = 'noopener noreferrer'; card.append(link);
  if (user) {
    const like = node('button', (post.liked ? 'Unlike' : 'Like') + ' · ' + (post.likes || 0));
    like.type = 'button'; like.className = 'like';
    like.addEventListener('click', async () => { like.disabled = true; try { const r = await send('LIKE', { id: post.id }); like.textContent = (r.liked ? 'Unlike' : 'Like') + ' · ' + r.likes; } catch (e) { fail(e); } finally { like.disabled = false; } });
    card.append(like);
    if (!reply) {
      const button = node('button', 'Replies · ' + (post.replies || 0)); button.type = 'button';
      const area = document.createElement('section'); area.className = 'replies'; area.hidden = true;
      const list = document.createElement('div'), form = document.createElement('form'), input = document.createElement('textarea');
      input.maxLength = 2000; input.required = true; input.placeholder = 'Write a reply…'; input.setAttribute('aria-label', 'Reply');
      const submit = node('button', 'Publish reply'); submit.type = 'submit'; form.append(input, submit); area.append(list, form);
      button.addEventListener('click', async () => { area.hidden = !area.hidden; if (!area.hidden) try { const t = await send('THREAD', { id: post.id }); list.replaceChildren(...t.replies.map(p => renderPost(p, true))); post.replies = t.replies.length; button.textContent = 'Replies · ' + post.replies; } catch (e) { fail(e); } });
      form.addEventListener('submit', async event => { event.preventDefault(); submit.disabled = true; try { const r = await send('POST', { body: input.value, parentId: post.id }); list.append(renderPost(r, true)); post.replies = (post.replies || 0) + 1; button.textContent = 'Replies · ' + post.replies; input.value = ''; status.textContent = 'Reply published.'; } catch (e) { fail(e); } finally { submit.disabled = false; } });
      card.append(button, area);
    }
  }
  return card;
}
async function loadFeed(append = false) {
  const generation = ++feedGeneration, uid = user?.id || 0;
  $('refresh').disabled = true; status.className = ''; status.textContent = 'Loading updates…';
  if (!append) { feed.replaceChildren(); lastId = null; }
  try {
    const data = await send('FEED', { tab: $('feed-tab').value, before: append ? lastId : null });
    if (generation !== feedGeneration || uid !== (user?.id || 0)) return;
    for (const p of data.posts) if (Number.isSafeInteger(p.id)) feed.append(renderPost(p));
    lastId = data.posts.length ? data.posts[data.posts.length - 1].id : lastId;
    $('more').hidden = data.posts.length < 30;
    status.textContent = feed.children.length ? (data.scope === 'member' ? 'Your permission-filtered feed' : 'Public updates · sign in to participate') : 'No updates yet.';
  } catch (e) { if (generation === feedGeneration) { fail(e); await authStatus().catch(() => {}); } }
  finally { if (generation === feedGeneration) $('refresh').disabled = false; }
}
$('signin').addEventListener('click', async () => { $('signin').disabled = true; try { await send('SIGN_IN'); await authStatus(); await loadFeed(); } catch (e) { fail(e); } finally { $('signin').disabled = false; } });
$('logout').addEventListener('click', async () => { const result = await send('LOG_OUT'); $('feed-tab').value = 'discover'; await authStatus(); await loadFeed(); if (!result.revoked) fail(new Error('Signed out locally. Server revocation could not be confirmed; the session expires within one hour.')); });
$('post-form').addEventListener('submit', async event => { event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true; try { await send('POST', { body: $('post-body').value, networkId: Number($('audience').value) || null }); $('post-body').value = ''; await loadFeed(); status.textContent = 'Post published.'; } catch (e) { fail(e); } finally { button.disabled = false; } });
$('refresh').addEventListener('click', () => loadFeed()); $('more').addEventListener('click', () => loadFeed(true)); $('feed-tab').addEventListener('change', () => loadFeed());
$('context').addEventListener('change', () => send('SET_CONTEXT', { enabled: $('context').checked }).catch(fail));
$('panel').addEventListener('click', () => { chrome.windows.getCurrent(win => { chrome.sidePanel.open({ windowId: win.id }).then(() => { $('panel').textContent = 'Side panel opened'; }).catch(() => fail(new Error('Use the NETWORK launcher on X or open the full website.'))); }); });
(async () => { $('context').checked = await send('CONTEXT_ENABLED'); await authStatus(); await loadFeed(); })().catch(fail);

// Keep popup and side panel synchronized without ever sending credentials to content scripts.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'session' && changes.auth) {
    ++feedGeneration; feed.replaceChildren();
    if (!changes.auth.newValue) { user = null; $('compose').hidden = true; $('feed-tab').value = 'discover'; }
    authStatus().then(() => loadFeed()).catch(fail);
  }
  if (area === 'local' && changes.contextEnabled) $('context').checked = changes.contextEnabled.newValue === true;
});
