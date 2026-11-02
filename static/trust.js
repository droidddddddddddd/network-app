/* NETWORK trust features: wallet signing (signMessage only), domain/dev-wallet/metadata verification, CTO backing,
   moderation queues, shared activity, achievements. Loaded after app.js; all checks are enforced server-side. */
'use strict';
const B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
function b58(bytes) {
  let n = 0n; for (const b of bytes) n = n * 256n + BigInt(b);
  let out = ''; while (n > 0n) { out = B58[Number(n % 58n)] + out; n /= 58n; }
  for (const b of bytes) { if (b !== 0) break; out = '1' + out; }
  return out;
}
const shortAddr = a => a && a.length > 10 ? `${a.slice(0, 4)}…${a.slice(-4)}` : (a || '');
const updatedAgo = t => { if (!t) return 'just now'; const m = Math.floor((Date.now() - new Date(t)) / 60000); return m < 1 ? 'just now' : m === 1 ? '1 min ago' : m < 60 ? `${m} min ago` : `${Math.floor(m / 60)} h ago`; };

function walletProvider() {
  const p = window.phantom?.solana || window.solflare || window.backpack || window.solana;
  return p && typeof p.signMessage === 'function' ? p : null;
}
/* Asks the browser wallet to SIGN A MESSAGE. Never a transaction. Returns {nonce, signature} for the server to verify. */
async function solSign(purpose, subject = '') {
  const w = walletProvider();
  if (!w) throw new Error('No Solana wallet found in this browser. Install Phantom, Solflare or Backpack, then try again. (Message signing only, no transaction.)');
  const res = await w.connect();
  const address = (res?.publicKey || w.publicKey).toString();
  const ch = await api('/verify/nonce', { body: { purpose, address, subject } });
  const signed = await w.signMessage(new TextEncoder().encode(ch.message), 'utf8');
  const sig = signed.signature || signed;
  return { nonce: ch.nonce, signature: b58(new Uint8Array(sig)), address };
}
async function verifyWalletFlow() {
  if (!confirm('Your wallet will ask you to SIGN A MESSAGE (not a transaction, no fees). NETWORK never asks for your seed phrase or private key. Continue?')) return;
  try { const s = await solSign('wallet'); await api('/verify/wallet', { body: { nonce: s.nonce, signature: s.signature } }); toast('Wallet ownership verified'); S.me = await api('/me'); route(); } catch (e) { fail(e); }
}

function suspendedBanner(c) {
  if (!S.me || !S.me.suspended || !c || c.querySelector('.susp')) return;
  c.insertAdjacentHTML('afterbegin', `<div class="card susp" style="border-color:#f05a5a"><b>Your account is suspended${S.me.suspended_until && !S.me.suspended_until.startsWith('9999') ? ' until ' + esc(new Date(S.me.suspended_until).toLocaleString()) : ''}.</b><div class="small muted">You can't post, message or endorse while suspended. Reason: ${esc(S.me.suspend_reason || 'not given')}</div></div>`);
}

// ---------------------------------------------------------------- reports (users + Networks; posts use the post menu)
document.addEventListener('click', async e => {
  const b = e.target.closest('[data-report]'); if (!b) return;
  e.preventDefault();
  const what = b.dataset.report === 'user' ? '@' + b.dataset.target : 'this Network';
  const reason = prompt(`Why are you reporting ${what}? (3–300 characters)`); if (!reason) return;
  try { await api('/reports', { body: { target_type: b.dataset.report, target: b.dataset.target, reason } }); toast('Reported to platform moderators. You\'ll be notified when it\'s reviewed.'); } catch (err) { fail(err); }
});

