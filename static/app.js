/* NETWORK — vanilla JS single-page app. All output is escaped; permissions are enforced server-side. */
'use strict';
const S = { me: null, meta: null, ws: null, route: '', chatNet: null, dmWith: null, newPosts: 0 };
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, opts = {}) {
  const o = { method: opts.method || (opts.body ? 'POST' : 'GET'), headers: { 'x-csrf': '1' }, credentials: 'same-origin' };
  if (opts.body instanceof FormData) o.body = opts.body;
  else if (opts.body !== undefined) { o.headers['content-type'] = 'application/json'; o.body = JSON.stringify(opts.body); }
  let r;
  try { r = await fetch('/api' + path, o); } catch { throw new Error('Network error — check your connection.'); }
  let data = null; try { data = await r.json(); } catch {}
  if (!r.ok) { const err = new Error((data && data.detail) || `Request failed (${r.status})`); err.status = r.status; throw err; }
  return data;
}
function toast(msg, isErr) { const d = document.createElement('div'); if (isErr) d.className = 'e'; d.textContent = msg; $('#toast').append(d); setTimeout(() => d.remove(), 3800); }
const fail = e => toast(e.message || String(e), true);

const P = {
  home: 'M3 11l9-8 9 8v9a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1z',
  networks: 'M16 11a4 4 0 10-4-4 4 4 0 004 4zM8 13a3 3 0 10-3-3 3 3 0 003 3zm8 1c-2.7 0-8 1.3-8 4v2h16v-2c0-2.7-5.3-4-8-4zM8 15c-.6 0-1.3 0-2 .1C3.6 15.5 1 16.6 1 18v2h5v-2c0-1.1.6-2.1 2-3z',
  discover: 'M12 2a10 10 0 1010 10A10 10 0 0012 2zm2.8 12.8L7 17l2.2-7.8L17 7z',
  opps: 'M12.6 6.4L10 4 3 10.6l1.4 1.4L6 10.5V20h3v-5h2v5h3v-6l4.6 4.3L20 17zM14 4l7 6-1.4 1.4L14 6.6 12.6 5.2z',
  rank: 'M4 20V10h4v10zm6 0V4h4v16zm6 0v-7h4v7z',
  msg: 'M3 5h18v14H3zm2 2v.5l7 4.5 7-4.5V7l-7 4.5z',
  bell: 'M12 22a2.5 2.5 0 002.5-2.5h-5A2.5 2.5 0 0012 22zm7-6V11a7 7 0 00-5.5-6.8V3h-3v1.2A7 7 0 005 11v5l-2 2v1h18v-1z',
  user: 'M12 12a5 5 0 10-5-5 5 5 0 005 5zm0 2c-3.3 0-10 1.7-10 5v3h20v-3c0-3.3-6.7-5-10-5z',
  plus: 'M11 4h2v7h7v2h-7v7h-2v-7H4v-2h7z',
  search: 'M10 3a7 7 0 015.6 11.2l5.1 5.1-1.4 1.4-5.1-5.1A7 7 0 1110 3zm0 2a5 5 0 100 10 5 5 0 000-10z',
  photo: 'M4 5h16v14H4zm2 12h12l-4-5-3 4-2-2zM8 7.5A1.5 1.5 0 109.5 9 1.5 1.5 0 008 7.5z',
  chart: 'M3 3v18h18v-2H5V3zm4 12l4-4 3 3 6-6-1.4-1.4L14 11.2l-3-3-5.4 5.4z',
  reply: 'M4 4h16v12H7l-3 3z',
  renet: 'M7 7h10v3l4-4-4-4v3H5v6h2zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2z',
  heart: 'M12 21s-7.5-4.6-9.5-9.3C1 8 3.4 4.5 7 4.5c2 0 3.5 1.1 5 2.8 1.5-1.7 3-2.8 5-2.8 3.6 0 6 3.5 4.5 7.2C19.5 16.4 12 21 12 21z',
  share: 'M12 3l5 5h-3v7h-4V8H7zm-7 14h14v4H5z',
  dots: 'M5 10a2 2 0 102 2 2 2 0 00-2-2zm7 0a2 2 0 102 2 2 2 0 00-2-2zm7 0a2 2 0 102 2 2 2 0 00-2-2z',
  check: 'M12 2l2.4 1.8 3-.2.9 2.9 2.5 1.7-1 2.8 1 2.8-2.5 1.7-.9 2.9-3-.2L12 22l-2.4-1.8-3 .2-.9-2.9L3.2 15.8l1-2.8-1-2.8 2.5-1.7.9-2.9 3 .2zm-1.2 13.2l5.7-5.7-1.4-1.4-4.3 4.3-2-2-1.4 1.4z',
  people: 'M9 11a4 4 0 10-4-4 4 4 0 004 4zm7 0a3 3 0 10-3-3 3 3 0 003 3zM9 13c-3 0-8 1.5-8 4v3h16v-3c0-2.5-5-4-8-4zm7 0c-.4 0-.8 0-1.3.1A5 5 0 0118 17v3h5v-3c0-2.5-4.5-4-7-4z',
  fire: 'M13 2s1 3-1 6-4 4-4 8a6 6 0 0012 0c0-3-1.5-5-3-6 0 2-1 3-2 3 1-3 0-8-2-11z',
  trophy: 'M7 3h10v3h4v3a4 4 0 01-4 4h-.3A5 5 0 0113 16v3h4v2H7v-2h4v-3a5 5 0 01-3.7-3H7a4 4 0 01-4-4V6h4zm10 5v3a2 2 0 002-2V8zM5 8v1a2 2 0 002 2V8z',
  bag: 'M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2h4v13H4V7zm2 0h4V5h-4z',
  bolt: 'M13 2L4 14h6l-1 8 9-12h-6z',
};
const ic = (n, cls = '') => `<svg viewBox="0 0 24 24" fill="currentColor" class="${cls}" aria-hidden="true"><path d="${P[n]}"/></svg>`;
const vbadge = (title = 'Identity verified') => `<svg class="vbadge" viewBox="0 0 24 24" fill="#22f08a"><title>${title}</title><path d="${P.check}"/></svg>`;