async function modQueue(el, slug = '') {
  const status = (location.hash.match(/[?&]status=(\w+)/) || [])[1] || 'open';
  const q = await api(`/moderation/queue?status=${status}${slug ? '&network=' + encodeURIComponent(slug) : ''}`);
  const base = slug ? `#/n/${slug}/moderation` : '#/moderation';
  const platform = !slug && S.me.is_platform_admin;
  const tgt = r => r.target_type === 'post' ? `<div class="small">“${esc(r.target.body)}”</div><div class="tiny muted">by @${esc(r.target.author?.username || '?')}${r.target.hidden ? ' · hidden' : ''}${r.target.removed ? ' · removed' : ''}</div>`
    : r.target_type === 'user' ? `<div class="small">User <a class="green" href="${esc(r.target.link)}">@${esc(r.target.user?.username || '?')}</a></div>` : `<div class="small">Network <a class="green" href="${esc(r.target.link)}">${esc(r.target.network?.name || '?')}</a></div>`;
  el.innerHTML = `<div class="card"><div class="row between wrap"><h3 style="margin:0">${slug ? 'Network moderation queue' : 'Platform moderation queue'}</h3><div class="chips"><a class="chip ${status === 'open' ? 'on' : ''}" href="${base}">Open</a><a class="chip ${status === 'resolved' ? 'on' : ''}" href="${base}?status=resolved">Resolved</a></div></div>
    <p class="tiny muted">Every action is audit-logged and the reporter is notified.${slug ? ' Suspensions are handled by platform admins.' : ''}</p>
    ${q.map(r => `<div class="li" style="align-items:flex-start"><div class="grow"><span class="pill a">${esc(r.target_type)}</span> ${r.count > 1 ? `<span class="pill">${r.count} reports</span>` : ''} <span class="tiny muted">${ago(r.created_at)} by @${esc(r.reporter?.username || '?')}${r.network ? ' · ' + esc(r.network.name) : ''}</span>
      ${tgt(r)}<div class="small"><b>Reason:</b> ${esc(r.reason)}</div>${r.status === 'resolved' ? `<div class="tiny green">Resolved: ${esc(r.resolution.replace(/_/g, ' '))} · ${ago(r.resolved_at)}</div>` : ''}</div>
      ${r.status === 'open' ? `<div class="row wrap"><button class="btn sm" data-rs="dismiss" data-rid="${r.id}">Dismiss</button>${r.target_type === 'post' ? `<button class="btn sm" data-rs="hide_post" data-rid="${r.id}">Hide post</button><button class="btn danger sm" data-rs="remove_post" data-rid="${r.id}">Remove post</button>` : ''}${platform && r.target_type !== 'network' ? `<button class="btn danger sm" data-rs="suspend_user" data-rid="${r.id}">Suspend user</button>` : ''}</div>` : ''}</div>`).join('') || '<p class="muted small">Nothing here.</p>'}</div>`;
  el.querySelectorAll('[data-rs]').forEach(b => b.onclick = async () => {
    const body = { action: b.dataset.rs, note: '' };
    if (body.action === 'suspend_user') { const h = prompt('Suspend for how many hours? Leave empty for indefinite.'); if (h === null) return; if (h.trim()) { body.suspend_hours = parseInt(h, 10); if (!(body.suspend_hours > 0)) return toast('Enter a number of hours', true); } }
    body.note = prompt('Note for the audit log (optional)') || '';
    try { const r = await api(`/reports/${b.dataset.rid}/resolve`, { body }); toast(`Resolved ${r.resolved} report(s)`); route(); } catch (e) { fail(e); }
  });
}
on(/^\/moderation(?:\?.*)?$/, async c => { if (!S.me.is_platform_admin) { c.innerHTML = '<div class="card empty">Platform moderation is only for platform admins (set by the ADMIN_USERNAMES server setting).</div>'; return; } await modQueue(c); }, { k: '', auth: true });

// ---------------------------------------------------------------- shared activity
async function connectedActivity(el) {
  try {
    const a = await api('/activity/connected');
    el.innerHTML = a.length ? `<div class="card"><h3 style="margin-top:0">Activity from connected Networks</h3>${a.map(x => `<a class="li small" href="${esc(x.link || '#/n/' + x.network.slug)}">${netAv(x.network, 'sm')}<span class="grow">${esc(x.text)}<div class="tiny muted">${esc(ACT_LABELS[x.type] || x.type)} · ${esc(x.network.name)} · ${ago(x.created_at)}</div></span></a>`).join('')}</div>` : '';
  } catch { el.innerHTML = ''; }
}