const ago = t => { const s = (Date.now() - new Date(t)) / 1000; if (s < 60) return 'now'; if (s < 3600) return `${Math.floor(s / 60)}m`; if (s < 86400) return `${Math.floor(s / 3600)}h`; if (s < 604800) return `${Math.floor(s / 86400)}d`; return new Date(t).toLocaleDateString(); };
const kfmt = n => n >= 1e9 ? (n / 1e9).toFixed(1) + 'B' : n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? (n / 1e3).toFixed(1) + 'K' : String(Math.round(n || 0));
const usd = n => n == null ? '—' : '$' + (n >= 1 ? kfmt(n) : Number(n).toPrecision(4));
const mx = v => v == null ? '—' : v.toFixed(2) + '×';
const pct = v => v == null ? '—' : Math.round(v * 100) + '%';
const initials = s => esc((s || '?').replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || '?');
const avatar = (u, cls = '') => u && u.avatar_url ? `<img class="av ${cls}" src="${esc(u.avatar_url)}" alt="" loading="lazy">` : `<span class="av ${cls}">${initials(u ? (u.display_name || u.name || u.username) : '?')}</span>`;
const netAv = (n, cls = '') => n && n.avatar_url ? `<img class="av sq ${cls}" src="${esc(n.avatar_url)}" alt="" loading="lazy">` : `<span class="av sq ${cls}">${initials(n && n.name)}</span>`;
const demo = x => x && x.is_demo ? ' <span class="demo" title="Seeded demo content">DEMO</span>' : '';
function rich(text) {
  return esc(text)
    .replace(/https?:\/\/[^\s<]+/g, u => `<a class="t" href="${u}" target="_blank" rel="noopener noreferrer nofollow">${u}</a>`)
    .replace(/(^|[\s(])@([A-Za-z0-9_]{3,20})\b/g, '$1<a class="t" href="#/u/$2">@$2</a>')
    .replace(/(^|[\s(])#([A-Za-z0-9_]{2,30})\b/g, '$1<a class="t" href="#/tag/%23$2">#$2</a>')
    .replace(/(^|[\s(])\$([A-Za-z][A-Za-z0-9]{0,14})\b/g, '$1<a class="t" href="#/tag/%24$2">$$$2</a>');
}
const typeColor = t => ({ Trading: 'g', KOL: 'a', 'Alpha Community': 'g', Marketing: 'a', Project: 'g', Personal: '' }[t] || '');

// ---------------------------------------------------------------- shell
const NAV = [
  ['home', 'My Network', '#/', 'home'], ['networks', 'Networks', '#/networks', 'networks'], ['discover', 'Discover', '#/discover', 'discover'],
  ['opps', 'Opportunities', '#/opportunities', 'opps'], ['rank', 'Rankings', '#/rankings', 'rank'], ['msg', 'Messages', '#/messages', 'messages'],
  ['bell', 'Notifications', '#/notifications', 'notifications'], ['user', 'My Profile', '#/me', 'me'],
];
function shell() {
  const me = S.me;
  $('#app').innerHTML = `
  <div class="shell">
    <aside class="side">
      <a class="logo" href="#/"><img src="/static/img/logo.svg" alt="">NETWORK</a>
      <nav class="nav" id="nav">${NAV.map(([i, l, h, k]) => `<a href="${h}" data-k="${k}">${ic(i)}<span>${l}</span><span class="badge hidden" data-badge="${k}"></span></a>`).join('')}</nav>
      <div class="card" id="side-trending"><h3>${ic('fire')} Network Pulse</h3><div class="muted small">Loading…</div></div>
      <div class="tiny muted" style="padding:0 6px"><a href="#/about">About</a> · <a href="#/rankings">How rankings work</a> · <a href="#/rewards">Rewards</a></div>
    </aside>
    <div class="main">
      <header class="top">
        <a class="logo mobile-only" href="#/" style="padding:0;font-size:18px"><img src="/static/img/logo.svg" alt="" style="width:28px;height:28px">NETWORK</a>
        <form class="search desktop-only" id="searchform" role="search">${ic('search')}<input id="q" placeholder="Search people, networks, projects…" maxlength="60" autocomplete="off"></form>
        <span class="sp"></span>
        <a class="iconbtn mobile-only" href="#/discover" aria-label="Search">${ic('search')}</a>
        ${me ? `<button class="btn ghost desktop-only" data-act="create-menu">${ic('plus')}<span class="create-txt">Create</span></button>
        <a class="iconbtn desktop-only" href="#/networks" aria-label="Networks">${ic('people')}</a>
        <a class="iconbtn" href="#/messages" aria-label="Messages">${ic('msg')}<span class="dot hidden" data-badge="messages"></span></a>
        <a class="iconbtn desktop-only" href="#/notifications" aria-label="Notifications">${ic('bell')}<span class="dot hidden" data-badge="notifications"></span></a>
        <div class="menu"><button class="iconbtn" data-act="usermenu" aria-label="Account">${avatar(me, 'sm')}</button></div>`
        : `<a class="btn" href="#/login">Log in</a><a class="btn primary" href="#/signup">Join</a>`}
      </header>
      <div class="content" id="content"><div class="col" id="center"></div><div class="col right" id="right"></div></div>
    </div>
  </div>
  <nav class="bottom">
    <a href="#/" data-k="home">${ic('home')}Home</a>
    <a href="#/networks" data-k="networks">${ic('networks')}Networks</a>
    <a href="${me ? '#/compose' : '#/login'}" class="plus" aria-label="Create">${ic('plus')}</a>
    <a href="#/opportunities" data-k="opps">${ic('opps')}Opps</a>
    <a href="${me ? '#/notifications' : '#/login'}" data-k="notifications">${ic('bell')}Alerts<span class="dot hidden" data-badge="notifications"></span></a>
    <a href="${me ? '#/me' : '#/login'}" data-k="me">${ic('user')}Me</a>
  </nav>`;
  $('#searchform')?.addEventListener('submit', e => { e.preventDefault(); const q = $('#q').value.trim(); if (q.length >= 2) location.hash = '#/search/' + encodeURIComponent(q); });
  sideTrending(); badges();
}
function sidePassport() {
  const el = $('#side-passport'); if (!el) return;
  const me = S.me;
  el.innerHTML = me ? `<a class="card pp" href="#/passport/${esc(me.username)}" style="display:block">
      <div class="row">${avatar(me)}<div class="grow"><div class="row" style="gap:6px"><b>Network Passport</b>${me.identity_verified ? vbadge() : ''}</div>
      <div class="tiny muted">${esc(me.display_name)} · ${me.identity_verified ? 'Identity verified' : 'Identity not verified'}</div></div></div>
      <div class="row between small" style="margin-top:10px"><span>Level ${me.level}</span><span class="muted">${kfmt(me.xp)} XP →</span></div>
      <div class="bar"><i style="width:${Math.round(Math.min(1, me.level_progress) * 100)}%"></i></div></a>`
    : `<div class="card pp"><b>Network Passport</b><p class="small muted">Your credibility page: networks, endorsements, contributions.</p><a class="btn primary sm block" href="#/signup">Create your Passport</a></div>`;
}
async function sideTrending() {
  try {
    const t = await api('/trending');
    $('#side-trending').innerHTML = `<h3>${ic('fire', 'amber')} Network Pulse <a class="more" href="#/discover">View all →</a></h3>` +
      (t.length ? t.slice(0, 6).map(x => `<a class="row between small" style="padding:5px 0" href="#/tag/${encodeURIComponent(x.tag)}"><b>${esc(x.tag)}</b><span class="muted">${x.posts} posts <span class="green">↑</span></span></a>`).join('') : '<div class="muted small">No topics yet</div>');
  } catch {}
}
function badges() {
  const me = S.me;
  const set = (k, n) => document.querySelectorAll(`[data-badge="${k}"]`).forEach(b => { b.textContent = n > 99 ? '99+' : n; b.classList.toggle('hidden', !n); });
  set('opps', S.openOpps || 0);
  if (!me) return;
  set('notifications', me.unread_notifications); set('messages', me.unread_messages);
}
function setActive(k) { document.querySelectorAll('[data-k]').forEach(a => a.classList.toggle('on', a.dataset.k === k)); }
function layout(wide) { $('#content').classList.toggle('wide', !!wide); $('#right').classList.toggle('hidden', !!wide); }

async function rightCol() {
  const el = $('#right'); if (!el || el.classList.contains('hidden')) return;
  el.innerHTML = `<div class="card" id="r-nets"></div><div class="card" id="r-opps"></div><div class="card" id="r-rank"></div><div id="side-passport"></div>
    <div class="card build"><b>Build Your Network.<br>Build Your Net Worth.</b><a class="btn primary sm" href="${S.me ? '#/create-network' : '#/signup'}">Create a Network →</a></div>`;
  sidePassport();
  const [all, opps, rank] = await Promise.all([api('/networks').catch(() => []), api('/opportunities').catch(() => []), api('/rankings').catch(() => null)]);
  const list = all.filter(n => n.my_role).concat(all.filter(n => !n.my_role)).slice(0, 4);
  if (!$('#r-nets')) return;
  $('#r-nets').innerHTML = `<h3>Your Networks <a class="more" href="#/networks">View all →</a></h3>` + (list.map(n => `
    <div class="li">${netAv(n)}<a class="grow" href="#/n/${esc(n.slug)}"><div class="ell"><b>${esc(n.name)}</b>${n.my_role ? ' <span class="green">●</span>' : ''}</div><div class="tiny muted">${kfmt(n.members)} members · ${esc(n.type)}</div></a>
    ${n.my_role ? '<span class="btn sm" style="cursor:default">Joined</span>' : n.my_status === 'pending' ? '<span class="btn sm" style="cursor:default">Requested</span>' : `<button class="btn ghost sm" data-act="join" data-slug="${esc(n.slug)}">Join</button>`}</div>`).join('') || '<div class="muted small">No networks yet.</div>');
  S.openOpps = opps.length; badges();
  $('#r-opps').innerHTML = `<h3>${ic('bag', 'green')} Top Opportunities <a class="more" href="#/opportunities">View all →</a></h3>` + (opps.slice(0, 3).map((o, i) => `
    <div class="li" style="align-items:flex-start"><span class="num">${i + 1}</span><a class="grow" href="#/opportunities/${o.id}"><b class="small">${esc(o.title)}</b>${demo(o)}<div class="tiny green">${esc(o.network ? o.network.name : '@' + o.creator.username)}</div><div class="tiny muted">${esc(o.category)} · ${ago(o.created_at)} · ${o.applicants} responses</div></a>
    ${o.is_mine ? '' : o.my_application ? '<span class="pill g">Applied</span>' : `<a class="btn primary sm" href="#/opportunities/${o.id}">Apply</a>`}</div>`).join('') || '<div class="muted small">No open opportunities.</div>');
  $('#r-rank').innerHTML = `<h3>${ic('trophy', 'amber')} Network Rankings <a class="more" href="#/rankings">View all →</a></h3>` + (rank ? rank.networks.filter(r => r.rank).slice(0, 5).map(r => `
    <a class="li" href="#/n/${esc(r.slug)}"><span class="num">${r.rank}</span>${netAv(r, 'sm')}<span class="grow ell small"><b>${esc(r.name)}</b></span><span class="score">${r.score.toFixed(1)}</span></a>`).join('') : '') + `<div class="tiny muted" style="margin-top:8px">Scores come from retention, engagement, growth, collaboration, reliability and verified performance. <a class="green" href="#/rankings">How it works</a></div>`;
}

// ---------------------------------------------------------------- posts
function callCard(c) {
  if (!c) return '';
  const cm = c.current_multiple, col = cm == null ? '' : cm >= 1 ? 'green' : 'red';
  return `<div class="callcard">
    <div class="row between wrap"><div class="row"><b>$${esc(c.symbol)}</b><span class="muted tiny ell" style="max-width:160px">${esc(c.name)}</span>${demo(c)}</div>
    ${c.rugged ? '<span class="pill r">⚠ Rug flagged: liquidity collapsed</span>' : c.independently_tracked ? `<span class="pill g" title="Our server checked prices against DexScreener ${c.checks} time(s). The caller didn't report them.">✓ Tracked call (DexScreener price at post time)</span>` : '<span class="pill a" title="Waiting for the first independent DexScreener check">Tracked call (DexScreener price at post time) · awaiting first check</span>'}</div>
    <div class="grid4"><div><div class="k">Entry</div><div class="v">${usd(c.entry_price)}</div><div class="tiny muted">MC ${usd(c.entry_mcap)}</div></div>
    <div><div class="k">Now</div><div class="mult ${col}">${mx(cm)}</div><div class="tiny muted">MC ${usd(c.current_mcap)}</div></div>
    <div><div class="k">Peak</div><div class="mult green">${mx(c.peak_multiple)}</div></div>
    <div><div class="k">1h / 24h / 7d</div><div class="v small">${mx(c.result_1h)} / ${mx(c.result_24h)} / ${mx(c.result_7d)}</div></div></div>
    <div class="tiny muted" style="margin-top:8px">CA <span style="font-family:monospace">${esc(c.token_address.slice(0, 6))}…${esc(c.token_address.slice(-6))}</span> · Liquidity ${usd(c.current_liquidity)} · Source: DexScreener${c.last_checked ? ' · checked ' + ago(c.last_checked) + ' ago' : ''} · <a class="green" href="https://dexscreener.com/solana/${esc(c.token_address)}" target="_blank" rel="noopener">Chart ↗</a></div></div>`;
}
function postInner(p) {
  return `<div class="hd"><a href="#/u/${esc(p.author.username)}">${avatar(p.author)}</a>
    <div class="grow"><div class="row" style="gap:6px;flex-wrap:wrap"><a class="name" href="#/u/${esc(p.author.username)}">${esc(p.author.display_name)}</a>${p.author.identity_verified ? vbadge() : ''}<span class="muted small">@${esc(p.author.username)} · ${ago(p.created_at)}</span>${demo(p)}</div>
    ${p.network ? `<div class="tiny"><a class="green" href="#/n/${esc(p.network.slug)}">${esc(p.network.name)}</a>${p.from_connection ? ' <span class="muted">· from a connected network</span>' : ''}${p.kind !== 'post' ? ` <span class="pill g" style="padding:1px 7px">${p.kind === 'announcement' ? '📣 Announcement' : 'Update'}</span>` : ''}${p.share_with_connections ? ' <span class="muted">· shared with connections</span>' : ''}</div>` : ''}</div>
    <div class="menu"><button class="act" data-act="postmenu" data-id="${p.id}" data-author="${esc(p.author.username)}" aria-label="More">${ic('dots')}</button></div></div>
    ${p.body ? `<div class="body">${rich(p.body)}</div>` : ''}
    ${p.image_url ? `<div class="media"><img src="${esc(p.image_url)}" alt="" loading="lazy"></div>` : ''}
    ${callCard(p.call)}`;
}
function actsHTML(p) {
  return `<div class="acts">
    <a class="act" href="#/post/${p.id}" title="Comment">${ic('reply')} ${kfmt(p.replies)}</a>
    <button class="act ${p.renetworked ? 'on' : ''}" data-act="renet" data-id="${p.id}" title="Re-Network">${ic('renet')} ${kfmt(p.renetworks)}</button>
    <button class="act ${p.liked ? 'liked' : ''}" data-act="like" data-id="${p.id}" title="Endorse this Network Post">${ic('heart')} <span>${kfmt(p.likes)}</span></button>
    <button class="act" data-act="copy" data-id="${p.id}" title="Copy link">${ic('share')}</button></div>`;
}
function postHTML(p) {
  if (p.renetwork) {
    const o = p.renetwork;
    return `<article class="card post" data-post="${o.id}"><div class="ctx">${ic('renet')} <a href="#/u/${esc(p.author.username)}">${esc(p.author.display_name)}</a> Re-Networked</div>${postInner(o)}${actsHTML(o)}</article>`;
  }
  return `<article class="card post ${p.kind === 'announcement' ? 'ann' : ''}" data-post="${p.id}">${postInner(p)}${actsHTML(p)}</article>`;
}
const feedHTML = (posts, empty = 'Nothing here yet.') => posts.length ? posts.map(postHTML).join('') : `<div class="card empty">${empty}</div>`;

function composerHTML(opts = {}) {
  const me = S.me;
  if (!me) return `<div class="card row between"><span class="muted">Join NETWORK to post, connect and collaborate.</span><a class="btn primary" href="#/signup">Sign up</a></div>`;
  return `<form class="card" id="composer" data-network="${opts.networkId || ''}" data-parent="${opts.parentId || ''}">
    <div class="composer">${avatar(me)}<div class="grow"><textarea id="c-body" maxlength="2000" placeholder="${esc(opts.placeholder || "What's on your mind?")}" rows="2"></textarea>
    <div id="c-prev"></div><div class="err" id="c-err"></div>
    <div class="tools"><label class="tool" title="Upload a photo">${ic('photo', 'green')} Photo<input type="file" id="c-file" accept="image/png,image/jpeg,image/gif,image/webp" hidden></label>
    <button type="button" class="tool" data-act="img-url">${ic('photo')} Image link</button>
    ${opts.parentId ? '' : `<button type="button" class="tool" data-act="new-call" data-network="${opts.networkId || ''}">${ic('chart', 'green')} Token call</button><a class="tool" href="#/opportunities/new">${ic('bag', 'green')} Opportunity</a>`}
    ${opts.admin ? `<select class="in" id="c-kind" style="width:auto;padding:6px 8px"><option value="post">Post</option><option value="announcement">📣 Announcement</option><option value="update">Update</option></select>
       <label class="tool"><input type="checkbox" id="c-share"> Share with connected networks</label>` : ''}
    <span style="flex:1"></span><button class="btn primary" id="c-submit">${opts.parentId ? 'Reply' : 'Post'}</button></div></div></div></form>`;
}
function bindComposer(onDone) {
  const f = $('#composer'); if (!f) return;
  let img = '';
  const prev = () => { $('#c-prev').innerHTML = img ? `<div class="preview"><img src="${esc(img)}" alt=""><button type="button" class="btn sm" style="position:absolute;top:6px;right:6px" id="c-rm">✕</button></div>` : ''; $('#c-rm')?.addEventListener('click', () => { img = ''; prev(); }); };
  $('#c-file').addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    if (file.size > 3 * 1024 * 1024) return toast('Image too large (max 3 MB).', true);
    const fd = new FormData(); fd.append('file', file);
    try { img = (await api('/upload', { body: fd })).url; prev(); } catch (er) { fail(er); }
  });
  f.querySelector('[data-act="img-url"]').addEventListener('click', e => { e.stopPropagation(); const u = prompt('Paste an image URL (https://…)'); if (u) { if (!/^https?:\/\/\S+$/.test(u.trim())) return toast('Must be an http(s) link', true); img = u.trim(); prev(); } });
  f.addEventListener('submit', async e => {
    e.preventDefault();
    const body = $('#c-body').value.trim(); $('#c-err').textContent = '';
    if (!body && !img) { $('#c-err').textContent = 'Write something or add an image.'; return; }
    const b = $('#c-submit'); b.disabled = true;
    try {
      const p = await api('/posts', { body: { body, image_url: img, network_id: Number(f.dataset.network) || null, parent_id: Number(f.dataset.parent) || null, kind: $('#c-kind')?.value || 'post', share_with_connections: !!$('#c-share')?.checked } });
      $('#c-body').value = ''; img = ''; prev(); toast('Posted'); onDone && onDone(p);
    } catch (er) { $('#c-err').textContent = er.message; } finally { b.disabled = false; }
  });
}

// ---------------------------------------------------------------- modal + forms
function modal(html, onMount) {
  $('#modal-card').innerHTML = `<button class="iconbtn" style="position:absolute;top:10px;right:10px" data-act="close-modal" aria-label="Close">✕</button>${html}`;
  $('#modal').classList.remove('hidden'); onMount && onMount($('#modal-card'));
}
function closeModal() { $('#modal').classList.add('hidden'); $('#modal-card').innerHTML = ''; }
const fval = (f, n) => { const el = f.elements[n]; if (!el) return undefined; return el.type === 'checkbox' ? el.checked : el.value.trim(); };
async function submitForm(f, fn) {
  const err = f.querySelector('.err'); if (err) err.textContent = '';
  const b = f.querySelector('button[type=submit],button:not([type])'); if (b) b.disabled = true;
  try { await fn(); } catch (e) { if (err) err.textContent = e.message; else fail(e); } finally { if (b) b.disabled = false; }
}
const SHARE_LABELS = { share_announcements: 'Public announcements', share_selected: 'Selected Network Posts', share_opportunities: 'Partnership opportunities',
  share_events: 'Public events', share_activity: 'Selected activity updates', display_public: 'Show this connection publicly' };
const ADMIN_LABELS = { perm_members: 'Manage members, requests & invites', perm_announce: 'Post announcements, updates & events', perm_connections: 'Manage Network connections',
  perm_settings: 'Edit Network settings', perm_moderate: 'Remove posts (moderation)', perm_opportunities: 'Publish & manage opportunities' };
const permBoxes = (labels, cur = {}) => Object.entries(labels).map(([k, l]) => `<label class="row small" style="margin:6px 0"><input type="checkbox" name="${k}" ${cur[k] ? 'checked' : ''}> ${l}</label>`).join('');
const readBoxes = (f, labels) => Object.fromEntries(Object.keys(labels).map(k => [k, !!f.elements[k].checked]));

function callModal(networkId) {
  modal(`<h3>Post a token call</h3><p class="small muted">Entry price is read from DexScreener by the server at the moment you post. You can't edit it. Results are then tracked independently.</p>
  <form id="callf"><label class="f"><span>Solana token contract address</span><input class="in" name="ca" required maxlength="44" placeholder="e.g. DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"></label>
  <label class="f"><span>Thesis (optional)</span><textarea class="in" name="notes" maxlength="500" rows="3"></textarea></label>
  <div id="trend" class="chips small"></div><div class="err"></div><button class="btn primary block" type="submit">Post call</button></form>`, async card => {
    const f = $('#callf', card);
    api('/tokens/trending').then(t => { $('#trend', card).innerHTML = t.length ? '<span class="tiny muted">Trending on DexScreener:</span>' + t.map(x => `<button type="button" class="chip" data-ca="${esc(x.address)}">$${esc(x.symbol)}</button>`).join('') : ''; $('#trend', card).querySelectorAll('[data-ca]').forEach(b => b.onclick = () => f.elements.ca.value = b.dataset.ca); }).catch(() => {});
    f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
      const ca = fval(f, 'ca'); if (!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(ca)) throw new Error('Enter a valid Solana contract address.');
      await api('/calls', { body: { token_address: ca, notes: fval(f, 'notes'), network_id: Number(networkId) || null } });
      closeModal(); toast('Call posted with DexScreener entry price'); route();
    }); });
  });
}