// ---------------------------------------------------------------- Launch Room: domain, dev wallet, metadata, CTO
async function tokenTrustPanel(el, n, P_) {
  let t; try { t = await api(`/networks/${n.slug}/token-trust`); } catch (e) { el.innerHTML = ''; return; }
  const st = x => x ? `<span class="pill ${x.status === 'verified' ? 'g' : x.status === 'failed' ? 'r' : 'a'}">${x.status === 'verified' ? '✓' : '○'} ${esc(x.detail)}</span>` : '<span class="pill">Not verified</span>';
  const ev = t.dev_evidence;
  const manage = P_.perm_settings;
  el.innerHTML = `<div class="card"><h3 style="margin-top:0">Trust & verification</h3>
    <p class="tiny muted">Each check proves one specific thing. None of them means a project is safe or a good investment. Wallet checks use message signing only, never a transaction.</p>
    <div class="factor"><span><b>Project domain</b></span>${st(t.domain)}</div>
    ${manage ? `<form id="domf" class="row wrap" style="margin:6px 0 12px"><input class="in grow" name="domain" placeholder="example.com" value="${esc(t.domain?.domain || '')}" maxlength="253"><button class="btn sm" type="submit">Get verification code</button>${t.domain && t.domain.status !== 'verified' ? '<button class="btn primary sm" type="button" id="domchk">Check now</button>' : ''}<div class="err" style="width:100%"></div><div id="domi" class="tiny" style="width:100%"></div></form>` : ''}
    <div class="factor"><span><b>Token</b></span>${t.mint ? `<span class="small" style="font-family:monospace">${esc(shortAddr(t.mint))}</span>` : '<span class="small muted" style="text-align:right;flex:1">No token set yet</span>'}</div>
    <div class="factor"><span><b>Dev wallet</b></span>${st(t.devwallet)}</div>
    ${ev ? `<div class="factor"><span><b>Creator wallet balance</b> <span class="tiny muted">(read-only, ${esc(ev.wallet_short)})</span></span><span class="small">${ev.error ? esc(ev.error) : `${kfmt(ev.balance)} tokens · ${esc(ev.summary)}${ev.last_activity ? ' · last activity ' + ago(ev.last_activity * 1000) : ''}`}</span></div>` : ''}
    <div class="factor"><span><b>Metadata authority</b></span>${st(t.metadata)}</div>
    ${manage ? `<form id="mintf" class="row wrap" style="margin-top:10px"><input class="in grow" name="mint" placeholder="Token mint address" value="${esc(t.mint || '')}" maxlength="44">
      <button class="btn sm" type="button" data-sig="devwallet">Verify dev wallet (sign)</button>${t.devwallet ? '<button class="btn sm" type="button" id="devre">Re-check</button>' : ''}<button class="btn sm" type="button" data-sig="metadata">Verify metadata authority (sign)</button><button class="btn ghost sm" type="button" id="ctonew">Start a CTO claim</button><div class="err" style="width:100%"></div></form>` : ''}
    <h4>Community takeover claims</h4>${t.claims.length ? t.claims.map(x => `<a class="li small" href="${esc(x.link)}">${netAv(x.network, 'sm')}<span class="grow"><b>${esc(x.network.name)}</b> · <span class="pill ${x.verified ? 'g' : ''}">${esc(x.label)}</span><div class="tiny muted">${esc(x.role)}</div></span></a>`).join('') : '<p class="small muted">No CTO claims on this token.</p>'}</div>`;
  const mintOf = () => ($('#mintf')?.elements.mint.value || '').trim();
  $('#domf')?.addEventListener('submit', e => { e.preventDefault(); const f = e.target; submitForm(f, async () => { const r = await api(`/networks/${n.slug}/verify/domain`, { body: { domain: fval(f, 'domain') } });
    $('#domi').innerHTML = `Add <b>one</b> of these, then press Check now:<br>DNS TXT record on <b>${esc(r.domain)}</b>: <code>${esc(r.txt)}</code><br>or a file at <code>${esc(r.file_url)}</code> containing <code>${esc(r.file_content)}</code>`; }); });
  $('#domchk')?.addEventListener('click', async () => { try { const r = await api(`/networks/${n.slug}/verify/domain/check`, { body: {} }); toast(r.detail, !r.verified); route(); } catch (e) { fail(e); } });
  el.querySelectorAll('[data-sig]').forEach(b => b.onclick = async () => {
    const mint = mintOf(); if (!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(mint)) return toast('Enter the token mint address first.', true);
    if (!confirm('Your wallet will ask you to SIGN A MESSAGE with the ' + (b.dataset.sig === 'devwallet' ? 'wallet that created the token' : 'metadata update-authority wallet') + '. No transaction, no fees. Continue?')) return;
    try { const s = await solSign(b.dataset.sig, mint); const r = await api(`/networks/${n.slug}/verify/${b.dataset.sig}`, { body: { nonce: s.nonce, signature: s.signature } }); toast(r.detail, !r.verified); route(); } catch (e) { fail(e); }
  });
  $('#devre')?.addEventListener('click', async () => { try { const r = await api(`/networks/${n.slug}/verify/devwallet/recheck`, { body: {} }); toast(r.detail, !r.verified); route(); } catch (e) { fail(e); } });
  $('#ctonew')?.addEventListener('click', async () => { const mint = mintOf(); if (!/^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(mint)) return toast('Enter the token mint address first.', true);
    try { const r = await api(`/networks/${n.slug}/cto`, { body: { mint } }); toast('CTO claim created. Share the "Back this CTO" link with holders.'); location.hash = r.link; } catch (e) { fail(e); } });
}