// ---------------------------------------------------------------- delegated actions
document.addEventListener('click', async e => {
  const t = e.target.closest('[data-act]');
  if (!t) { document.querySelectorAll('.menu-list').forEach(m => m.remove()); return; }
  const a = t.dataset.act, id = t.dataset.id;
  const need = () => { if (!S.me) { location.hash = '#/login'; return false; } return true; };
  try {
    if (a === 'close-modal') return closeModal();
    if (a === 'usermenu' || a === 'create-menu' || a === 'postmenu') {
      e.stopPropagation(); document.querySelectorAll('.menu-list').forEach(m => m.remove());
      const items = a === 'usermenu' ? [['#/me', 'My Network Passport'], ['#/settings', 'Edit profile & privacy'], ['#/rewards', 'Rewards'], ['logout', 'Log out']]
        : a === 'create-menu' ? [['#/compose', 'Network Post'], ['call', 'Token call'], ['#/create-network', 'Create a Network'], ['#/opportunities/new', 'Opportunity']]
        : [['copy', 'Copy link'], ...(S.me && t.dataset.author === S.me.username ? [['edit', 'Edit'], ['delete', 'Delete']] : S.me ? [['report', 'Report'], ['delete', 'Remove (Network admin)'], ['block', `Block @${t.dataset.author}`]] : [])];
      const m = document.createElement('div'); m.className = 'menu-list';
      m.innerHTML = items.map(([k, l]) => `<button data-act="mi" data-k="${esc(k)}" data-id="${id || ''}" data-author="${esc(t.dataset.author || '')}">${esc(l)}</button>`).join('');
      t.parentElement.append(m); return;
    }
    if (a === 'mi') {
      const k = t.dataset.k; document.querySelectorAll('.menu-list').forEach(m => m.remove());
      if (k.startsWith('#')) { location.hash = k; return; }
      if (k === 'logout') { await api('/auth/logout', { body: {} }); S.me = null; if (S.ws) S.ws.close(); location.hash = '#/login'; boot(); return; }
      if (k === 'call') return callModal();
      if (k === 'copy') { await navigator.clipboard?.writeText(location.origin + '/#/post/' + id).catch(() => {}); return toast('Link copied'); }
      if (k === 'edit') {
        const p = (await api('/posts/' + id)).post;
        return modal(`<h3>Edit post</h3><form id="ef"><textarea class="in" name="body" rows="5" maxlength="2000">${esc(p.body)}</textarea><div class="err"></div><button class="btn primary" type="submit">Save</button></form>`, c => {
          const f = $('#ef', c); f.addEventListener('submit', ev => { ev.preventDefault(); submitForm(f, async () => { await api('/posts/' + id, { method: 'PUT', body: { body: fval(f, 'body') } }); closeModal(); toast('Post updated'); route(); }); }); });
      }
      if (k === 'delete') { if (!confirm('Remove this post?')) return; await api('/posts/' + id, { method: 'DELETE' }); toast('Post removed'); document.querySelectorAll(`[data-post="${id}"]`).forEach(x => x.remove()); return; }
      if (k === 'report') { const r = prompt('Why are you reporting this post? (3–300 characters)'); if (!r) return; await api(`/posts/${id}/report`, { body: { reason: r } }); return toast('Reported to the Network admins. Thanks.'); }
      if (k === 'block') { if (!confirm(`Block @${t.dataset.author}? You won't see each other's posts or messages.`)) return; await api(`/users/${t.dataset.author}/block`, { body: {} }); toast('Blocked'); return route(); }
    }
    if (a === 'like') { if (!need()) return; const r = await api(`/posts/${id}/like`, { body: {} }); t.classList.toggle('liked', r.liked); t.querySelector('span').textContent = kfmt(r.likes); return; }
    if (a === 'renet') { if (!need()) return; const r = await api(`/posts/${id}/renetwork`, { body: {} }); toast(r.renetworked ? 'Re-Networked to your Network' : 'Re-Network removed'); t.classList.toggle('on', r.renetworked); return; }
    if (a === 'copy') { await navigator.clipboard?.writeText(location.origin + '/#/post/' + id).catch(() => {}); return toast('Link copied'); }
    if (a === 'new-call') { if (!need()) return; return callModal(t.dataset.network); }
    if (a === 'join') { if (!need()) return; const r = await api(`/networks/${t.dataset.slug}/join`, { body: {} }); toast(r.status === 'active' ? 'Joined Network' : 'Request sent to the Network admins'); return route(); }
    if (a === 'leave') { if (!confirm('Leave this Network?')) return; await api(`/networks/${t.dataset.slug}/leave`, { body: {} }); toast('Left Network'); return route(); }
    if (a === 'follow') { if (!need()) return; const r = await api(`/users/${t.dataset.user}/follow`, { body: {} }); toast(r.following ? 'Added to your Connected list' : 'Removed'); return route(); }
    if (a === 'block-user') { const b = t.dataset.blocked === '1'; if (!b && !confirm('Block this user? They will not be able to message you.')) return; await api(`/users/${t.dataset.user}/block`, { body: {} }); toast(b ? 'Unblocked' : 'Blocked'); return route(); }
  } catch (er) { fail(er); }
});
$('#modal')?.addEventListener('click', e => { if (e.target.id === 'modal') closeModal(); });

// ---------------------------------------------------------------- realtime
function connectWS() {
  if (!S.me || (S.ws && S.ws.readyState <= 1)) return;
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  S.ws = ws;
  ws.onopen = () => { if (S.chatNet) ws.send(JSON.stringify({ type: 'join_network', slug: S.chatNet })); };
  ws.onmessage = ev => {
    let m; try { m = JSON.parse(ev.data); } catch { return; }
    if (m.type === 'notification') { S.me.unread_notifications++; badges(); if (!m.silent) toast(m.text); }
    else if (m.type === 'dm') {
      if (S.dmWith === m.from) { appendDM(m.message); api('/messages/' + m.from).catch(() => {}); }
      else { S.me.unread_messages++; badges(); toast('New message from @' + m.from); }
    } else if (m.type === 'chat' && S.chatNet) appendChat(m.message);
    else if (m.type === 'new_post' && S.route === 'home') { S.newPosts++; const nb = $('#newbar'); if (nb) { nb.classList.remove('hidden'); nb.textContent = `${S.newPosts} new Network Post${S.newPosts > 1 ? 's' : ''} · show`; } }
  };
  ws.onclose = () => { S.ws = null; if (S.me) setTimeout(connectWS, 4000); };
}

// ---------------------------------------------------------------- router
const ROUTES = [];
const on = (re, fn, opts = {}) => ROUTES.push({ re, fn, ...opts });
async function route() {
  const h = location.hash.replace(/^#/, '') || '/';
  if (S.ws && S.chatNet) { S.ws.readyState === 1 && S.ws.send(JSON.stringify({ type: 'leave_networks' })); }
  S.chatNet = null; S.dmWith = null; S.newPosts = 0; closeModal();
  for (const r of ROUTES) {
    const m = h.match(r.re);
    if (!m) continue;
    if (r.auth && !S.me) { location.hash = '#/login'; return; }
    if (r.bare) { $('#app').innerHTML = '<div id="center"></div>'; } else if (!$('.shell')) shell();
    if (!r.bare) { layout(r.wide); setActive(r.k || ''); }
    S.route = r.k || '';
    const c = $('#center'); c.innerHTML = '<div class="card empty">Loading…</div>';
    window.scrollTo(0, 0);
    try { await r.fn(c, ...m.slice(1).map(x => x == null ? undefined : decodeURIComponent(x))); } catch (e) { c.innerHTML = `<div class="card empty"><b>${esc(e.status === 404 ? 'Not found' : e.status === 403 ? 'No access' : 'Something went wrong')}</b><p class="muted">${esc(e.message)}</p><a class="btn" href="#/">Back to My Network</a></div>`; }
    if (!r.bare && !r.wide) rightCol().catch(() => {});
    return;
  }
  location.hash = '#/';
}
window.addEventListener('hashchange', route);

// ---------------------------------------------------------------- auth pages
function authPage(c, mode) {
  const signup = mode === 'signup';
  c.innerHTML = `<div class="auth"><a class="logo" href="#/" style="justify-content:center;margin-bottom:18px"><img src="/static/img/logo.svg" alt="">NETWORK</a>
  <div class="card"><h2 style="margin-top:0">${signup ? 'Create your Network Passport' : 'Welcome back'}</h2>
  <p class="muted small">Build Your Network. Build Your Net Worth.</p>
  <form id="af">${signup ? `<label class="f"><span>Username</span><input class="in" name="username" required minlength="3" maxlength="20" pattern="[A-Za-z0-9_]{3,20}" autocomplete="username"></label>
  <label class="f"><span>Display name</span><input class="in" name="display_name" maxlength="50"></label>
  <label class="f"><span>Email</span><input class="in" name="email" type="email" required maxlength="254" autocomplete="email"></label>`
  : `<label class="f"><span>Username or email</span><input class="in" name="login" required maxlength="254" autocomplete="username"></label>`}
  <label class="f"><span>Password</span><input class="in" name="password" type="password" required minlength="${signup ? 8 : 1}" maxlength="128" autocomplete="${signup ? 'new-password' : 'current-password'}"></label>
  ${signup ? '<p class="tiny muted">8+ characters with at least one letter and one number. NETWORK never asks for seed phrases or private keys.</p>' : ''}
  <div class="err"></div><button class="btn primary block" type="submit">${signup ? 'Create account' : 'Log in'}</button></form>
  <p class="small muted" style="text-align:center">${signup ? 'Already have an account? <a class="green" href="#/login">Log in</a>' : 'New here? <a class="green" href="#/signup">Create an account</a>'}</p>
  ${signup ? '' : '<p class="tiny muted" style="text-align:center">Local demo accounts: <b>alpha_annie</b> or <b>solsurfer</b>, password <b>demo1234</b> (DEMO data).</p>'}
  </div></div>`;
  const f = $('#af');
  f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    const body = signup ? { username: fval(f, 'username'), display_name: fval(f, 'display_name'), email: fval(f, 'email'), password: f.elements.password.value }
      : { login: fval(f, 'login'), password: f.elements.password.value };
    S.me = await api(signup ? '/auth/register' : '/auth/login', { body });
    shell(); connectWS(); location.hash = signup ? '#/welcome' : '#/'; if (!signup) route();
  }); });
}
on(/^\/login$/, c => authPage(c, 'login'), { bare: true });
on(/^\/signup$/, c => authPage(c, 'signup'), { bare: true });

// ---------------------------------------------------------------- home (My Network Feed)
function heroHTML() {
  return `<section class="hero"><h1>NETWORK</h1><h2>Build Your Network. Build Your Net Worth.</h2><p>Connect • Collaborate • Grow</p>
  <a class="btn primary" href="#/networks">Explore Networks →</a></section>`;
}
async function loadFeed(el, path, empty) {
  el.innerHTML = '<div class="card empty">Loading…</div>';
  const posts = await api(path);
  el.innerHTML = feedHTML(posts, empty);
  if (posts.length >= 30) {
    const more = document.createElement('button'); more.className = 'btn block'; more.textContent = 'Load more';
    more.onclick = async () => { more.disabled = true; const sep = path.includes('?') ? '&' : '?'; const older = await api(path + sep + 'before=' + posts[posts.length - 1].id).catch(fail) || [];
      more.remove(); el.insertAdjacentHTML('beforeend', feedHTML(older, 'No older posts.')); };
    el.append(more);
  }
}
function oppCard(o) {
  return `<a class="card" href="#/opportunities/${o.id}" style="display:block;border-color:rgba(34,240,138,.35)">
    <div class="tiny green">${ic('bag')} Opportunity for you · ${esc(o.category)}</div><b>${esc(o.title)}</b>${demo(o)}
    <div class="tiny muted">${esc(o.network ? o.network.name : '@' + o.creator.username)} · ${o.negotiable && !o.compensation ? 'Negotiable' : esc(o.compensation)}${o.deadline ? ' · apply by ' + new Date(o.deadline).toLocaleDateString() : ''}</div></a>`;
}
on(/^\/$/, async c => {
  const tab = sessionStorage.getItem('feedtab' + (S.me ? S.me.id : 0)) || (S.me ? 'network' : 'discover');
  const tabs = S.me ? [['network', 'My Network Feed'], ['announcements', 'Announcements'], ['following', 'Connected'], ['discover', 'Discover']] : [['discover', 'Discover']];
  c.innerHTML = heroHTML() + composerHTML() + `<div class="tabs" id="ftabs">${tabs.map(([k, l]) => `<button data-t="${k}" class="${k === tab ? 'on' : ''}">${l}</button>`).join('')}</div>
    <button class="btn primary sm newbar hidden" id="newbar"></button><div id="feed-opps"></div><div id="feed"></div>`;
  const load = t => { sessionStorage.setItem('feedtab' + (S.me ? S.me.id : 0), t); c.querySelectorAll('#ftabs button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
    return loadFeed($('#feed'), '/feed?tab=' + t, t === 'network' ? 'Your My Network Feed is empty. Join Networks or connect with people to fill it.' : 'Nothing here yet.'); };
  c.querySelectorAll('#ftabs button').forEach(b => b.onclick = () => load(b.dataset.t));
  $('#newbar').onclick = () => { $('#newbar').classList.add('hidden'); S.newPosts = 0; load(sessionStorage.getItem('feedtab') || 'network'); };
  bindComposer(() => load(sessionStorage.getItem('feedtab') || 'network'));
  await load(tabs.some(x => x[0] === tab) ? tab : tabs[0][0]);
  if (S.me) api('/opportunities/suggested').then(os => { if (os.length && $('#feed-opps')) $('#feed-opps').innerHTML = os.slice(0, 2).map(oppCard).join(''); }).catch(() => {});
}, { k: 'home' });

on(/^\/compose$/, c => { c.innerHTML = `<h2>New Network Post</h2>` + composerHTML(); bindComposer(p => location.hash = '#/post/' + p.id); }, { k: 'home', auth: true });

on(/^\/post\/(\d+)$/, async (c, id) => {
  const d = await api('/posts/' + id);
  c.innerHTML = `<a class="small muted" href="javascript:history.back()">← Back</a>` + postHTML(d.post) + composerHTML({ parentId: d.post.id, placeholder: 'Write a reply…' }) +
    `<h3 class="small muted">Replies</h3>` + feedHTML(d.replies, 'No replies yet.');
  bindComposer(() => route());
});

// ---------------------------------------------------------------- welcome / onboarding
on(/^\/welcome$/, async c => {
  const meta = S.meta;
  c.innerHTML = `<div class="card"><h2 style="margin-top:0">Welcome to NETWORK, ${esc(S.me.display_name)} 👋</h2><p class="muted">Tell us what you do so we can suggest Networks and Opportunities. You can change this later.</p>
  <form id="obf"><h3>I am a…</h3><div class="chips" id="roles">${meta.roles.map(r => `<label class="chip"><input type="radio" name="role" value="${esc(r)}" hidden ${S.me.role === r ? 'checked' : ''}>${esc(r)}</label>`).join('')}</div>
  <h3>Interested in</h3><div class="chips">${meta.network_types.concat(meta.opportunity_categories).map(i => `<label class="chip"><input type="checkbox" name="i" value="${esc(i)}" hidden ${(S.me.interests || []).includes(i) ? 'checked' : ''}>${esc(i)}</label>`).join('')}</div>
  <div class="err"></div><div class="row" style="margin-top:14px"><button class="btn primary" type="submit">Save & show suggestions</button><a class="btn ghost" href="#/">Skip</a></div></form></div><div id="sugg"></div>`;
  const f = $('#obf');
  const sync = () => f.querySelectorAll('label.chip').forEach(l => l.classList.toggle('on', l.querySelector('input').checked));
  f.addEventListener('change', sync); sync();
  const showSugg = async () => {
    const s = await api('/suggestions');
    $('#sugg').innerHTML = `<div class="card"><h3>Suggested Networks</h3>${s.networks.map(n => `<div class="li">${netAv(n)}<a class="grow" href="#/n/${esc(n.slug)}"><b>${esc(n.name)}</b>${demo(n)}<div class="tiny muted">${esc(n.type)} · ${n.members} members</div></a><button class="btn ghost sm" data-act="join" data-slug="${esc(n.slug)}">Join Network</button></div>`).join('') || '<p class="muted small">No matching public Networks yet.</p>'}</div>
      <div class="card"><h3>Open Opportunities for you</h3>${s.opportunities.map(o => `<div class="li"><a class="grow" href="#/opportunities/${o.id}"><b>${esc(o.title)}</b><div class="tiny muted">${esc(o.category)}</div></a></div>`).join('') || '<p class="muted small">No matching opportunities yet.</p>'}</div>`;
  };
  f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    const role = (f.querySelector('input[name=role]:checked') || {}).value || '';
    const interests = [...f.querySelectorAll('input[name=i]:checked')].map(x => x.value);
    S.me = await api('/me/onboarding', { method: 'PUT', body: { role, interests } }); toast('Saved'); await showSugg();
  }); });
  if (S.me.role) showSugg().catch(() => {});
}, { k: 'home', auth: true });

// ---------------------------------------------------------------- networks
const netCard = n => `<div class="card"><div class="row">${netAv(n)}<a class="grow" href="#/n/${esc(n.slug)}"><div class="row" style="gap:6px"><b class="ell">${esc(n.name)}</b>${n.is_private ? '<span class="pill">🔒 Private</span>' : ''}${demo(n)}</div>
  <div class="tiny muted">@${esc(n.slug)} · ${esc(n.type)} · ${kfmt(n.members)} Network Members</div></a>
  ${n.my_role ? `<span class="pill g">${esc(n.my_role === 'founder' ? 'Network Founder' : n.my_role === 'admin' ? 'Network Admin' : 'Joined')}</span>` : n.my_status === 'pending' ? '<span class="pill a">Requested</span>' : `<button class="btn ghost sm" data-act="join" data-slug="${esc(n.slug)}">${n.is_private ? 'Request to join' : 'Join Network'}</button>`}</div>
  <p class="small muted" style="margin:8px 0 0">${esc(n.description)}</p></div>`;
async function networksPage(c, discover) {
  const types = S.meta.network_types;
  c.innerHTML = `<div class="row between wrap"><h2>${discover ? 'Discover' : 'Networks'}</h2><a class="btn primary" href="#/create-network">${ic('plus')} Create a Network</a></div>
   <form class="search" id="nq" style="max-width:none;margin-bottom:10px">${ic('search')}<input name="q" placeholder="Search Networks, projects, people, opportunities" maxlength="60"></form>
   <div class="chips" id="nt"><button class="chip on" data-t="">All</button>${types.map(t => `<button class="chip" data-t="${esc(t)}">${esc(t === 'Alpha Communities' ? 'Alpha Communities' : t)}</button>`).join('')}${S.me && !discover ? '<button class="chip" data-t="mine">My Networks</button>' : ''}</div>
   <div id="nl" style="margin-top:12px;display:grid;gap:12px"></div>${discover ? '<h3>Network Pulse: recent Network Posts</h3><div id="dfeed"></div>' : ''}`;
  let type = '';
  const load = async () => { const q = $('#nq').elements.q.value.trim();
    const list = await api(`/networks?q=${encodeURIComponent(q)}&type=${type === 'mine' ? '' : encodeURIComponent(type)}&mine=${type === 'mine' ? 1 : 0}`);
    $('#nl').innerHTML = list.map(netCard).join('') || '<div class="card empty">No Networks match. <a class="green" href="#/create-network">Create one</a>.</div>'; };
  $('#nt').onclick = e => { const b = e.target.closest('[data-t]'); if (!b) return; type = b.dataset.t; $('#nt').querySelectorAll('.chip').forEach(x => x.classList.toggle('on', x === b)); load().catch(fail); };
  $('#nq').addEventListener('submit', e => { e.preventDefault(); const q = $('#nq').elements.q.value.trim(); if (discover && q.length >= 2) location.hash = '#/search/' + encodeURIComponent(q); else load().catch(fail); });
  await load();
  if (discover) loadFeed($('#dfeed'), '/feed?tab=discover').catch(fail);
}
on(/^\/networks$/, c => networksPage(c, false), { k: 'networks' });
on(/^\/discover$/, c => networksPage(c, true), { k: 'discover' });

function networkForm(n = {}) {
  const t = S.meta.network_types;
  return `<label class="f"><span>Network name</span><input class="in" name="name" required minlength="3" maxlength="60" value="${esc(n.name || '')}"></label>
  ${n.slug ? '' : '<label class="f"><span>Unique handle (URL)</span><input class="in" name="slug" maxlength="40" pattern="[a-z0-9-]{3,40}" placeholder="auto from name"></label>'}
  <label class="f"><span>Category</span><select class="in" name="type" ${n.slug ? 'disabled' : ''}>${t.map(x => `<option ${n.type === x ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select></label>
  <label class="f"><span>Description</span><textarea class="in" name="description" maxlength="1000" rows="3">${esc(n.description || '')}</textarea></label>
  <div class="row wrap"><label class="f grow"><span>Profile image</span><input type="file" accept="image/*" data-up="avatar_url"></label><label class="f grow"><span>Cover image</span><input type="file" accept="image/*" data-up="cover_url"></label></div>
  <input type="hidden" name="avatar_url" value="${esc(n.avatar_url || '')}"><input type="hidden" name="cover_url" value="${esc(n.cover_url || '')}">
  <label class="row small"><input type="checkbox" name="is_private" ${n.is_private ? 'checked' : ''}> Private Network (join by request or Network Invite; content members-only)</label>
  <label class="row small"><input type="checkbox" name="members_can_post" ${n.members_can_post === false ? '' : 'checked'}> Members can post (otherwise only founder/admins)</label>
  <label class="row small"><input type="checkbox" name="accept_connections" ${n.accept_connections === false ? '' : 'checked'}> Accept Network connection requests</label>`;
}
function bindUploads(f) {
  f.querySelectorAll('[data-up]').forEach(inp => inp.addEventListener('change', async () => {
    const file = inp.files[0]; if (!file) return; if (file.size > 3 * 1024 * 1024) return toast('Image too large (max 3 MB).', true);
    const fd = new FormData(); fd.append('file', file);
    try { f.elements[inp.dataset.up].value = (await api('/upload', { body: fd })).url; toast('Image uploaded'); } catch (e) { fail(e); }
  }));
}
on(/^\/create-network$/, c => {
  c.innerHTML = `<div class="card"><h2 style="margin-top:0">Create a Network</h2><p class="muted small">You'll be the Network Founder. Project Networks get a Launch Room; no token or wallet needed.</p><form id="cnf">${networkForm()}<div class="err"></div><button class="btn primary" type="submit" style="margin-top:12px">Create a Network</button></form></div>`;
  const f = $('#cnf'); bindUploads(f);
  f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    const n = await api('/networks', { body: { name: fval(f, 'name'), slug: fval(f, 'slug'), type: fval(f, 'type'), description: fval(f, 'description'), is_private: fval(f, 'is_private'), avatar_url: fval(f, 'avatar_url'), cover_url: fval(f, 'cover_url') } });
    if (!fval(f, 'members_can_post') || !fval(f, 'accept_connections')) await api('/networks/' + n.slug, { method: 'PUT', body: { members_can_post: fval(f, 'members_can_post'), accept_connections: fval(f, 'accept_connections') } });
    toast('Network created'); location.hash = '#/n/' + n.slug + (n.type === 'Project' ? '/launch' : '');
  }); });
}, { k: 'networks', auth: true });

// ---------------------------------------------------------------- network page
function countdown(at) {
  const d = new Date(at) - Date.now(); if (d <= 0) return '<span class="pill g">Launched / live</span>';
  const p = [Math.floor(d / 864e5), Math.floor(d / 36e5) % 24, Math.floor(d / 6e4) % 60];
  return `<div class="countdown">${p.map((v, i) => `<div><b>${v}</b><span class="tiny muted">${['days', 'hrs', 'min'][i]}</span></div>`).join('')}</div>`;
}
const verifLine = v => Object.values(v || {}).map(x => `<span class="pill ${x.verified ? 'g' : ''}" title="${esc(x.how)}">${x.verified ? '✓' : '○'} ${esc(x.label)}: ${x.verified ? (x.status === 'tracked' ? 'tracked (DexScreener price at post time)' : 'verified') : esc(x.status)}</span>`).join(' ');
on(/^\/n\/([a-z0-9-]+)(?:\/(\w+))?$/, async (c, slug, tab = 'feed') => {
  const n = await api('/networks/' + slug);
  const P_ = n.my_perms || {};
  const admin = n.my_role === 'founder' || n.my_role === 'admin';
  const member = !!n.my_role;
  const tabs = [['feed', 'Network Posts'], ['announcements', 'Announcements'], ['events', 'Events'],
    ...(member ? [['chat', 'Chat'], ['connected', 'From Connected Networks']] : []),
    ...(n.type === 'Project' ? [['launch', 'Launch Room']] : []), ['members', 'Network Members'], ['connections', 'Connected Networks'], ['reputation', 'Reputation'],
    ...(P_.perm_settings || P_.perm_members ? [['settings', 'Settings']] : [])];
  c.innerHTML = `<div class="nethead"><div class="cover">${n.cover_url ? `<img src="${esc(n.cover_url)}" alt="">` : ''}</div><div class="info">
    <div class="row between wrap" style="align-items:flex-end">${netAv(n, 'lg')}<div class="row wrap">
      ${member ? (n.my_role === 'founder' ? '<span class="pill g">Network Founder</span>' : `<span class="pill g">${n.my_role === 'admin' ? 'Network Admin' : 'Member'}</span><button class="btn sm" data-act="leave" data-slug="${esc(n.slug)}">Leave</button>`)
        : n.my_status === 'pending' ? '<span class="pill a">Request pending</span>' : S.me ? `<button class="btn primary sm" data-act="join" data-slug="${esc(n.slug)}">${n.is_private ? 'Request to join' : 'Join Network'}</button>` : '<a class="btn primary sm" href="#/login">Log in to join</a>'}
      ${P_.perm_connections ? '<button class="btn ghost sm" id="connreq">Connect Networks</button>' : ''}</div></div>
    <h2 style="margin:8px 0 0">${esc(n.name)} ${n.project_verified ? vbadge('Project verified') : ''}${demo(n)}</h2>
    <div class="small muted">@${esc(n.slug)} · ${esc(n.type)} · ${n.is_private ? '🔒 Private' : 'Public'} · Founded by <a class="green" href="#/u/${esc(n.founder.username)}">@${esc(n.founder.username)}</a> · ${new Date(n.created_at).toLocaleDateString()}</div>
    <p style="margin:8px 0">${rich(n.description)}</p>
    <div class="row wrap" style="gap:18px"><span class="stat"><b>${kfmt(n.members)}</b>Network Members</span><span class="stat"><b>${n.connections.filter(x => x.status === 'approved').length}</b>Connected Networks</span><span class="stat"><b>${n.reputation.eligible ? n.reputation.score.toFixed(1) : '—'}</b>Network score</span>${n.pending_requests ? `<a class="stat" href="#/n/${esc(n.slug)}/members"><b class="amber">${n.pending_requests}</b>Pending requests</a>` : ''}</div>
  </div><div class="tabs" style="padding:0 10px">${tabs.map(([k, l]) => `<a href="#/n/${esc(n.slug)}/${k}" class="${k === tab ? 'on' : ''}">${l}</a>`).join('')}</div></div><div id="ntab" style="margin-top:14px"></div>`;
  $('#connreq')?.addEventListener('click', () => connectModal(n));
  const el = $('#ntab');
  if (!n.can_view && !['members', 'connections', 'reputation', 'events'].includes(tab)) { el.innerHTML = `<div class="card empty">🔒 This is a private Network. ${n.my_status === 'pending' ? 'Your request is pending approval.' : 'Request to join or use a Network Invite to see its posts.'}</div>`; return; }
  if (tab === 'feed' || tab === 'announcements') {
    el.innerHTML = (member && tab === 'feed' && (n.members_can_post || admin) ? composerHTML({ networkId: n.id, admin: P_.perm_announce, placeholder: `Post to ${n.name}…` }) : '') + '<div id="nf"></div>';
    bindComposer(() => route());
    await loadFeed($('#nf'), `/networks/${n.slug}/feed${tab === 'announcements' ? '?kind=announcement' : ''}`, tab === 'announcements' ? 'No announcements yet.' : 'No Network Posts yet.');
  } else if (tab === 'connected') {
    el.innerHTML = '<p class="small muted">Only what connected Networks explicitly chose to share with this Network appears here.</p><div id="nf"></div>';
    await loadFeed($('#nf'), `/networks/${n.slug}/feed?kind=connected`, 'Connected Networks haven\'t shared anything with this Network yet.');
  } else if (tab === 'chat') {
    S.chatNet = n.slug;
    el.innerHTML = `<div class="card chat"><div class="msgs" id="msgs"></div><form id="chf" class="row" style="margin-top:8px"><input class="in" name="body" maxlength="1000" placeholder="Message ${esc(n.name)}…" required autocomplete="off"><button class="btn primary" type="submit">Send</button></form></div>`;
    const hist = await api(`/networks/${n.slug}/chat`); hist.forEach(appendChat);
    if (S.ws && S.ws.readyState === 1) S.ws.send(JSON.stringify({ type: 'join_network', slug: n.slug })); else connectWS();
    const f = $('#chf'); f.addEventListener('submit', e => { e.preventDefault(); const body = fval(f, 'body'); if (!body) return; f.elements.body.value = '';
      api(`/networks/${n.slug}/chat`, { body: { body } }).then(m => { if (!document.querySelector(`[data-cm="${m.id}"]`)) appendChat(m); }).catch(fail); });
  } else if (tab === 'events') await eventsTab(el, n, P_);
  else if (tab === 'launch') launchTab(el, n, P_);
  else if (tab === 'members') await membersTab(el, n, P_);
  else if (tab === 'connections') connectionsTab(el, n, P_);
  else if (tab === 'reputation') repTab(el, n.reputation, n.verification);
  else if (tab === 'settings') await settingsTab(el, n, P_);
}, { k: 'networks' });