on(/^\/cto\/(\d+)$/, async (c, id) => {
  const x = await api('/cto/' + id);
  const res = x.result || {};
  c.innerHTML = `<div class="card"><div class="tiny muted">Community takeover claim</div><h2 style="margin:4px 0">${esc(x.network.name)} for $${esc(x.symbol)}</h2>
    <div class="small" style="font-family:monospace">${esc(x.mint)}</div>
    <p><span class="pill ${x.verified ? 'g' : 'a'}">${esc(x.label)}</span></p>
    <p class="tiny muted">${esc(x.what_it_means)} Threshold: ${res.threshold ? `${res.threshold.wallets} distinct wallets holding ${res.threshold.pct}%` : 'set by the server'} of circulating supply (curve, pool, dev and burned tokens excluded). Balances are read live at each check, so selling drops support.</p>
    ${x.dev_verification ? `<p class="small">Separately: <span class="pill g">${esc(x.dev_verification.detail)}</span> (${esc(x.dev_verification.network.name)})</p>` : ''}
    ${S.me ? `<div class="card" style="background:transparent"><b>Back this CTO</b><p class="small">Your wallet will sign this exact text (plus a one-time code). No transaction, no fees:</p><code class="small">${esc(x.support_text)}</code>
      <div class="row wrap" style="margin-top:8px"><button class="btn primary" id="backb">${x.my_backing ? 'Re-sign backing' : 'Sign to back this claim'}</button><button class="btn sm" id="rechk">Re-check now</button></div>${x.my_backing ? `<p class="tiny green">You back this claim with ${esc(x.my_backing)}.</p>` : ''}<p class="tiny muted">One backing per wallet per token; backing another claim moves your support. Wallets created in the last 24h count at 50% and not toward the wallet minimum.</p></div>` : '<a class="btn primary" href="#/login">Log in to back this claim</a>'}
  </div>
  <div class="card"><h3 style="margin-top:0">Backers</h3>${res.checked_at ? `<p class="tiny muted">Checked ${updatedAgo(res.checked_at)} · ${res.distinct} counted wallets · ${(res.pct || 0).toFixed(2)}% of circulating supply${res.shared_funder_pct ? ` · ${res.shared_funder_pct}% of backing comes from wallets that share a first funder` : ''}</p>` : '<p class="tiny muted">Not checked yet.</p>'}
    <table class="table"><thead><tr><th>Wallet</th><th>Balance now</th><th>Counted</th></tr></thead><tbody>${(res.backers || []).map(b => `<tr><td style="font-family:monospace">${esc(b.wallet)}</td><td>${kfmt(b.amount)}</td><td class="small">${b.counted ? '✓' : '—'} ${esc(b.note || '')}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">No backers yet.</td></tr>'}</tbody></table></div>
  <div class="card"><h3 style="margin-top:0">All claims on this token</h3>${x.claims.map(k => `<a class="li small" href="${esc(k.link)}">${netAv(k.network, 'sm')}<span class="grow"><b>${esc(k.network.name)}</b> <span class="pill ${k.role === 'leading claim' ? 'g' : ''}">${esc(k.role)}</span><div class="tiny muted">${esc(k.label)}</div></span></a>`).join('')}</div>`;
  $('#backb')?.addEventListener('click', async () => { if (!confirm('Sign a message (not a transaction) to back this claim?')) return;
    try { const s = await solSign('cto_back', String(x.id)); const r = await api(`/cto/${x.id}/back`, { body: { nonce: s.nonce, signature: s.signature } }); toast(r.switched ? 'Backing moved to this claim' : 'Backing recorded'); route(); } catch (e) { fail(e); } });
  $('#rechk')?.addEventListener('click', async () => { try { await api(`/cto/${x.id}/recheck`, { body: {} }); toast('Re-checked with live balances'); route(); } catch (e) { fail(e); } });
}, { k: 'networks' });

// ---------------------------------------------------------------- achievements & XP (replaces the old Rewards placeholder)
on(/^\/achievements$/, async c => {
  const u = await api('/users/' + S.me.username);
  const r = u.reputation, ind = r.indicators;
  const goals = [
    ['founder', 'Network Founder', 'Found a Network', u.networks_founded.length, 1],
    ['connector', 'Connector', 'Get an approved connection for a Network you founded', u.network_connections.length, 1],
    ['endorsed', 'Endorsed', 'Receive 3 peer endorsements', ind.endorsements.value, 3],
    ['delivers', 'Delivers', 'Complete a collaboration', ind.fulfilled_commitments.value, 1],
    ['tracked_caller', 'Tracked Caller', 'Have an independently tracked token call', ind.verified_trading_performance.tracked_calls || 0, 1],
    ['community_builder', 'Community Builder', 'Be active in 3 Networks', u.networks_founded.length + u.networks_joined.length, 3]];
  const have = new Set(u.achievements.map(a => a.code));
  c.innerHTML = `<div class="card"><h2 style="margin-top:0">Achievements & XP</h2><div class="row wrap" style="gap:18px"><span class="stat"><b>Lv ${r.level}</b>Level</span><span class="stat"><b>${kfmt(r.xp)}</b>XP earned</span></div>
    <div class="bar" style="max-width:420px"><i style="width:${Math.round(r.level_progress * 100)}%"></i></div><p class="tiny muted">${Math.round(r.level_progress * 100)}% of the way to level ${r.level + 1}. XP comes only from on-platform records (posts in Networks, replies, collaborations, endorsements, tracked calls). It can't be bought and there are no token rewards.</p></div>
    <div class="card"><h3 style="margin-top:0">Achievements</h3>${goals.map(([code, name, how, v, need]) => `<div class="li"><span style="font-size:20px">${have.has(code) ? '🏅' : '○'}</span><div class="grow"><b>${esc(name)}</b><div class="tiny muted">${esc(how)}</div><div class="bar"><i style="width:${Math.min(100, Math.round((v || 0) / need * 100))}%"></i></div></div><span class="small ${have.has(code) ? 'green' : 'muted'}">${have.has(code) ? 'Earned' : `${Math.min(v || 0, need)}/${need}`}</span></div>`).join('')}</div>`;
}, { k: 'me', auth: true });