function appendChat(m) {
  const box = $('#msgs'); if (!box || document.querySelector(`[data-cm="${m.id}"]`)) return;
  const mine = S.me && m.user.id === S.me.id;
  box.insertAdjacentHTML('beforeend', `<div class="bubble ${mine ? 'mine' : ''}" data-cm="${m.id}"><div class="tiny muted"><a href="#/u/${esc(m.user.username)}">@${esc(m.user.username)}</a> · ${ago(m.created_at)}</div>${rich(m.body)}</div>`);
  box.scrollTop = box.scrollHeight;
}

async function eventsTab(el, n, P_) {
  const evs = await api(`/networks/${n.slug}/events`);
  el.innerHTML = (P_.perm_announce ? `<form class="card" id="evf"><h3 style="margin-top:0">New event</h3><div class="row wrap"><input class="in grow" name="title" required minlength="3" maxlength="120" placeholder="AMA with the team"><input class="in" type="datetime-local" name="starts_at" required style="width:auto"></div>
    <input class="in" name="link" maxlength="300" placeholder="Link (https://…, optional)" style="margin-top:8px"><textarea class="in" name="description" maxlength="1000" rows="2" placeholder="Details" style="margin-top:8px"></textarea>
    <label class="row small"><input type="checkbox" name="is_public" checked> Public event (can be shared with connected Networks that you allow)</label><div class="err"></div><button class="btn primary sm" type="submit">Create event</button></form>` : '') +
    (evs.map(e => `<div class="card"><div class="row between"><b>${esc(e.title)}</b>${demo(e)}<span class="pill ${e.is_public ? 'g' : ''}">${e.is_public ? 'Public' : 'Members only'}</span></div><div class="small green">${new Date(e.starts_at).toLocaleString()}</div><p class="small">${rich(e.description)}</p>${e.link ? `<a class="green small" href="${esc(e.link)}" target="_blank" rel="noopener nofollow">${esc(e.link)}</a>` : ''}${P_.perm_announce ? `<button class="btn danger sm" style="float:right" data-del-ev="${e.id}">Delete</button>` : ''}</div>`).join('') || '<div class="card empty">No upcoming events.</div>');
  el.querySelectorAll('[data-del-ev]').forEach(b => b.onclick = async () => { if (!confirm('Delete event?')) return; await api('/events/' + b.dataset.delEv, { method: 'DELETE' }).catch(fail); route(); });
  const f = $('#evf'); f && f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    await api(`/networks/${n.slug}/events`, { body: { title: fval(f, 'title'), starts_at: new Date(fval(f, 'starts_at')).toISOString(), link: fval(f, 'link'), description: fval(f, 'description'), is_public: fval(f, 'is_public') } }); toast('Event created'); route(); }); });
}

function launchTab(el, n, P_) {
  const st = S.meta.project_stages, cur = st.indexOf(n.stage);
  el.innerHTML = `<div class="card"><h3 style="margin-top:0">Project journey</h3><div class="journey">${st.map((s, i) => `<span class="st ${i < cur ? 'done' : i === cur ? 'cur' : ''}">${esc(s.toUpperCase())}</span>${i < st.length - 1 ? '<span class="muted">→</span>' : ''}`).join('')}</div>
    <p class="tiny muted">No token launch or wallet is required to run a Project Network.</p></div>
    <div class="card"><h3 style="margin-top:0">Launch countdown</h3>${n.launch_at ? countdown(n.launch_at) + `<div class="tiny muted" style="margin-top:6px">${new Date(n.launch_at).toLocaleString()}</div>` : '<p class="muted small">No launch date set.</p>'}
    ${n.token_address ? `<p class="small">Token: <span style="font-family:monospace">${esc(n.token_address)}</span> · <a class="green" href="https://dexscreener.com/solana/${esc(n.token_address)}" target="_blank" rel="noopener">DexScreener ↗</a></p>` : ''}
    <div class="small">${verifLine(n.verification)}</div></div>
    <div class="card"><h3 style="margin-top:0">Team</h3><div class="small" style="white-space:pre-wrap">${rich(n.team_info) || '<span class="muted">Not added yet.</span>'}</div></div>
    <div class="card"><h3 style="margin-top:0">Roadmap</h3><div class="small" style="white-space:pre-wrap">${rich(n.roadmap) || '<span class="muted">Not added yet.</span>'}</div></div>
    <div class="row wrap"><a class="btn" href="#/n/${esc(n.slug)}/announcements">Project updates</a><a class="btn" href="#/opportunities?network=${esc(n.slug)}">Partnership & marketing opportunities</a>${P_.perm_opportunities ? '<a class="btn ghost" href="#/opportunities/new">Post an opportunity</a>' : ''}<a class="btn" href="#/n/${esc(n.slug)}/connections">Connected Networks</a></div>
    ${P_.perm_settings ? `<form class="card" id="lrf" style="margin-top:14px"><h3 style="margin-top:0">Edit Launch Room</h3>
      <label class="f"><span>Stage</span><select class="in" name="stage">${st.map(s => `<option ${s === n.stage ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select></label>
      <label class="f"><span>Launch date (optional)</span><input class="in" type="datetime-local" name="launch_at" value="${n.launch_at ? new Date(new Date(n.launch_at) - new Date().getTimezoneOffset() * 6e4).toISOString().slice(0, 16) : ''}"></label>
      <label class="f"><span>Team</span><textarea class="in" name="team_info" rows="3" maxlength="3000">${esc(n.team_info)}</textarea></label>
      <label class="f"><span>Roadmap</span><textarea class="in" name="roadmap" rows="4" maxlength="3000">${esc(n.roadmap)}</textarea></label>
      <label class="f"><span>Token contract (optional)</span><input class="in" name="token_address" maxlength="64" value="${esc(n.token_address)}"></label>
      <div class="err"></div><button class="btn primary" type="submit">Save Launch Room</button>
      ${n.my_role === 'founder' && !n.project_verified ? ' <button class="btn ghost" type="button" id="pverify">Request project verification</button>' : ''}</form>` : ''}`;
  const f = $('#lrf');
  f && f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    const la = fval(f, 'launch_at');
    await api('/networks/' + n.slug, { method: 'PUT', body: { stage: fval(f, 'stage'), launch_at: la ? new Date(la).toISOString() : null, team_info: fval(f, 'team_info'), roadmap: fval(f, 'roadmap'), token_address: fval(f, 'token_address') } });
    toast('Launch Room saved'); route(); }); });
  $('#pverify')?.addEventListener('click', async () => { try { const r = await api('/verifications', { body: { kind: 'project', network_slug: n.slug } }); toast('Request recorded: ' + r.detail); route(); } catch (e) { fail(e); } });
}

async function membersTab(el, n, P_) {
  let list; try { list = await api(`/networks/${n.slug}/members`); } catch (e) { el.innerHTML = `<div class="card empty">${esc(e.message)}</div>`; return; }
  const founder = n.my_role === 'founder';
  const pending = list.filter(m => m.status === 'pending');
  const row = m => `<div class="li">${avatar(m)}<a class="grow" href="#/u/${esc(m.username)}"><b>${esc(m.display_name)}</b>${demo(m)}<div class="tiny muted">@${esc(m.username)} · ${m.role === 'founder' ? 'Network Founder' : m.role === 'admin' ? 'Network Admin' : 'Member'}${m.joined_at ? ' · joined ' + ago(m.joined_at) : ''}</div></a>
    ${m.status === 'pending' && P_.perm_members ? `<button class="btn primary sm" data-ma="approve" data-uid="${m.id}">Approve</button><button class="btn danger sm" data-ma="reject" data-uid="${m.id}">Reject</button>` : ''}
    ${m.status === 'active' && m.role !== 'founder' && S.me && m.id !== S.me.id ? `${founder ? `<button class="btn sm" data-ma="${m.role === 'admin' ? 'make_member' : 'make_admin'}" data-uid="${m.id}">${m.role === 'admin' ? 'Remove admin' : 'Make admin'}</button>${m.role === 'admin' ? `<button class="btn sm" data-perm="${m.id}">Permissions</button>` : ''}` : ''}${P_.perm_members && (m.role !== 'admin' || founder) ? `<button class="btn danger sm" data-ma="remove" data-uid="${m.id}">Remove</button>` : ''}` : ''}</div>`;
  el.innerHTML = (pending.length ? `<div class="card"><h3 style="margin-top:0">Membership requests (${pending.length})</h3>${pending.map(row).join('')}</div>` : '') +
    (P_.perm_members ? `<div class="card"><h3 style="margin-top:0">Network Invite</h3><form id="invf" class="row wrap"><input class="in grow" name="username" maxlength="20" placeholder="@username (optional, for a personal invite)"><input class="in" type="number" name="max_uses" min="1" max="500" value="25" style="width:90px" title="Max uses"><input class="in" type="number" name="days" min="1" max="60" value="7" style="width:80px" title="Days valid"><button class="btn primary sm" type="submit">Create invite</button><div class="err" style="width:100%"></div></form><div id="invl"></div></div>` : '') +
    `<div class="card"><h3 style="margin-top:0">Network Members (${list.length - pending.length})</h3>${list.filter(m => m.status === 'active').map(row).join('')}</div>`;
  el.querySelectorAll('[data-ma]').forEach(b => b.onclick = async () => { if (b.dataset.ma === 'remove' && !confirm('Remove this member?')) return; try { await api(`/networks/${n.slug}/members/${b.dataset.uid}`, { body: { action: b.dataset.ma } }); toast('Done'); route(); } catch (e) { fail(e); } });
  el.querySelectorAll('[data-perm]').forEach(b => b.onclick = () => { const m = list.find(x => x.id == b.dataset.perm);
    modal(`<h3>Admin permissions: @${esc(m.username)}</h3><form id="pf">${permBoxes(ADMIN_LABELS, m.perms || {})}<div class="err"></div><button class="btn primary" type="submit">Save</button></form>`, c2 => {
      const f = $('#pf', c2); f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => { await api(`/networks/${n.slug}/members/${m.id}/perms`, { method: 'PUT', body: readBoxes(f, ADMIN_LABELS) }); closeModal(); toast('Permissions saved'); route(); }); }); }); });
  const f = $('#invf');
  if (f) {
    const loadInv = async () => { const inv = await api(`/networks/${n.slug}/invites`); $('#invl').innerHTML = inv.filter(i => !i.revoked).map(i => `<div class="li small"><code class="grow ell">${esc(location.origin + '/#/invite/' + i.code)}</code><span class="muted">${i.uses}/${i.max_uses} used${i.invitee ? ' · for @' + esc(i.invitee.username) : ''} · expires ${new Date(i.expires_at).toLocaleDateString()}</span><button class="btn sm" data-copy="${esc(i.code)}">Copy</button><button class="btn danger sm" data-rev="${i.id}">Revoke</button></div>`).join('');
      $('#invl').querySelectorAll('[data-copy]').forEach(b => b.onclick = () => { navigator.clipboard?.writeText(location.origin + '/#/invite/' + b.dataset.copy).catch(() => {}); toast('Invite link copied'); });
      $('#invl').querySelectorAll('[data-rev]').forEach(b => b.onclick = async () => { await api('/invites/' + b.dataset.rev, { method: 'DELETE' }).catch(fail); loadInv(); }); };
    loadInv().catch(() => {});
    f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => { await api(`/networks/${n.slug}/invites`, { body: { username: fval(f, 'username'), max_uses: Number(fval(f, 'max_uses')), days: Number(fval(f, 'days')) } }); toast('Network Invite created'); f.elements.username.value = ''; loadInv(); }); });
  }
}

const shareList = s => s ? Object.entries(SHARE_LABELS).filter(([k]) => s[k]).map(([, l]) => l).join(', ') || 'Nothing shared' : '';
function connectionsTab(el, n, P_) {
  const cs = n.connections;
  const item = x => `<div class="li" style="align-items:flex-start">${netAv(x.network)}<div class="grow"><a href="#/n/${esc(x.network.slug)}"><b>${esc(x.network.name)}</b></a> <span class="pill ${x.status === 'approved' ? 'g' : 'a'}">${x.status === 'approved' ? 'Connected' : x.incoming ? 'Incoming request' : 'Request sent'}</span>
    ${x.message ? `<div class="small">“${esc(x.message)}”</div>` : ''}${x.we_share ? `<div class="tiny muted">We share: ${esc(shareList(x.we_share))}</div>` : ''}${x.they_share ? `<div class="tiny muted">They share with us: ${esc(shareList(x.they_share))}</div>` : ''}</div>
    ${P_.perm_connections ? (x.status === 'pending' && x.incoming ? `<button class="btn primary sm" data-cd="${x.id}">Review</button>` : `${x.status === 'approved' ? `<button class="btn sm" data-cp="${x.id}">Sharing</button>` : ''}<button class="btn danger sm" data-cx="${x.id}">${x.status === 'approved' ? 'Disconnect' : 'Cancel'}</button>`) : ''}</div>`;
  el.innerHTML = `<div class="card"><h3 style="margin-top:0">Connected Networks</h3><p class="tiny muted">Connecting never exposes private content. Each Network chooses exactly what it shares, and the server enforces it.</p>${cs.map(item).join('') || '<p class="muted small">No connections yet.</p>'}${P_.perm_connections ? '<button class="btn ghost sm" id="cn2">Connect with another Network</button>' : ''}</div>`;
  $('#cn2')?.addEventListener('click', () => connectModal(n));
  el.querySelectorAll('[data-cd]').forEach(b => b.onclick = () => { const x = cs.find(c => c.id == b.dataset.cd);
    modal(`<h3>${esc(x.network.name)} wants to connect</h3>${x.message ? `<p>“${esc(x.message)}”</p>` : ''}<p class="small muted">They share with you: ${esc(shareList(x.they_share))}</p><form id="df"><b class="small">What ${esc(n.name)} shares with them:</b>${permBoxes(SHARE_LABELS)}<div class="err"></div><div class="row"><button class="btn primary" type="submit">Approve</button><button class="btn danger" type="button" id="rej">Reject</button></div></form>`, c2 => {
      const f = $('#df', c2);
      f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => { await api(`/connections/${x.id}/decide`, { body: { action: 'approve', permissions: readBoxes(f, SHARE_LABELS) } }); closeModal(); toast('Networks connected'); route(); }); });
      $('#rej', c2).onclick = async () => { try { await api(`/connections/${x.id}/decide`, { body: { action: 'reject' } }); closeModal(); toast('Request rejected'); route(); } catch (e) { fail(e); } }; }); });
  el.querySelectorAll('[data-cp]').forEach(b => b.onclick = () => { const x = cs.find(c => c.id == b.dataset.cp);
    modal(`<h3>What ${esc(n.name)} shares with ${esc(x.network.name)}</h3><form id="spf">${permBoxes(SHARE_LABELS, x.we_share)}<div class="err"></div><button class="btn primary" type="submit">Save sharing permissions</button></form>`, c2 => {
      const f = $('#spf', c2); f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => { await api(`/connections/${x.id}/permissions`, { method: 'PUT', body: readBoxes(f, SHARE_LABELS) }); closeModal(); toast('Sharing updated'); route(); }); }); }); });
  el.querySelectorAll('[data-cx]').forEach(b => b.onclick = async () => { if (!confirm('Remove this connection?')) return; try { await api('/connections/' + b.dataset.cx, { method: 'DELETE' }); toast('Removed'); route(); } catch (e) { fail(e); } });
}
function connectModal(n) {
  modal(`<h3>Connect ${esc(n.name)} with another Network</h3><form id="crf"><label class="f"><span>Network handle</span><input class="in" name="target" required maxlength="40" placeholder="e.g. sol-alpha" list="netlist"><datalist id="netlist"></datalist></label>
    <label class="f"><span>Message</span><textarea class="in" name="message" maxlength="500" rows="2"></textarea></label><b class="small">What ${esc(n.name)} will share with them:</b>${permBoxes(SHARE_LABELS)}<div class="err"></div><button class="btn primary" type="submit">Send connection request</button></form>`, c2 => {
    api('/networks').then(l => $('#netlist', c2).innerHTML = l.filter(x => x.slug !== n.slug).map(x => `<option value="${esc(x.slug)}">${esc(x.name)}</option>`).join('')).catch(() => {});
    const f = $('#crf', c2); f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => { await api(`/networks/${n.slug}/connections`, { body: { target_slug: fval(f, 'target'), message: fval(f, 'message'), permissions: readBoxes(f, SHARE_LABELS) } }); closeModal(); toast('Connection request sent'); location.hash = `#/n/${n.slug}/connections`; route(); }); }); });
}
function indicCard(title, v, detail, fmt = x => x) { return `<div class="card"><div class="tiny muted">${esc(title)}</div><div class="v">${v == null ? '—' : fmt(v)}</div><div class="tiny muted">${esc(typeof detail === 'string' ? detail : '')}</div></div>`; }
function repTab(el, r, verification) {
  const i = r.indicators, t = i.verified_trading_performance;
  el.innerHTML = `<div class="card"><div class="row between"><h3 style="margin:0">Network score</h3><span class="score" style="font-size:22px">${r.eligible ? r.score.toFixed(1) : 'Not ranked'}</span></div>${r.eligible ? '' : '<p class="small muted">Networks need at least 3 active members to be ranked.</p>'}
    ${Object.entries(r.score_parts).map(([k, v]) => `<div class="factor"><span>${esc(k.replace(/_/g, ' '))}</span><span class="muted">${v.toFixed(1)}</span></div>`).join('')}<a class="tiny green" href="#/rankings">How rankings work</a></div>
    <div class="indic">${indicCard('Member retention', i.member_retention.value, i.member_retention.detail, pct)}${indicCard('Organic growth (7d)', i.organic_growth.value, i.organic_growth.detail, pct)}
    ${indicCard('Engagement quality', i.engagement_quality.value, i.engagement_quality.detail, pct)}${indicCard('Collaboration history', i.collaboration_history.value, i.collaboration_history.detail)}
    ${indicCard('Reliability', i.reliability.value, i.reliability.detail, pct)}${indicCard('Trading performance', t.verified ? pct(t.win_rate) + ' win rate' : null, t.label)}</div>
    <div class="card small">${verifLine(verification)}</div>`;
}
async function settingsTab(el, n, P_) {
  el.innerHTML = (P_.perm_settings ? `<form class="card" id="nsf"><h3 style="margin-top:0">Network settings</h3>${networkForm(n)}<div class="err"></div><button class="btn primary" type="submit" style="margin-top:10px">Save settings</button></form>` : '<div class="card muted small">You can manage members and invites from the Network Members tab. Editing settings needs the founder to grant "Edit Network settings".</div>');
  const f = $('#nsf'); if (!f) return; bindUploads(f);
  f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    await api('/networks/' + n.slug, { method: 'PUT', body: { name: fval(f, 'name'), description: fval(f, 'description'), is_private: fval(f, 'is_private'), avatar_url: fval(f, 'avatar_url'), cover_url: fval(f, 'cover_url'), members_can_post: fval(f, 'members_can_post'), accept_connections: fval(f, 'accept_connections') } });
    toast('Settings saved'); route(); }); });
}
on(/^\/invite\/([\w-]+)$/, async (c, code) => {
  const i = await api('/invites/' + code);
  c.innerHTML = `<div class="card" style="text-align:center">${netAv(i.network, 'lg')}<h2>Network Invite: ${esc(i.network.name)}</h2><p class="muted">@${esc(i.inviter.username)} invited you · ${esc(i.network.type)} · ${i.network.members} Network Members${i.network.is_private ? ' · 🔒 Private' : ''}</p>
    ${i.expired ? '<p class="red">This invite has expired or been used up.</p>' : S.me ? '<button class="btn primary" id="acc">Accept & Join Network</button>' : `<a class="btn primary" href="#/signup">Sign up to join</a> <a class="btn" href="#/login">Log in</a>`}</div>`;
  $('#acc')?.addEventListener('click', async () => { try { await api(`/networks/${i.network.slug}/join?invite=${encodeURIComponent(code)}`, { body: {} }); toast('Joined via Network Invite'); location.hash = '#/n/' + i.network.slug; } catch (e) { fail(e); } });
});

// ---------------------------------------------------------------- opportunities
on(/^\/opportunities(?:\?(.*))?$/, async (c, qs = '') => {
  const params = new URLSearchParams(qs);
  const cats = S.meta.opportunity_categories;
  c.innerHTML = `<div class="row between wrap"><h2>Opportunities</h2>${S.me ? '<a class="btn primary" href="#/opportunities/new">' + ic('plus') + ' Post an opportunity</a>' : ''}</div>
  <form class="card" id="of"><div class="row wrap"><input class="in grow" name="q" maxlength="50" placeholder="Search opportunities" value="${esc(params.get('q') || '')}">
  <select class="in" name="category" style="width:auto"><option value="">All categories</option>${cats.map(x => `<option ${params.get('category') === x ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select>
  <select class="in" name="status" style="width:auto">${['open', 'filled', 'closed'].map(x => `<option ${params.get('status') === x ? 'selected' : ''}>${x}</option>`).join('')}</select>
  ${S.me ? `<label class="row small"><input type="checkbox" name="relevant" ${params.get('relevant') ? 'checked' : ''}> Relevant to my Networks</label><label class="row small"><input type="checkbox" name="mine" ${params.get('mine') ? 'checked' : ''}> Posted by me</label>` : ''}
  <button class="btn" type="submit">Filter</button></div>${params.get('network') ? `<div class="tiny muted" style="margin-top:6px">Network: @${esc(params.get('network'))} · <a class="green" href="#/opportunities">clear</a></div>` : ''}</form><div id="ol"></div>`;
  const f = $('#of');
  let offset = 0;
  const load = async (append) => {
    const p = new URLSearchParams({ q: fval(f, 'q'), category: fval(f, 'category'), status: fval(f, 'status'), offset, limit: 20 });
    if (params.get('network')) p.set('network', params.get('network'));
    if (S.me && fval(f, 'relevant')) p.set('relevant', 1); if (S.me && fval(f, 'mine')) p.set('mine', 1);
    const list = await api('/opportunities?' + p);
    const html = list.map(o => `<a class="card" href="#/opportunities/${o.id}" style="display:block"><div class="row between wrap"><span class="pill g">${esc(o.category)}</span><span class="pill ${o.status === 'open' ? 'g' : ''}">${esc(o.status)}</span></div>
      <h3 style="margin:8px 0 4px">${esc(o.title)}${demo(o)}</h3><div class="small muted">${o.network ? 'by ' + esc(o.network.name) : 'by @' + esc(o.creator.username)} · ${ago(o.created_at)} · ${o.applicants} applicants${o.deadline ? ' · deadline ' + new Date(o.deadline).toLocaleDateString() : ''}</div>
      <div class="small" style="margin-top:6px">${esc(o.compensation || '')}${o.negotiable ? ' (negotiable)' : ''}</div>${o.my_application ? `<span class="pill a">You responded · ${esc(o.my_application.status)}</span>` : ''}</a>`).join('');
    $('#ol').innerHTML = (append ? $('#ol').innerHTML.replace(/<button[^>]*id="omore"[\s\S]*$/, '') : '') + (html || (append ? '' : '<div class="card empty">No opportunities match.</div>')) + (list.length === 20 ? '<button class="btn block" id="omore">Load more</button>' : '');
    $('#omore')?.addEventListener('click', () => { offset += 20; load(true).catch(fail); });
  };
  f.addEventListener('submit', e => { e.preventDefault(); offset = 0; load().catch(fail); });
  await load();
}, { k: 'opps' });

on(/^\/opportunities\/new$/, async c => {
  const nets = (await api('/networks?mine=1')).filter(n => n.my_role === 'founder' || n.my_role === 'admin');
  c.innerHTML = `<div class="card"><h2 style="margin-top:0">Post an opportunity</h2><form id="nof">
   <label class="f"><span>Post as</span><select class="in" name="network_id"><option value="">Myself (@${esc(S.me.username)})</option>${nets.map(n => `<option value="${n.id}">${esc(n.name)} (Network)</option>`).join('')}</select></label>
   <label class="f"><span>Category</span><select class="in" name="category">${S.meta.opportunity_categories.map(x => `<option>${esc(x)}</option>`).join('')}</select></label>
   <label class="f"><span>Title</span><input class="in" name="title" required minlength="5" maxlength="120"></label>
   <label class="f"><span>Description</span><textarea class="in" name="description" required minlength="20" maxlength="3000" rows="5"></textarea></label>
   <label class="f"><span>Requirements</span><textarea class="in" name="requirements" maxlength="2000" rows="3" placeholder="Skills, experience, audience size…"></textarea></label>
   <div class="row wrap"><label class="f grow"><span>Compensation</span><input class="in" name="compensation" maxlength="120" placeholder="e.g. 5 SOL, $2k/month, rev share"></label><label class="row small"><input type="checkbox" name="negotiable"> Negotiable</label></div>
   <label class="f"><span>Application deadline (optional)</span><input class="in" type="date" name="deadline"></label>
   <div class="err"></div><button class="btn primary" type="submit">Publish</button></form></div>`;
  const f = $('#nof');
  f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    const dl = fval(f, 'deadline');
    const o = await api('/opportunities', { body: { network_id: Number(fval(f, 'network_id')) || null, category: fval(f, 'category'), title: fval(f, 'title'), description: fval(f, 'description'), requirements: fval(f, 'requirements'), compensation: fval(f, 'compensation'), negotiable: fval(f, 'negotiable'), deadline: dl ? new Date(dl + 'T23:59:00').toISOString() : null } });
    toast('Opportunity published'); location.hash = '#/opportunities/' + o.id; }); });
}, { k: 'opps', auth: true });

on(/^\/opportunities\/(\d+)$/, async (c, id) => {
  const o = await api('/opportunities/' + id);
  c.innerHTML = `<a class="small muted" href="#/opportunities">← Opportunities</a><div class="card"><div class="row between wrap"><span class="pill g">${esc(o.category)}</span><span class="pill ${o.status === 'open' ? 'g' : ''}">${esc(o.status)}${o.expired ? ' · deadline passed' : ''}</span></div>
    <h2>${esc(o.title)}${demo(o)}</h2><div class="small muted">${o.network ? `by <a class="green" href="#/n/${esc(o.network.slug)}">${esc(o.network.name)}</a> · ` : ''}posted by <a class="green" href="#/u/${esc(o.creator.username)}">@${esc(o.creator.username)}</a> · ${ago(o.created_at)}</div>
    <p style="white-space:pre-wrap">${rich(o.description)}</p>${o.requirements ? `<h3>Requirements</h3><p class="small" style="white-space:pre-wrap">${rich(o.requirements)}</p>` : ''}
    <div class="row wrap" style="gap:18px"><span class="stat"><b>${esc(o.compensation || '—')}</b>Compensation${o.negotiable ? ' (negotiable)' : ''}</span><span class="stat"><b>${o.deadline ? new Date(o.deadline).toLocaleDateString() : 'None'}</b>Deadline</span><span class="stat"><b>${o.applicants}</b>Responses</span></div>
    <div id="oact" style="margin-top:14px"></div></div><div id="apps"></div>`;
  const act = $('#oact');
  if (!S.me) act.innerHTML = '<a class="btn primary" href="#/login">Log in to apply</a>';
  else if (o.can_manage) act.innerHTML = `<div class="row wrap"><span class="small muted">Status:</span>${['open', 'filled', 'closed'].map(s => `<button class="btn sm ${o.status === s ? 'primary' : ''}" data-st="${s}">${s}</button>`).join('')}</div>`;
  else if (o.my_application) act.innerHTML = `<span class="pill a">You ${o.my_application.kind === 'application' ? 'applied' : 'expressed interest'} · ${esc(o.my_application.status)}</span>${o.my_application.kind === 'interest' && o.status === 'open' ? ' <button class="btn sm" id="upg">Send full application</button>' : ''} <a class="btn sm" href="#/messages/${esc(o.creator.username)}">Message creator</a>`;
  else if (o.status === 'open' && !o.expired) act.innerHTML = `<form id="apf"><textarea class="in" name="message" maxlength="2000" rows="4" placeholder="Why you're a fit: experience, links, availability (20+ characters for a full application)"></textarea><div class="err"></div><div class="row"><button class="btn primary" type="submit">Apply</button><button class="btn ghost" type="button" id="int">I'm interested</button></div></form>`;
  else act.innerHTML = '<span class="muted">Not accepting responses.</span>';
  act.querySelectorAll('[data-st]').forEach(b => b.onclick = async () => { try { await api(`/opportunities/${o.id}/status`, { body: { status: b.dataset.st } }); toast('Status updated'); route(); } catch (e) { fail(e); } });
  const f = $('#apf');
  const send = kind => submitForm(f, async () => { await api(`/opportunities/${o.id}/apply`, { body: { kind, message: fval(f, 'message') } }); toast(kind === 'application' ? 'Application sent' : 'Interest sent'); route(); });
  f && f.addEventListener('submit', e => { e.preventDefault(); send('application'); });
  $('#int')?.addEventListener('click', () => send('interest'));
  $('#upg')?.addEventListener('click', () => modal(`<h3>Full application</h3><form id="upf"><textarea class="in" name="message" rows="5" minlength="20" maxlength="2000" required></textarea><div class="err"></div><button class="btn primary" type="submit">Send</button></form>`, c2 => {
    const g = $('#upf', c2); g.addEventListener('submit', e => { e.preventDefault(); submitForm(g, async () => { await api(`/opportunities/${o.id}/apply`, { body: { kind: 'application', message: fval(g, 'message') } }); closeModal(); toast('Application sent'); route(); }); }); }));
  if (o.applications) {
    $('#apps').innerHTML = `<div class="card"><h3 style="margin-top:0">Applicants (${o.applications.length})</h3>${o.applications.map(a => `<div class="li" style="align-items:flex-start">${avatar(a.applicant)}<div class="grow"><a href="#/u/${esc(a.applicant.username)}"><b>${esc(a.applicant.display_name)}</b></a> <span class="tiny muted">@${esc(a.applicant.username)} · ${a.kind} · ${ago(a.created_at)}</span> <span class="pill ${a.status === 'accepted' || a.status === 'completed' ? 'g' : a.status === 'rejected' ? 'r' : 'a'}">${a.status}</span>
      ${a.message ? `<div class="small" style="white-space:pre-wrap">${esc(a.message)}</div>` : ''}<div class="row wrap" style="margin-top:6px"><a class="btn sm" href="#/passport/${esc(a.applicant.username)}">Passport</a><a class="btn sm" href="#/messages/${esc(a.applicant.username)}">Contact</a>
      ${a.status === 'pending' ? `<button class="btn primary sm" data-ad="${a.id}" data-s="accepted">Accept</button><button class="btn danger sm" data-ad="${a.id}" data-s="rejected">Reject</button>` : a.status === 'accepted' ? `<button class="btn sm" data-ad="${a.id}" data-s="completed">Mark collaboration completed</button>` : ''}</div></div></div>`).join('') || '<p class="muted small">No responses yet.</p>'}</div>`;
    $('#apps').querySelectorAll('[data-ad]').forEach(b => b.onclick = async () => { try { await api('/applications/' + b.dataset.ad, { body: { status: b.dataset.s } }); toast('Updated'); route(); } catch (e) { fail(e); } });
  }
}, { k: 'opps' });

// ---------------------------------------------------------------- Network Passport / profile
async function passport(c, name, tab = 'passport') {
  const u = await api('/users/' + name);
  const r = u.reputation, ind = r.indicators, t = ind.verified_trading_performance;
  const netList = l => l.map(n => `<a class="chip" href="#/n/${esc(n.slug)}">${esc(n.name)}${n.role && n.role !== 'member' ? ' · ' + esc(n.role === 'founder' ? 'Founder' : 'Admin') : ''}</a>`).join('') || '<span class="muted small">None</span>';
  c.innerHTML = `<div class="nethead"><div class="cover"></div><div class="info"><div class="row between wrap" style="align-items:flex-end">${avatar(u, 'xl')}
    <div class="row wrap">${u.is_me ? '<a class="btn sm" href="#/settings">Edit profile & privacy</a>' : S.me ? `<button class="btn primary sm" data-act="follow" data-user="${esc(u.username)}">${u.is_following ? 'Connected ✓' : 'Connect'}</button><a class="btn sm" href="#/messages/${esc(u.username)}">Message</a><button class="btn sm" id="endbtn">Endorse</button><button class="btn danger sm" data-act="block-user" data-user="${esc(u.username)}" data-blocked="${u.blocked ? 1 : 0}">${u.blocked ? 'Unblock' : 'Block'}</button>` : ''}</div></div>
    <h2 style="margin:8px 0 0">${esc(u.display_name)} ${u.verification.identity.verified ? vbadge() : ''}${demo(u)}</h2><div class="small muted">@${esc(u.username)} · Network Passport · member since ${new Date(u.created_at).toLocaleDateString()}</div>
    <p>${rich(u.bio)}</p>
    <div class="row wrap small">${u.x_handle ? `<a class="green" href="https://x.com/${esc(u.x_handle)}" target="_blank" rel="noopener nofollow">X @${esc(u.x_handle)}</a>` : ''}${u.telegram ? `<a class="green" href="https://t.me/${esc(u.telegram)}" target="_blank" rel="noopener nofollow">Telegram @${esc(u.telegram)}</a>` : ''}${u.website ? `<a class="green" href="${esc(u.website)}" target="_blank" rel="noopener nofollow">${esc(u.website.replace(/^https?:\/\//, ''))}</a>` : ''}${u.wallet_address ? `<span class="muted" title="Self-reported, not ownership-verified unless marked">Wallet ${esc(u.wallet_address.slice(0, 4))}…${esc(u.wallet_address.slice(-4))}</span>` : ''}</div>
    <div class="row wrap" style="gap:18px;margin-top:8px"><span class="stat"><b>Lv ${r.level}</b>${kfmt(r.xp)} XP earned</span><span class="stat"><b>${u.followers}</b>Network Members</span><span class="stat"><b>${u.following}</b>Connected</span><span class="stat"><b>${ind.endorsements.value}</b>Endorsements</span></div>
    <div class="bar" style="max-width:320px"><i style="width:${Math.round(r.level_progress * 100)}%"></i></div></div>
    <div class="tabs" style="padding:0 10px"><a href="#/passport/${esc(u.username)}" class="${tab === 'passport' ? 'on' : ''}">Passport</a><a href="#/u/${esc(u.username)}" class="${tab === 'posts' ? 'on' : ''}">Network Posts</a></div></div><div id="ptab" style="margin-top:14px"></div>`;
  $('#endbtn')?.addEventListener('click', () => modal(`<h3>Endorse @${esc(u.username)}</h3><p class="tiny muted">Endorsements are for people you've actually worked with: a shared Network or a collaboration is required. One per category, max 5 per day.</p>
    <form id="enf"><div class="chips">${S.meta.endorse_categories.map(k => `<label class="chip ${u.my_endorsements.includes(k) ? 'on' : ''}"><input type="radio" name="cat" value="${esc(k)}" hidden ${u.my_endorsements.includes(k) ? 'disabled' : ''}>${esc(k)}${u.my_endorsements.includes(k) ? ' ✓' : ''}</label>`).join('')}</div>
    <textarea class="in" name="note" maxlength="300" rows="2" placeholder="What did they do well? (optional)" style="margin-top:10px"></textarea><div class="err"></div><button class="btn primary" type="submit">Endorse</button></form>`, c2 => {
      const f = $('#enf', c2); f.addEventListener('change', () => f.querySelectorAll('label.chip').forEach(l => { if (!l.querySelector('input').disabled) l.classList.toggle('on', l.querySelector('input').checked); }));
      f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => { const cat = (f.querySelector('input[name=cat]:checked') || {}).value; if (!cat) throw new Error('Pick a category.');
        await api(`/users/${u.username}/endorse`, { body: { category: cat, note: fval(f, 'note') } }); closeModal(); toast('Endorsement recorded'); route(); }); }); }));
  const el = $('#ptab');
  if (tab === 'posts') return loadFeed(el, `/users/${u.username}/posts`, 'No Network Posts yet.');
  const hidden = u.hidden_sections.length ? `<p class="tiny muted">@${esc(u.username)} keeps some Passport sections private.</p>` : '';
  el.innerHTML = `<div class="card"><h3 style="margin-top:0">Verification</h3><div class="small">${verifLine(u.verification)}</div><p class="tiny muted">Each verification type is separate. ${esc(t.label)}.</p>
    ${u.is_me ? `<div class="row wrap"><button class="btn sm" data-vk="wallet">Request wallet verification</button><button class="btn sm" data-vk="identity">Request identity verification</button></div><p class="tiny muted">No external provider is connected in this beta, so requests stay pending. NETWORK never asks for seed phrases or private keys.</p>` : ''}</div>
    <div class="card"><h3 style="margin-top:0">Reputation indicators</h3><div class="indic">${indicCard('Engagement quality', ind.engagement_quality.value, ind.engagement_quality.detail)}${indicCard('Collaboration history', ind.collaboration_history.value, ind.collaboration_history.detail)}
      ${indicCard('Fulfilled commitments', ind.fulfilled_commitments.value, ind.fulfilled_commitments.detail)}${indicCard('Reliability', ind.reliability.value, ind.reliability.detail, pct)}${indicCard('Community contributions', ind.community_contributions.value, ind.community_contributions.detail)}
      ${indicCard('Tracked calls (DexScreener price at post time)', t.verified ? `${t.tracked_calls} · ${pct(t.win_rate)} hit 1.5×` : null, t.verified ? `Avg peak ${mx(t.avg_peak)} · ${t.rugs} rugs flagged` : 'No independently tracked calls yet')}</div><p class="tiny muted">Reputation is earned from on-platform records only. Follower counts don't add reputation, and it can't be bought.</p></div>
    ${hidden}
    ${u.networks_founded.length || u.networks_joined.length || u.is_me ? `<div class="card"><h3 style="margin-top:0">Networks founded</h3><div class="chips">${netList(u.networks_founded)}</div><h3>Networks joined</h3><div class="chips">${netList(u.networks_joined)}</div><h3>Connected Networks</h3><div class="chips">${netList(u.network_connections)}</div><h3>Projects supported</h3><div class="chips">${netList(u.projects_supported)}</div></div>` : ''}
    ${u.achievements.length ? `<div class="card"><h3 style="margin-top:0">Achievements</h3><div class="chips">${u.achievements.map(a => `<span class="chip" title="${esc(a.desc)}">🏅 ${esc(a.name)}</span>`).join('')}</div></div>` : ''}
    ${Object.keys(u.endorsement_summary || {}).length || u.endorsements.length ? `<div class="card"><h3 style="margin-top:0">Endorsements</h3><div class="chips">${Object.entries(u.endorsement_summary).map(([k, v]) => `<span class="chip on">${esc(k)} · ${v}</span>`).join('')}</div>
      ${u.endorsements.map(e => `<div class="li small">${avatar(e.from, 'sm')}<div class="grow"><a href="#/u/${esc(e.from.username)}">@${esc(e.from.username)}</a> endorsed for <b>${esc(e.category)}</b>${e.note ? `: “${esc(e.note)}”` : ''}<div class="tiny muted">${ago(e.created_at)}</div></div></div>`).join('')}</div>` : ''}
    ${u.collaborations.length ? `<div class="card"><h3 style="margin-top:0">Collaboration history</h3>${u.collaborations.map(x => `<a class="li small" href="#/opportunities/${x.opportunity_id}"><span class="grow"><b>${esc(x.title)}</b> with @${esc(x.with.username)} · ${esc(x.category)}</span><span class="pill ${x.status === 'completed' ? 'g' : 'a'}">${esc(x.status)}</span></a>`).join('')}</div>` : ''}
    ${u.calls.length ? `<div class="card"><h3 style="margin-top:0">Token calls</h3>${u.calls.slice(0, 5).map(callCard).join('')}</div>` : ''}`;
  el.querySelectorAll('[data-vk]').forEach(b => b.onclick = async () => { try { const r2 = await api('/verifications', { body: { kind: b.dataset.vk } }); toast('Request recorded: ' + r2.detail); route(); } catch (e) { fail(e); } });
}
on(/^\/passport\/(\w+)$/, (c, n) => passport(c, n, 'passport'), { k: 'me' });
on(/^\/u\/(\w+)$/, (c, n) => passport(c, n, 'posts'), { k: 'me' });
on(/^\/me$/, c => passport(c, S.me.username, 'passport'), { k: 'me', auth: true });

on(/^\/settings$/, c => {
  const m = S.me, pv = m.privacy;
  const PL = { show_wallet: 'Wallet address', show_socials: 'Social links', show_networks: 'Networks founded / joined / connected', show_endorsements: 'Endorsements received', show_contributions: 'Contributions & collaboration history', show_achievements: 'Achievements' };
  c.innerHTML = `<div class="card"><h2 style="margin-top:0">Edit profile</h2><form id="sf">
  <div class="row">${avatar(m, 'lg')}<label class="f grow"><span>Profile picture</span><input type="file" accept="image/*" data-up="avatar_url"></label></div><input type="hidden" name="avatar_url" value="${esc(m.avatar_url || '')}">
  <label class="f"><span>Display name</span><input class="in" name="display_name" required maxlength="50" value="${esc(m.display_name)}"></label>
  <label class="f"><span>Bio</span><textarea class="in" name="bio" maxlength="300" rows="3">${esc(m.bio)}</textarea></label>
  <div class="row wrap"><label class="f grow"><span>X handle</span><input class="in" name="x_handle" maxlength="20" value="${esc(m.x_handle)}"></label><label class="f grow"><span>Telegram</span><input class="in" name="telegram" maxlength="40" value="${esc(m.telegram)}"></label></div>
  <label class="f"><span>Website</span><input class="in" name="website" maxlength="200" value="${esc(m.website)}" placeholder="https://"></label>
  <label class="f"><span>Solana wallet address (optional, public address only)</span><input class="in" name="wallet_address" maxlength="64" value="${esc(m.wallet_address)}"></label>
  <p class="tiny muted">Never share a seed phrase or private key. NETWORK will never ask for them. A wallet entered here is not "verified" ownership.</p>
  <h3>Passport privacy: show publicly</h3>${Object.entries(PL).map(([k, l]) => `<label class="row small" style="margin:6px 0"><input type="checkbox" name="${k}" ${pv[k] ? 'checked' : ''}> ${l}</label>`).join('')}
  <div class="err"></div><button class="btn primary" type="submit">Save</button> <a class="btn ghost" href="#/welcome">Change role & interests</a></form></div>`;
  const f = $('#sf'); bindUploads(f);
  f.addEventListener('submit', e => { e.preventDefault(); submitForm(f, async () => {
    const body = { display_name: fval(f, 'display_name'), bio: fval(f, 'bio'), avatar_url: fval(f, 'avatar_url'), x_handle: fval(f, 'x_handle').replace(/^@/, ''), telegram: fval(f, 'telegram'), website: fval(f, 'website'), wallet_address: fval(f, 'wallet_address') };
    Object.keys(PL).forEach(k => body[k] = fval(f, k));
    S.me = await api('/me', { method: 'PUT', body }); toast('Profile saved'); shell(); route(); }); });
}, { k: 'me', auth: true });

// ---------------------------------------------------------------- messages
function appendDM(m) { const box = $('#msgs'); if (!box || document.querySelector(`[data-dm="${m.id}"]`)) return; box.insertAdjacentHTML('beforeend', `<div class="bubble ${m.mine ? 'mine' : ''}" data-dm="${m.id}">${rich(m.body)}<div class="tiny muted">${ago(m.created_at)}</div></div>`); box.scrollTop = box.scrollHeight; }
on(/^\/messages(?:\/(\w+))?$/, async (c, who) => {
  const convos = await api('/messages');
  const list = `<div class="card" id="clist"><h3 style="margin-top:0">Messages</h3>${convos.map(x => `<a class="li" href="#/messages/${esc(x.user.username)}">${avatar(x.user, 'sm')}<span class="grow ell"><b>${esc(x.user.display_name)}</b><div class="tiny muted ell">${esc(x.last)}</div></span>${x.unread ? `<span class="badge">${x.unread}</span>` : `<span class="tiny muted">${ago(x.at)}</span>`}</a>`).join('') || '<p class="muted small">No conversations yet. Message someone from their Network Passport.</p>'}</div>`;
  if (!who) { c.innerHTML = list; return; }
  S.dmWith = who;
  const th = await api('/messages/' + who);
  c.innerHTML = `<a class="small muted" href="#/messages">← All messages</a><div class="card chat"><div class="row" style="margin-bottom:8px">${avatar(th.user, 'sm')}<a href="#/passport/${esc(th.user.username)}"><b>${esc(th.user.display_name)}</b> <span class="muted small">@${esc(th.user.username)}</span></a></div><div class="msgs" id="msgs"></div>
    <form id="dmf" class="row" style="margin-top:8px"><input class="in" name="body" required maxlength="2000" placeholder="Write a message…" autocomplete="off"><button class="btn primary" type="submit">Send</button></form><div class="err"></div></div>`;
  th.messages.forEach(appendDM);
  const me = await api('/me'); if (me) { S.me = me; badges(); }
  const f = $('#dmf'); f.addEventListener('submit', e => { e.preventDefault(); const body = fval(f, 'body'); if (!body) return;
    api('/messages/' + who, { body: { body } }).then(m => { f.elements.body.value = ''; appendDM(m); c.querySelector('.err').textContent = ''; }).catch(er => c.querySelector('.err').textContent = er.message); });
}, { k: 'messages', auth: true });

// ---------------------------------------------------------------- notifications
on(/^\/notifications$/, async c => {
  const ns = await api('/notifications');
  c.innerHTML = `<div class="row between"><h2>Notifications</h2>${ns.some(n => !n.read) ? '<button class="btn sm" id="mar">Mark all as read</button>' : ''}</div><div class="card">${ns.map(n => `<a class="li" href="${esc(n.link || '#/notifications')}" data-nid="${n.id}" style="${n.read ? 'opacity:.65' : ''}">${n.read ? '' : '<span class="green">●</span>'}<span class="grow small">${esc(n.text)}<div class="tiny muted">${esc(n.type.replace(/_/g, ' '))} · ${ago(n.created_at)}</div></span></a>`).join('') || '<p class="muted small">No notifications yet.</p>'}</div>`;
  $('#mar')?.addEventListener('click', async () => { await api('/notifications/read', { body: {} }).catch(fail); S.me.unread_notifications = 0; badges(); route(); });
  c.querySelectorAll('[data-nid]').forEach(a => a.addEventListener('click', () => { api(`/notifications/${a.dataset.nid}/read`, { body: {} }).then(() => { S.me.unread_notifications = Math.max(0, S.me.unread_notifications - 1); badges(); }).catch(() => {}); }));
}, { k: 'notifications', auth: true });

// ---------------------------------------------------------------- rankings
on(/^\/rankings(?:\/(\w+))?$/, async (c, cat = 'top') => {
  const r = await api('/rankings');
  const cur = r.categories.find(x => x.key === cat) || r.categories[0];
  const rows = cur.kind === 'network'
    ? cur.rows.map(n => `<tr><td class="num">${n.rank}</td><td><a class="row" href="#/n/${esc(n.slug)}">${netAv(n, 'sm')}<span><b>${esc(n.name)}</b>${demo(n)}<div class="tiny muted">${esc(n.type)} · ${n.members} members</div></span></a></td><td class="score">${cur.key === 'growing' ? pct(n.growth) : cur.key === 'active' ? n.activity : n.score.toFixed(1)}</td>
      <td class="hide-sm">${Object.entries(n.score_parts).map(([k, v]) => `<div class="factor"><span class="tiny">${esc(k.replace(/_/g, ' '))}</span><span class="tiny muted">${v.toFixed(1)}</span></div>`).join('')}</td></tr>`).join('')
    : cur.rows.map(u => `<tr><td class="num">${u.rank}</td><td><a class="row" href="#/passport/${esc(u.username)}">${avatar(u, 'sm')}<span><b>${esc(u.display_name)}</b>${demo(u)}<div class="tiny muted">@${esc(u.username)} · Lv ${u.level}</div></span></a></td><td class="score">${cur.key === 'callers' ? pct(u.trading.win_rate) : cur.key === 'endorsed' ? u.endorsements_weighted.toFixed(1) : u[{ collaborators: 'collaborations', contributors: 'contributions', research: 'research' }[cur.key]]}</td><td class="hide-sm tiny muted">${cur.key === 'callers' ? `${u.trading.tracked_calls} tracked calls · avg peak ${mx(u.trading.avg_peak)} · ${u.trading.rugs} rugs` : cur.key === 'endorsed' ? `${u.endorsements} endorsements (weighted by endorser reputation)` : ''}</td></tr>`).join('');
  c.innerHTML = `<h2>Network Rankings</h2><div class="chips">${r.categories.map(x => `<a class="chip ${x.key === cur.key ? 'on' : ''}" href="#/rankings/${x.key}">${esc(x.title)}</a>`).join('')}</div>
   <div class="card" style="margin-top:12px"><h3 style="margin-top:0">${esc(cur.title)}</h3><p class="small muted">Metric: <b>${esc(cur.metric)}</b>. ${esc(cur.how)}</p>
   <table class="table"><thead><tr><th>#</th><th>${cur.kind === 'network' ? 'Network' : 'Member'}</th><th>${esc(cur.metric.split(' (')[0])}</th><th class="hide-sm">Breakdown</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="muted">Nobody qualifies yet. Rankings fill from real activity.</td></tr>'}</tbody></table></div>
   <div class="card"><h3 style="margin-top:0">How the Network score works</h3>${r.method.map(m => `<div class="factor"><span><b>${esc(m.factor)}</b> <span class="muted">${esc(m.how)}</span></span><span class="green">${m.weight}%</span></div>`).join('')}
   <ul class="small muted">${r.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul></div>`;
}, { k: 'rank' });

// ---------------------------------------------------------------- search, intelligence, static pages
on(/^\/search\/(.+)$/, async (c, q) => {
  const r = await api('/search?q=' + encodeURIComponent(q));
  const sec = (t, h) => h ? `<div class="card"><h3 style="margin-top:0">${t}</h3>${h}</div>` : '';
  c.innerHTML = `<h2>Results for “${esc(q)}”</h2>` + sec('People', r.users.map(u => `<a class="li" href="#/passport/${esc(u.username)}">${avatar(u, 'sm')}<b>${esc(u.display_name)}</b><span class="muted small">@${esc(u.username)}</span></a>`).join('')) +
    sec('Networks', r.networks.map(n => `<a class="li" href="#/n/${esc(n.slug)}">${netAv(n, 'sm')}<b>${esc(n.name)}</b><span class="muted small">${esc(n.type)} · ${n.members} members</span></a>`).join('')) +
    sec('Projects', r.projects.map(n => `<a class="li" href="#/n/${esc(n.slug)}/launch">${netAv(n, 'sm')}<b>${esc(n.name)}</b><span class="muted small">Project · ${n.members} members</span></a>`).join('')) +
    sec('Opportunities', r.opportunities.map(o => `<a class="li" href="#/opportunities/${o.id}"><b>${esc(o.title)}</b><span class="muted small">${esc(o.category)}</span></a>`).join('')) +
    (r.posts.length ? '<h3>Network Posts</h3>' + feedHTML(r.posts) : '') + (Object.values(r).every(x => !x.length) ? '<div class="card empty">No results.</div>' : '');
});
on(/^\/tag\/(.+)$/, async (c, tag) => { c.innerHTML = `<h2>${esc(tag)}</h2><div id="tf"></div>`; await loadFeed($('#tf'), '/feed?tab=' + encodeURIComponent('tag:' + tag.toLowerCase()), 'No posts with this tag in the last while.'); });
on(/^\/intelligence$/, async c => {
  const d = await api('/intelligence');
  const nl = l => l.map(n => `<a class="li" href="#/n/${esc(n.slug)}">${netAv(n, 'sm')}<span class="grow"><b>${esc(n.name)}</b><div class="tiny muted">${esc(n.type)}${n.members != null ? ' · ' + n.members + ' members' : ''}${n.new_members_7d ? ` · +${n.new_members_7d} this week` : ''}</div></span></a>`).join('') || '<p class="muted small">Nothing yet.</p>';
  const box = (t, h) => `<div class="card"><h3 style="margin-top:0">${t}</h3>${h}</div>`;
  c.innerHTML = `<h2>Network Intelligence</h2><p class="small muted">A quick view of your ecosystem, built only from records you're allowed to see.</p>
   <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px">
   ${box('Connected Networks', nl(d.connected_networks))}${box('Related projects', nl(d.related_projects))}${box('Growing communities', nl(d.growing_communities))}
   ${box('Partnership activity', d.partnership_activity.map(p => `<div class="li small"><a class="green" href="#/n/${esc(p.a.slug)}">${esc(p.a.name)}</a> ⇄ <a class="green" href="#/n/${esc(p.b.slug)}">${esc(p.b.name)}</a><span class="tiny muted">${p.at ? ago(p.at) : ''}</span></div>`).join('') || '<p class="muted small">No connections yet.</p>')}
   ${box('Your collaborators', d.collaborators.map(u => `<a class="li small" href="#/passport/${esc(u.username)}">${avatar(u, 'sm')}<b>${esc(u.display_name)}</b><span class="muted">${u.count} collab</span></a>`).join('') || '<p class="muted small">Accept or complete opportunities to build history.</p>')}
   ${box('Network activity (7 days)', d.network_activity.map(n => `<a class="li small" href="#/n/${esc(n.slug)}"><b class="grow">${esc(n.name)}</b><span class="muted">${n.posts_7d} posts · ${n.chat_7d} chat</span></a>`).join('') || '<p class="muted small">Join Networks to see activity.</p>')}
   ${box('Relevant opportunities', d.relevant_opportunities.map(o => `<a class="li small" href="#/opportunities/${o.id}"><b class="grow">${esc(o.title)}</b><span class="muted">${esc(o.category)}</span></a>`).join('') || '<p class="muted small">None right now.</p>')}
   ${box('Upcoming events', d.upcoming_events.map(e => `<a class="li small" href="#/n/${esc(e.network.slug)}/events"><b class="grow">${esc(e.title)}</b><span class="muted">${new Date(e.starts_at).toLocaleDateString()} · ${esc(e.network.name)}</span></a>`).join('') || '<p class="muted small">No events.</p>')}
   </div><h3>Recent announcements</h3>${feedHTML(d.recent_announcements, 'No announcements from your Networks or shared by connected Networks.')}`;
}, { k: 'discover', auth: true });
on(/^\/rewards$/, c => { c.innerHTML = `<div class="card"><h2 style="margin-top:0">Rewards: coming soon</h2><p class="muted">Rewards are not live. When they launch they will be tied to earned contribution, never to buying reputation or rankings. Nothing is being distributed today.</p></div>`; });
on(/^\/about$/, c => { c.innerHTML = `<div class="card"><h2 style="margin-top:0">About NETWORK</h2><p>NETWORK isn't just where you find the next opportunity. It's where you build the connections that create opportunities.</p><img src="/static/img/mockup.png" alt="Design mockup" style="max-width:100%;border-radius:12px"><p class="small muted">Token data from DexScreener's free public API. Not financial advice. Items marked DEMO are seeded sample content.</p></div>`; });

// ---------------------------------------------------------------- boot
async function boot() {
  try { [S.me, S.meta] = await Promise.all([api('/me'), api('/meta')]); } catch (e) { S.meta = S.meta || { network_types: [], opportunity_categories: [], endorse_categories: [], project_stages: [], roles: [] }; }
  shell(); connectWS(); route();
}
boot();
