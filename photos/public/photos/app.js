/* 北欧 2026 · 共享相册前端 —— 一个 ES module，无依赖、无构建，手机和电脑同一份
 *
 * 数据流：/api/list 一次拿全量元数据（几千张也只有几百 KB，带 ETag，没变化时 304）
 *        → 筛选 / 分组 / 排序全部在本机做（瞬时）；只有「文字搜索」去问服务端（它有向量索引和结果缓存）。
 *
 * 上传（最要紧的部分，见 §上传）：
 *   指纹 = SHA-256(每 8 MB 块的 SHA-256 拼接) —— 算一次记在本机，同一个文件再选一次不用重算；
 *   服务端按指纹判断：已有 → 秒传 · 传了一半 → 只补缺的块 · 没有 → 分块传。
 *   每块失败自动重试（指数退避，断网就等 online 事件），手机上传期间保持亮屏。
 */
const API = '/photos/api';
const PART = 8 * 2 ** 20;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const F = (h, k) => `/photos/f/${h}/${k}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const WK = '日一二三四五六';
const DAY0 = Date.UTC(2026, 8, 24);
const fmtB = b => b >= 2 ** 30 ? (b / 2 ** 30).toFixed(2) + ' GB' : b >= 2 ** 20 ? (b / 2 ** 20).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
const fmtD = s => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
const localIso = ms => new Date(ms - new Date(ms).getTimezoneOffset() * 60e3).toISOString().slice(0, 19);
const tOf = it => it.t || localIso(it.c);
const dayOf = it => tOf(it).slice(0, 10);
function dayLabel(d) {
  const [y, m, dd] = d.split('-').map(Number), u = Date.UTC(y, m - 1, dd);
  const n = Math.round((u - DAY0) / 864e5) + 1;
  return `${m}/${dd} 周${WK[new Date(u).getUTCDay()]}` + (n >= 1 && n <= 24 ? ` · D${n}` : '');
}
const hm = it => tOf(it).slice(11, 16);
const md = it => { const t = tOf(it); return `${+t.slice(5, 7)}/${+t.slice(8, 10)} ${t.slice(11, 16)}`; };

class ApiErr extends Error { constructor(status, msg) { super(msg); this.status = status; } }
async function api(path, { method = 'GET', body } = {}) {
  const opt = { method, credentials: 'same-origin', headers: {} };
  if (body !== undefined) { opt.headers['content-type'] = 'application/json'; opt.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(API + path, opt); } catch { throw new ApiErr(0, '网络断了'); }
  let j = null; try { j = await r.json(); } catch { /* 空 body */ }
  if (r.status === 401 && path !== '/login') { showGate(); throw new ApiErr(401, '需要重新登录'); }
  if (!r.ok) throw new ApiErr(r.status, (j && j.error) || `HTTP ${r.status}`);
  return j;
}

function toast(msg, ms = 2600) {
  const t = $('#toast'); t.innerHTML = msg; t.hidden = false;
  clearTimeout(toast.tm); if (ms) toast.tm = setTimeout(() => { t.hidden = true; }, ms);
}

/* ================= 状态 ================= */
const S = {
  me: null, data: null, ver: 0, byH: new Map(), users: new Map(), persons: new Map(), moments: new Map(),
  myPerson: null,
  tab: 'grid', group: localStorage.np_group || 'day', desc: localStorage.np_desc === '1',
  quick: 'all', day: null, person: null, special: null, cam: null, burst: true,
  q: '', res: null, sel: new Set(), selMode: false, view: [], lb: -1,
  searches: [],
};

/* ================= 登录 ================= */
let pendingPass = '';
function showGate() { $('#gate').hidden = false; $('#app').hidden = true; $('#btn-sel').hidden = true; }
async function doPass(pass) {
  $('#pass-err').textContent = '';
  try {
    const r = await api('/login', { method: 'POST', body: { pass } });
    pendingPass = pass;
    $('#f-pass').hidden = true; $('#f-name').hidden = false;
    $('#names').innerHTML = (r.users || []).map(u => `<button type="button" class="chip" data-n="${esc(u.name)}">${esc(u.name)}</button>`).join('');
    $('#name').focus();
  } catch (e) { $('#pass-err').textContent = e.message; }
}
async function doName(name) {
  name = name.trim(); if (!name) return;
  try {
    await api('/login', { method: 'POST', body: { pass: pendingPass, name } });
    localStorage.np_k = pendingPass;              // 之后「复制邀请链接」用；口令本来就是群里共享的
    boot();
  } catch (e) { toast(e.message); }
}
$('#f-pass').addEventListener('submit', e => { e.preventDefault(); doPass($('#pass').value.trim()); });
$('#f-name').addEventListener('submit', e => { e.preventDefault(); doName($('#name').value); });
$('#names').addEventListener('click', e => { const b = e.target.closest('[data-n]'); if (b) doName(b.dataset.n); });

/* ================= 列表 ================= */
async function loadList() {
  const r = await fetch(API + '/list', { credentials: 'same-origin', cache: 'no-cache' });
  if (r.status === 401) { showGate(); return false; }
  const d = await r.json();
  if (S.data && d.ver === S.ver) return false;
  S.data = d; S.ver = d.ver;
  S.byH = new Map(d.items.map(it => [it.h, it]));
  S.users = new Map(d.users.map(u => [u.id, u.name]));
  S.persons = new Map(d.persons.map(p => [p.id, p]));
  S.moments = new Map((d.moments || []).map(m => [m.id, m]));
  S.myPerson = d.persons.find(p => p.uid === S.me.id)?.id ?? null;
  for (const h of [...S.sel]) if (!S.byH.has(h)) S.sel.delete(h);
  return true;
}
async function refresh(force) {
  const changed = await loadList();
  if (!changed && !force) return;
  if (S.q) await runSearch(S.q, true);
  renderAll();
}

/* ================= 筛选 / 分组 ================= */
const isMine = it => it.u.includes(S.me.id) || (S.myPerson != null && it.p.includes(S.myPerson));
const special = it => (it.tg && it.tg.special) || [];
const isHL = it => (it.tg && it.tg.memo >= 4) || special(it).length > 0 || (it.mo != null && (S.moments.get(it.mo)?.memo || 0) >= 4 && it.bc !== 0);
const placeKey = it => it.pl ? it.pl.split(/\s*·\s*/).slice(0, 2).join(' · ') : (it.la != null ? '有坐标 · 等 AI 查地名' : '没有位置信息');
const camKey = it => it.cam || '未知设备';

function filtered() {
  const burstN = new Map();
  for (const it of S.data.items) if (it.b) burstN.set(it.b, (burstN.get(it.b) || 0) + 1);
  S.burstN = burstN;
  let xs = S.data.items.filter(it => {
    if (S.quick === 'mine' && !isMine(it)) return false;
    if (S.quick === 'up' && !it.u.includes(S.me.id)) return false;
    if (S.quick === 'v' && it.k !== 'v') return false;
    if (S.quick === 'i' && it.k !== 'i') return false;
    if (S.quick === 'hl' && !isHL(it)) return false;
    if (S.day && dayOf(it) !== S.day) return false;
    if (S.person != null && !it.p.includes(S.person)) return false;
    if (S.special && !special(it).includes(S.special)) return false;
    if (S.cam && camKey(it) !== S.cam) return false;
    if (S.burst && it.b && !it.bc && !S.res) return false;
    return true;
  });
  if (S.res) {
    const rank = new Map(S.res.ids.map((h, i) => [h, i]));
    xs = xs.filter(it => rank.has(it.h)).sort((a, b) => rank.get(a.h) - rank.get(b.h));
  } else {
    xs.sort((a, b) => tOf(a) < tOf(b) ? -1 : tOf(a) > tOf(b) ? 1 : 0);
    if (S.desc) xs.reverse();
  }
  return xs;
}

/** 分组：返回 [{key, title, sub, items}]，组的顺序按「组里最早一张的时间」—— 地点组因此沿着旅行路线排 */
function groups(xs) {
  if (S.res) return [{ key: 'q', title: '', items: xs }];
  const by = new Map();
  const keyf = { day: dayOf, place: placeKey, cam: camKey, moment: it => it.mo != null ? 'm' + it.mo : 'd' + dayOf(it) }[S.group] || dayOf;
  for (const it of xs) { const k = keyf(it); if (!by.has(k)) by.set(k, []); by.get(k).push(it); }
  const out = [];
  for (const [k, items] of by) {
    const g = { key: k, items, t0: items.reduce((m, it) => tOf(it) < m ? tOf(it) : m, '9') };
    if (S.group === 'day') { g.title = dayLabel(k); g.sub = topPlace(items); }
    else if (S.group === 'place') {
      g.title = k; const days = [...new Set(items.map(dayOf))].sort();
      g.sub = days.length ? dayLabel(days[0]).split(' · ')[0] + (days.length > 1 ? ` → ${dayLabel(days.at(-1)).split(' · ')[0]}` : '') : '';
      const geo = items.filter(it => it.la != null);
      if (geo.length) {
        const la = geo.reduce((s, it) => s + it.la, 0) / geo.length, lo = geo.reduce((s, it) => s + it.lo, 0) / geo.length;
        g.map = `https://www.openstreetmap.org/?mlat=${la.toFixed(5)}&mlon=${lo.toFixed(5)}#map=12/${la.toFixed(4)}/${lo.toFixed(4)}`;
      }
    } else if (S.group === 'cam') { g.title = k; g.sub = [...new Set(items.flatMap(it => it.u.map(u => S.users.get(u))))].join('、'); }
    else if (k[0] === 'm') {
      const m = S.moments.get(Number(k.slice(1))) || {};
      g.title = (m.memo >= 4 ? '★ ' : '') + (m.title || '一段时光'); g.star = m.memo >= 4;
      g.sub = [m.start && dayLabel(m.start.slice(0, 10)).split(' · ')[0] + ' ' + m.start.slice(11, 16) + (m.end ? '–' + m.end.slice(11, 16) : ''), m.place].filter(Boolean).join(' · ');
    } else { g.title = dayLabel(k.slice(1)); g.sub = '还没分到「时刻」（等 AI）'; }
    out.push(g);
  }
  if (S.group === 'cam') out.sort((a, b) => b.items.length - a.items.length);
  else out.sort((a, b) => (a.t0 < b.t0 ? -1 : 1) * (S.desc ? -1 : 1));
  return out;
}
function topPlace(items) {
  const c = new Map();
  for (const it of items) if (it.pl) { const k = it.pl.split(/\s*·\s*/).slice(0, 2).join(' · '); c.set(k, (c.get(k) || 0) + 1); }
  return [...c.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map(x => x[0]).join(' / ');
}

/* ================= 渲染：照片 ================= */
function tile(it) {
  const img = it.f & 1
    ? `<img loading="lazy" decoding="async" src="${F(it.h, 't')}" alt="">`
    : `<span class="ph0">${it.k === 'v' ? '🎬' : '🖼'}<i>${esc((it.n.split('.').pop() || '').toUpperCase())}</i><i>等缩略图</i></span>`;
  const bn = it.b ? S.burstN.get(it.b) : 0;
  const badges = [
    it.k === 'v' ? `<em class="bd">▶ ${it.d ? fmtD(it.d) : ''}</em>` : '',
    bn > 1 && S.burst && !S.res ? `<em class="bd br" title="${bn} 张相似的，这张是${it.pn ? '你挑的' : ' AI 挑的'}最好的">▣ ${bn}</em>` : '',
    isHL(it) ? '<em class="bd hl">★</em>' : '',
    it.src ? '<em class="bd ai" title="AI 改过的">✨</em>' : '',
  ].join('');
  return `<a class="tl${S.sel.has(it.h) ? ' on' : ''}" data-h="${it.h}" href="${F(it.h, 'o')}">${img}${badges}<b class="ck"></b></a>`;
}

function renderGrid() {
  if (!S.data) return;
  const xs = filtered(); S.view = xs;
  const gs = groups(xs);
  const size = xs.reduce((s, it) => s + it.s, 0);
  const nv = xs.filter(it => it.k === 'v').length;
  let sum = `<span>${xs.length - nv} 张照片 · ${nv} 个视频 · ${fmtB(size)}</span>`;
  if (S.res) sum = `<span>🔎 「${esc(S.res.q)}」 ${xs.length} 个结果 · ${S.res.sem ? '关键词 + 语义' : '关键词'} · ${S.res.took} ms${S.res.cached ? '（缓存命中）' : ''}</span>` +
    (S.res.terms && S.res.terms.length > 1 ? `<span class="s">分词：${S.res.terms.map(esc).join(' / ')}</span>` : '') +
    `<button class="chip" id="q-x">✕ 清除搜索</button>`;
  const anyF = S.quick !== 'all' || S.day || S.person != null || S.special || S.cam;
  if (anyF && !S.res) sum += `<button class="chip" id="f-x">✕ 清除筛选</button>`;
  if (xs.length) sum += `<button class="chip" id="dl-all">⬇ 下载这 ${xs.length} 个</button>`;
  $('#sum').innerHTML = sum;
  $('#grid').innerHTML = gs.map(g => `<div class="grp" data-g="${esc(g.key)}">
      ${g.title ? `<div class="gh"><h3>${esc(g.title)}</h3><span class="s">${esc(g.sub || '')} · ${g.items.length}</span>
        ${g.map ? `<a class="s" href="${g.map}" target="_blank" rel="noopener">地图 ↗</a>` : ''}
        <span class="grow"></span><button class="chip sm" data-selg="${esc(g.key)}">选这组</button></div>` : ''}
      <div class="tiles">${g.items.map(tile).join('')}</div></div>`).join('');
  $('#empty').hidden = !!xs.length;
  $('#empty').textContent = S.data.items.length ? '没有符合条件的照片 —— 换个筛选或搜索词试试。' : '还没有照片 —— 点右上角「＋ 上传」，或者直接把文件拖进来。';
  S.groupsNow = gs;
}

function chipRow(el, items, cur, attr) {
  el.innerHTML = items.map(([v, label, n]) => `<button class="chip" data-${attr}="${esc(v)}" aria-pressed="${String(v) === String(cur)}">${label}${n != null ? ` <i>${n}</i>` : ''}</button>`).join('');
  el.hidden = !items.length;
}
function renderChips() {
  const its = S.data.items;
  $$('#quick [data-f]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.f === S.quick)));
  $('#burst').setAttribute('aria-pressed', String(S.burst));
  $$('#grouping [data-gp]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.gp === S.group)));
  $('#order').textContent = S.desc ? '↓ 新的在前' : '↑ 旧的在前';
  const nf = [S.day, S.person, S.special, S.cam].filter(v => v != null).length;   // 手机上按天/人/场景/设备这几行默认收起
  $('#more-f').textContent = S.moreF ? '收起筛选 ▴' : `筛选 ▾${nf ? ` · ${nf}` : ''}`;
  $('.fbar').classList.toggle('open', !!S.moreF);
  const days = new Map(); for (const it of its) days.set(dayOf(it), (days.get(dayOf(it)) || 0) + 1);
  chipRow($('#days'), [...days.entries()].sort().map(([d, n]) => [d, dayLabel(d).split(' · ')[0], n]), S.day, 'day');
  const pc = new Map(); for (const it of its) for (const p of it.p) pc.set(p, (pc.get(p) || 0) + 1);
  const ps = [...S.persons.values()].filter(p => pc.has(p.id)).sort((a, b) => (b.id === S.myPerson) - (a.id === S.myPerson) || pc.get(b.id) - pc.get(a.id));
  chipRow($('#pchips'), ps.map(p => [p.id, (p.id === S.myPerson ? '🙋 ' : '👤 ') + esc(p.name || '未命名'), pc.get(p.id)]), S.person, 'person');
  const sp = new Map(); for (const it of its) for (const t of special(it)) sp.set(t, (sp.get(t) || 0) + 1);
  chipRow($('#specials'), [...sp.entries()].sort((a, b) => b[1] - a[1]).map(([t, n]) => [t, esc(t), n]), S.special, 'sp');
  const cams = new Map(); for (const it of its) cams.set(camKey(it), (cams.get(camKey(it)) || 0) + 1);
  chipRow($('#cams'), cams.size > 1 ? [...cams.entries()].sort((a, b) => b[1] - a[1]).map(([c, n]) => [c, '📷 ' + esc(c), n]) : [], S.cam, 'cam');
}

function renderTop() {
  const d = S.data;
  const done = d.items.filter(it => it.a).length;
  const p = $('#pipe'); p.hidden = false;
  p.className = 'pipe ' + (d.pipe ? 'on' : 'off');
  p.title = d.pipe ? 'GPU 分析端在线：新照片几分钟内会有标签、人脸、地点' : 'GPU 分析端离线：上传、浏览、下载都不受影响，只是新照片暂时没有 AI 标签';
  p.textContent = `${d.pipe ? '● AI 在线' : '○ AI 离线'} · 已分析 ${done}/${d.items.length}`;
  const me = $('#me'); me.hidden = false; me.textContent = '👤 ' + S.me.name;
}
function renderAll() {
  renderTop(); renderChips(); renderGrid(); renderSel();
  if (S.tab === 'people') renderPeople();
  if (S.tab === 'insight') renderInsight();
}

/* ---------- 搜索 ---------- */
async function runSearch(q, silent) {
  q = q.trim(); S.q = q;
  if (!q) { S.res = null; renderGrid(); return; }
  if (!silent) $('#sum').innerHTML = `<span>🔎 正在找「${esc(q)}」…</span>`;
  try {
    const r = await api('/search?q=' + encodeURIComponent(q));
    if (S.q !== q) return;
    S.res = r;
    S.searches.unshift({ q, took: r.took, cached: r.cached, sem: r.sem, n: r.ids.length });
    S.searches.length = Math.min(S.searches.length, 12);
    if (!silent) renderGrid();
  } catch (e) { toast('搜索失败：' + e.message); }
}
let qTimer;
$('#q').addEventListener('input', e => { clearTimeout(qTimer); const v = e.target.value; qTimer = setTimeout(() => runSearch(v), 450); });
$('#f-search').addEventListener('submit', e => { e.preventDefault(); clearTimeout(qTimer); $('#q').blur(); runSearch($('#q').value); });
async function loadSuggest() {
  try {
    const s = await api('/suggest');
    const sc = (S.data.scenes || []).map(x => x.label).filter(Boolean);
    const words = [...new Set([...s.map(x => x.t), ...sc])].slice(0, 30);
    $('#sugg').innerHTML = words.map(w => `<button class="chip ghost" data-q="${esc(w)}">${esc(w)}</button>`).join('');
  } catch { /* 可有可无 */ }
}

/* ---------- 点击：筛选 chip / 分组 / 瓦片 ---------- */
document.addEventListener('click', e => {
  const t = e.target;
  let b;
  if ((b = t.closest('#quick [data-f]'))) { S.quick = b.dataset.f; if (S.quick === 'all') { S.day = S.person = S.special = S.cam = null; } return renderAll(); }
  if (t.closest('#burst')) { S.burst = !S.burst; return renderAll(); }
  if ((b = t.closest('[data-gp]'))) { S.group = localStorage.np_group = b.dataset.gp; return renderAll(); }
  if (t.closest('#more-f')) { S.moreF = !S.moreF; return renderChips(); }
  if (t.closest('#order')) { S.desc = !S.desc; localStorage.np_desc = S.desc ? '1' : '0'; return renderAll(); }
  if ((b = t.closest('[data-day]'))) { S.day = S.day === b.dataset.day ? null : b.dataset.day; return renderAll(); }
  if ((b = t.closest('[data-person]'))) { const v = Number(b.dataset.person); S.person = S.person === v ? null : v; return renderAll(); }
  if ((b = t.closest('[data-sp]'))) { S.special = S.special === b.dataset.sp ? null : b.dataset.sp; return renderAll(); }
  if ((b = t.closest('[data-cam]'))) { S.cam = S.cam === b.dataset.cam ? null : b.dataset.cam; return renderAll(); }
  if ((b = t.closest('[data-q]'))) { e.preventDefault(); closeLb(); goTab('grid'); $('#q').value = b.dataset.q; return runSearch(b.dataset.q); }
  if (t.closest('#q-x')) { $('#q').value = ''; S.q = ''; S.res = null; return renderGrid(); }
  if (t.closest('#f-x')) { S.quick = 'all'; S.day = S.person = S.special = S.cam = null; return renderAll(); }
  if (t.closest('#dl-all')) return zipDownload(S.view.map(it => it.h), zipName());
  if ((b = t.closest('[data-selg]'))) {
    const g = S.groupsNow.find(g => g.key === b.dataset.selg); if (!g) return;
    S.selMode = true; const all = g.items.every(it => S.sel.has(it.h));
    for (const it of g.items) all ? S.sel.delete(it.h) : S.sel.add(it.h);
    return renderGrid(), renderSel();
  }
  if ((b = t.closest('.tl'))) {
    if (e.metaKey || e.ctrlKey) return;   // 新标签页打开原图
    e.preventDefault();
    const h = b.dataset.h;
    if (S.selMode || e.shiftKey) return toggleSel(h, e.shiftKey, b);
    return openLb(S.view.findIndex(it => it.h === h));
  }
  if ((b = t.closest('[data-tab]'))) return goTab(b.dataset.tab);
});

/* 长按进入多选（手机上的习惯动作） */
let lpTimer = null, lpFired = false;
$('#grid').addEventListener('touchstart', e => {
  const b = e.target.closest('.tl'); if (!b) return;
  lpFired = false;
  lpTimer = setTimeout(() => { lpFired = true; S.selMode = true; toggleSel(b.dataset.h, false, b); navigator.vibrate?.(15); }, 480);
}, { passive: true });
['touchend', 'touchmove', 'touchcancel'].forEach(ev => $('#grid').addEventListener(ev, e => {
  clearTimeout(lpTimer);
  if (lpFired && ev === 'touchend') { e.preventDefault(); lpFired = false; }
}));

/* ---------- 多选 ---------- */
let lastSel = null;
function toggleSel(h, range, el) {
  S.selMode = true;
  if (range && lastSel) {
    const a = S.view.findIndex(it => it.h === lastSel), b = S.view.findIndex(it => it.h === h);
    const [lo, hi] = a < b ? [a, b] : [b, a];
    for (let i = lo; i <= hi; i++) S.sel.add(S.view[i].h);
    renderGrid();
  } else {
    S.sel.has(h) ? S.sel.delete(h) : S.sel.add(h);
    el && el.classList.toggle('on', S.sel.has(h));
  }
  lastSel = h; renderSel();
}
function renderSel() {
  const on = S.selMode && S.tab === 'grid';
  $('#selbar').hidden = !on; document.body.classList.toggle('selmode', on);
  $('#btn-sel').hidden = on || S.tab !== 'grid' || !S.data || !S.data.items.length;
  const n = S.sel.size, sz = [...S.sel].reduce((s, h) => s + (S.byH.get(h)?.s || 0), 0);
  $('#selcount').textContent = n ? `已选 ${n} 个 · ${fmtB(sz)}` : '点照片来选择';
}
$('#btn-sel').onclick = () => { S.selMode = true; renderSel(); };
$('#sel-x').onclick = () => { S.selMode = false; S.sel.clear(); shareReady = null; renderGrid(); renderSel(); };
$('#sel-all').onclick = () => { const all = S.view.every(it => S.sel.has(it.h)); for (const it of S.view) all ? S.sel.delete(it.h) : S.sel.add(it.h); renderGrid(); renderSel(); };
$('#sel-zip').onclick = () => S.sel.size && zipDownload([...S.sel], zipName(S.sel.size));
$('#sel-share').onclick = () => S.sel.size && shareFiles([...S.sel], $('#sel-share'));

/* ================= 下载 ================= */
function zipName(n) {
  const d = S.day ? S.day.slice(5) : S.res ? S.res.q : '';
  return `北欧2026${d ? '-' + d : ''}${n ? `-${n}个` : ''}`;
}
/** 打包下载：Worker 流式拼 zip（只存不压，总长度事先算好 → 浏览器显示真实进度）。一包最多 500 个 */
async function zipDownload(ids, name) {
  if (!ids.length) return;
  if (ids.length === 1) { location.href = F(ids[0], 'o') + '?dl=1'; return; }
  const chunks = []; for (let i = 0; i < ids.length; i += 500) chunks.push(ids.slice(i, i + 500));
  try {
    const urls = [];
    for (let i = 0; i < chunks.length; i++) urls.push((await api('/zip', { method: 'POST', body: { ids: chunks[i], name: chunks.length > 1 ? `${name}-第${i + 1}包` : name } })).url);
    const size = ids.reduce((s, h) => s + (S.byH.get(h)?.s || 0), 0);
    if (urls.length === 1) { location.href = urls[0]; toast(`开始下载 ${ids.length} 个文件（${fmtB(size)}），看浏览器的下载栏`, 5000); }
    else toast(`一共 ${fmtB(size)}，分成 ${urls.length} 包，逐个点：<br>` + urls.map((u, i) => `<a href="${u}">⬇ 第 ${i + 1} 包</a>`).join(' · '), 0);
  } catch (e) { toast('打包失败：' + e.message); }
}

/** 存进手机相册：iOS/安卓的系统分享面板里有「存储 N 个项目」。
 *  分两步是因为 iOS 要求 share() 必须由一次点击直接触发，而下载文件要时间 —— 先下载，再让人点第二下 */
let shareReady = null;
async function shareFiles(ids, btn) {
  if (!navigator.canShare) return toast('这个浏览器不支持直接存相册，用「打包下载」吧');
  if (shareReady && shareReady.key === ids.join()) {
    try { await navigator.share({ files: shareReady.files }); } catch (e) { if (e.name !== 'AbortError') toast('分享失败：' + e.message); }
    shareReady = null; btn.textContent = btn.dataset.l || '📲 存到手机'; return;
  }
  const items = ids.map(h => S.byH.get(h)).filter(Boolean);
  const size = items.reduce((s, it) => s + it.s, 0);
  if (items.length > 60 || size > 800 * 2 ** 20) return toast(`一次最多 60 个 / 800 MB（现在 ${items.length} 个 / ${fmtB(size)}），分几次选，或者用「打包下载」`, 5000);
  btn.dataset.l = btn.dataset.l || btn.textContent;
  const files = []; let got = 0;
  try {
    for (const it of items) {
      btn.textContent = `下载中 ${Math.round(got / size * 100)}%`;
      const b = await (await fetch(F(it.h, 'o'), { credentials: 'same-origin' })).blob();
      got += it.s;
      files.push(new File([b], it.n, { type: b.type || 'application/octet-stream' }));
    }
  } catch (e) { btn.textContent = btn.dataset.l; return toast('下载失败：' + e.message); }
  if (!navigator.canShare({ files })) { btn.textContent = btn.dataset.l; return toast('系统不接受这些文件的分享，用「打包下载」吧'); }
  shareReady = { key: ids.join(), files };
  btn.textContent = '✅ 好了，再点一下保存';
}

/* ================= 大图 ================= */
function openLb(i) {
  if (i < 0 || i >= S.view.length) return;
  S.lb = i; const it = S.view[i];
  $('#lb').hidden = false; document.body.classList.add('lbopen');
  const media = $('#lb-media');
  const poster = it.f & 2 ? F(it.h, 'p') : it.f & 1 ? F(it.h, 't') : '';
  if (it.k === 'v') {
    const src = it.f & 4 ? F(it.h, 'v') : F(it.h, 'o');
    media.innerHTML = `<video controls playsinline autoplay preload="metadata" ${poster ? `poster="${poster}"` : ''} src="${src}"></video>`;
  } else {
    const web = /\.(jpe?g|png|webp|gif|avif)$/i.test(it.n) && it.s < 25 * 2 ** 20;
    const src = it.f & 2 ? F(it.h, 'p') : web ? F(it.h, 'o') : poster;
    media.innerHTML = src ? `<img src="${src}" alt="">` : `<div class="ph0 big">🖼<i>这个格式浏览器显示不了，等 AI 生成预览<br>可以直接下载原图</i></div>`;
  }
  renderLbInfo(it);
  for (const j of [i + 1, i - 1]) { const n = S.view[j]; if (n && n.k === 'i' && n.f & 2) new Image().src = F(n.h, 'p'); }
}
function renderLbInfo(it) {
  const tg = it.tg || {};
  const tags = [...new Set([...(tg.special || []), ...(tg.objects || []), ...(tg.tags || [])])].slice(0, 16);
  const ppl = it.p.map(p => S.persons.get(p)).filter(Boolean);
  const mine = it.u.includes(S.me.id);
  const mo = it.mo != null ? S.moments.get(it.mo) : null;
  const group = it.b ? S.data.items.filter(x => x.b === it.b).sort((a, b) => (b.q ?? -1) - (a.q ?? -1)) : [];
  $('#lb-info').innerHTML = `
    <div class="lb-row"><b>${md(it)}</b>${it.pl ? `<span>📍 ${esc(it.pl)}</span>` : ''}${it.cam ? `<span>📷 ${esc(it.cam)}</span>` : ''}
      <span class="s">${esc(it.n)} · ${fmtB(it.s)}${it.w ? ` · ${it.w}×${it.hh}` : ''}${it.d ? ` · ${fmtD(it.d)}` : ''}</span></div>
    ${mo ? `<div class="lb-row s">${mo.memo >= 4 ? '★ ' : ''}时刻：${esc(mo.title)}</div>` : ''}
    ${it.cap ? `<p class="cap">${esc(it.cap)}</p>` : it.a ? '' : '<p class="s">AI 还没分析这张（分析端在线时几分钟内会有描述、标签和人脸）</p>'}
    <div class="lb-row">上传：${it.u.map(u => esc(S.users.get(u) || '?')).join('、')}
      ${ppl.length ? ` · 照片里：${ppl.map(p => `<button class="chip sm" data-person="${p.id}">${esc(p.name || '未命名')}</button>`).join('')}` : it.nf ? ` · ${it.nf} 张脸（去「人物」认领）` : ''}</div>
    ${tags.length ? `<div class="lb-row">${tags.map(t => `<button class="chip ghost sm" data-q="${esc(t)}">${esc(t)}</button>`).join('')}</div>` : ''}
    ${group.length > 1 ? `<div class="lb-grp"><div class="s">这组 ${group.length} 张几乎一样的，按 AI 打分从高到低 · <b>${it.bc ? (it.pn ? '这张是你挑的' : '这张是 AI 挑的最好的') : '不是这组的封面'}</b></div>
      <div class="strip">${group.map(g => `<button class="st${g.h === it.h ? ' cur' : ''}" data-goto="${g.h}">${g.f & 1 ? `<img src="${F(g.h, 't')}" alt="">` : '🖼'}<i>${g.bc ? '★' : ''}${g.q != null ? Math.round(g.q * 100) : ''}</i></button>`).join('')}</div>
      ${it.bc ? '' : `<button class="btn sm" id="lb-pick">👍 这张更好，设为这组的封面</button>`}</div>` : ''}
    ${it.src ? aiSrcRow(it) : ''}
    <div class="lb-row acts">
      <a class="btn pri sm" href="${F(it.h, 'o')}?dl=1">⬇ 下载原${it.k === 'v' ? '视频' : '图'}</a>
      <button class="btn sm" id="lb-share">📲 存到手机</button>
      <button class="btn sm" id="lb-sel">${S.sel.has(it.h) ? '✓ 已选' : '选中'}</button>
      ${it.k === 'v' && it.f & 4 ? `<button class="btn ghost sm" id="lb-orig">看原画质</button>` : ''}
      ${it.k === 'i' && S.data.ai && S.data.ai.length ? `<button class="btn sm" id="lb-ai">✨ AI 改图</button>` : ''}
      ${mine ? `<button class="btn ghost sm danger" id="lb-del">撤回我的上传</button>` : ''}
    </div>
    <div id="lb-aied"></div>`;
  const job = [...S.edits.values()].find(j => j.h === it.h && !j.over);
  if (job) aiPanel(it, job);
}

/* ================= AI 改图 =================
 * 原图不动：改好的图作为一张新照片存进相册（拍摄时间/地点沿用原图，所以就排在原图旁边）。
 * 模型是 GPU 端经公司模型网关调的 —— 分析端离线时按钮不出现。 */
const AI_MODELS = {
  nano: ['Nano Banana 2', '约 10 秒 · 默认'],
  pro: ['Nano Banana Pro', '约 20 秒 · 细节更好'],
  gpt: ['GPT Image 2', '约 35 秒 · OpenAI'],
};
const AI_PRESETS = ['把天空换成绚丽的极光', '把天空换成金色的晚霞', '去掉背景里的路人', '变成油画风格', '变成吉卜力动画风格', '变成冬天下雪的样子'];
S.edits = new Map();
function aiSrcRow(it) {
  const src = S.byH.get(it.src), ai = it.ai || {};
  return `<div class="lb-row aisrc">✨ AI 编辑自 ${src ? `<button class="chip sm" data-goto="${it.src}">原图</button>` : '（原图已删除）'}
    <span>「${esc(ai.p || '')}」</span><span class="s">${esc((AI_MODELS[ai.m] || [ai.m])[0] || '')}${ai.by != null && S.users.get(ai.by) ? ` · ${esc(S.users.get(ai.by))} 改的` : ''}</span>
    ${src && src.f & 2 ? `<button class="btn ghost sm" id="lb-cmp">按住看原图</button>` : ''}</div>`;
}
function aiPanel(it, job) {
  const box = $('#lb-aied'); if (!box) return;
  const keys = (S.data.ai || []).filter(k => AI_MODELS[k]);
  const m0 = keys.includes(localStorage.np_aim) ? localStorage.np_aim : keys[0];
  if (job) {
    const sec = Math.round((Date.now() - job.t0) / 1000);
    const st = job.status === 'queued' ? (job.ahead ? `排队中，前面还有 ${job.ahead} 张` : '排队中') : job.status === 'running' ? '正在改…' : '';
    box.innerHTML = `<div class="aied"><div class="lb-row"><span class="spin"></span><b>${st}</b><span class="s">${sec} 秒 · ${esc((AI_MODELS[job.model] || [''])[0])} · 「${esc(job.prompt)}」</span></div>
      <div class="s">可以先去看别的照片，好了会提示你。</div></div>`;
    return;
  }
  box.innerHTML = `<div class="aied">
    <textarea id="ai-p" rows="2" maxlength="400" placeholder="说一句话，比如：把天空换成极光 / 去掉右边那个路人 / 变成水彩画"></textarea>
    <div class="lb-row">${AI_PRESETS.map(p => `<button class="chip ghost sm" data-aip="${esc(p)}">${esc(p)}</button>`).join('')}</div>
    <div class="lb-row">${keys.map(k => `<label class="aim"><input type="radio" name="ai-m" value="${k}"${k === m0 ? ' checked' : ''}> ${AI_MODELS[k][0]} <span class="s">${AI_MODELS[k][1]}</span></label>`).join('')}</div>
    <div class="lb-row"><button class="btn pri sm" id="ai-go">✨ 开始改</button>
      <span class="s">原图不动，改好的会作为新照片存进相册 · 图片会经公司的模型网关发给 Google / OpenAI 处理</span></div>
  </div>`;
  $('#ai-p').focus();
}
async function aiGo(it, btn) {
  const prompt = $('#ai-p').value.trim();
  const model = (document.querySelector('input[name="ai-m"]:checked') || {}).value;
  if (!prompt) { toast('先说一下要怎么改'); $('#ai-p').focus(); return; }
  localStorage.np_aim = model;
  btn.disabled = true;
  let r;
  try { r = await api('/edit', { method: 'POST', body: { h: it.h, prompt, model } }); }
  catch (e) { btn.disabled = false; toast(e.message, 4000); return; }
  const job = { ...r, t0: Date.now() };
  S.edits.set(r.id, job);
  aiPanel(it, job);
  aiPoll(job);
}
async function aiPoll(job) {
  while (!job.over) {
    await new Promise(r => setTimeout(r, 2000));
    let r;
    try { r = await api('/edit?id=' + job.id); } catch { continue; }
    Object.assign(job, r);
    const cur = S.view[S.lb];
    const here = !$('#lb').hidden && cur && cur.h === job.h;
    if (r.status === 'done') {
      job.over = true;
      await refresh(true);
      const out = S.byH.get(r.out_h);
      if (here && out) {
        // refresh 可能重排了当前视图：新照片在视图里就直接跳过去，不在（被筛选掉了）就临时插到原图后面
        let i = S.view.findIndex(x => x.h === out.h);
        if (i < 0) { i = Math.max(0, S.view.findIndex(x => x.h === job.h)) + 1; S.view.splice(i, 0, out); }
        openLb(i); toast('✨ 改好了 —— 这张是新照片，原图还在');
      }
      else toast('✨ 有一张照片改好了，就排在原图旁边', 4000);
    } else if (r.status === 'error') {
      job.over = true;
      if (here) { aiPanel(cur); $('#ai-p').value = job.prompt; }
      toast('没改成：' + (r.err || '未知原因'), 6000);
    } else if (here) aiPanel(cur, job);
  }
}
function closeLb() {
  if ($('#lb').hidden) return;
  $('#lb').hidden = true; $('#lb-media').innerHTML = ''; document.body.classList.remove('lbopen'); S.lb = -1;
}
$('#lb-x').onclick = closeLb;
$('#lb-prev').onclick = () => openLb(S.lb - 1);
$('#lb-next').onclick = () => openLb(S.lb + 1);
$('#lb').addEventListener('click', async e => {
  const t = e.target, it = S.view[S.lb]; if (!it) return;
  if (t === $('#lb') || t === $('#lb-media')) return closeLb();
  let b;
  if ((b = t.closest('[data-goto]'))) {
    const i = S.view.findIndex(x => x.h === b.dataset.goto);
    if (i >= 0) return openLb(i);
    // 被「收起连拍」藏起来的那几张不在当前视图里 —— 临时插到当前位置
    S.view.splice(S.lb + 1, 0, S.byH.get(b.dataset.goto)); return openLb(S.lb + 1);
  }
  if (t.closest('[data-person]')) closeLb();
  if (t.id === 'lb-share') return shareFiles([it.h], t);
  if (t.id === 'lb-ai') return $('#ai-p') ? ($('#lb-aied').innerHTML = '') : aiPanel(it);
  if ((b = t.closest('[data-aip]'))) { $('#ai-p').value = b.dataset.aip; return; }
  if (t.id === 'ai-go') return aiGo(it, t);
  if (t.id === 'lb-sel') { S.selMode = true; toggleSel(it.h); renderGrid(); t.textContent = S.sel.has(it.h) ? '✓ 已选' : '选中'; return; }
  if (t.id === 'lb-orig') { const v = $('#lb-media video'); const pos = v.currentTime; v.src = F(it.h, 'o'); v.currentTime = pos; v.play(); t.remove(); return; }
  if (t.id === 'lb-pick') { await api('/pick', { method: 'POST', body: { h: it.h } }); toast('好，以后这组就显示这张'); await refresh(true); const i = S.view.findIndex(x => x.h === it.h); return i >= 0 ? openLb(i) : closeLb(); }
  if (t.id === 'lb-del') {
    if (!confirm(it.u.length > 1 ? '撤回你的上传？（别人也传过这张，所以它会留在相册里）' : '撤回你的上传？这张会从相册里消失。')) return;
    const r = await api('/delete', { method: 'POST', body: { h: it.h } });
    toast(r.hidden ? '已删除' : '已撤回（别人也传过，照片还在）'); closeLb(); refresh(true);
  }
});
document.addEventListener('keydown', e => {
  if ($('#lb').hidden) { if (e.key === 'Escape' && S.selMode) $('#sel-x').click(); return; }
  if (e.key === 'Escape') closeLb();
  if (e.key === 'ArrowLeft') openLb(S.lb - 1);
  if (e.key === 'ArrowRight') openLb(S.lb + 1);
});
// 「按住看原图」：按下换成原图的预览，松开换回来（手机上长按也一样）
$('#lb').addEventListener('pointerdown', e => {
  if (e.target.id !== 'lb-cmp') return;
  const it = S.view[S.lb], img = $('#lb-media img'); if (!it || !img) return;
  const back = img.src; img.src = F(it.src, 'p'); e.target.textContent = '松开看改后的';
  const up = () => { img.src = back; e.target.textContent = '按住看原图'; removeEventListener('pointerup', up); removeEventListener('pointercancel', up); };
  addEventListener('pointerup', up); addEventListener('pointercancel', up);
});
let tx = null, ty = null;
$('#lb-media').addEventListener('touchstart', e => { tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, { passive: true });
$('#lb-media').addEventListener('touchend', e => {
  if (tx == null) return;
  const dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty; tx = null;
  if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) openLb(S.lb + (dx < 0 ? 1 : -1));
  else if (dy > 90 && Math.abs(dy) > Math.abs(dx) * 1.5) closeLb();
});

/* ================= 人物 ================= */
/** 人脸头像：用 CSS 背景定位从预览图里裁出一个正方形（不另外存头像文件）。坐标是 0–1 的相对值 */
function faceDiv(f, cls = 'fc') {
  const it = S.byH.get(f.h) || {};
  const W = it.w || 1, H = it.hh || 1;
  const side = Math.max(f.w * W, f.hh * H) * 1.6;
  const sw = Math.min(1, side / W), sh = Math.min(1, side / H);
  const cx = f.x + f.w / 2, cy = f.y + f.hh / 2;
  const x0 = Math.min(Math.max(cx - sw / 2, 0), 1 - sw), y0 = Math.min(Math.max(cy - sh / 2, 0), 1 - sh);
  const src = it.f & 2 ? F(f.h, 'p') : F(f.h, 't');
  const px = sw >= 1 ? 50 : x0 / (1 - sw) * 100, py = sh >= 1 ? 50 : y0 / (1 - sh) * 100;
  return `<span class="${cls}" data-face="${f.id}" data-fh="${f.h}" style="background-image:url('${src}');background-size:${100 / sw}% ${100 / sh}%;background-position:${px}% ${py}%"></span>`;
}
async function renderPeople() {
  const el = $('#people');
  if (!el.innerHTML) el.innerHTML = '<p class="s">加载中…</p>';
  let d; try { d = await api('/people'); } catch (e) { el.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
  S.peopleData = d;
  const iAmKnown = d.persons.some(p => p.uid === S.me.id);
  const opts = d.persons.map(p => `<option value="${p.id}">${esc(p.name || '未命名')}</option>`).join('');
  el.innerHTML = `
    ${d.persons.length ? `<h3>已认出的人</h3><div class="pgrid">${d.persons.map(p => `
      <div class="pcard${p.uid === S.me.id ? ' me' : ''}">
        <div class="faces">${p.faces.map(f => `<span class="fw">${faceDiv(f)}<button class="fx" data-unassign="${f.id}" title="这张不是 TA">✕</button></span>`).join('')}</div>
        <div class="pn"><b>${esc(p.name || '未命名')}</b>${p.uid === S.me.id ? ' <span class="badge ok">就是你</span>' : ''}<span class="s">${p.n} 张</span></div>
        <div class="pa"><button class="btn sm pri" data-see="${p.id}">看 TA 的照片</button><button class="btn sm ghost" data-rename="${p.id}">改名</button></div>
      </div>`).join('')}</div>` : ''}
    <h3>${d.persons.length ? '还没认领的脸' : 'AI 找到的脸（按长相分组）'}</h3>
    ${d.clusters.length ? `<div class="pgrid">${d.clusters.map(c => `
      <div class="pcard">
        <div class="faces">${c.faces.map(f => faceDiv(f)).join('')}</div>
        <div class="pn"><span class="s">同一个人 · ${c.n} 张照片</span></div>
        <div class="pa">
          ${iAmKnown ? '' : `<button class="btn sm pri" data-claim="${c.id}" data-me="1">🙋 这是我</button>`}
          ${d.persons.length ? `<select data-merge="${c.id}"><option value="">是…</option>${opts}</select>` : ''}
          <button class="btn sm ghost" data-claim="${c.id}" data-new="1">起个名字</button>
        </div>
      </div>`).join('')}</div>` : `<p class="s">${S.data.pipe ? '还没有足够的人脸（同一个人至少出现在 2 张照片里才会成组）。' : 'AI 分析端离线 —— 上线后会自动找脸、分组。'}</p>`}
    ${d.loose ? `<p class="s">另有 ${d.loose} 张零散的脸（只出现一次，或者被标成「不是 TA」）。</p>` : ''}`;
}
$('#people').addEventListener('click', async e => {
  const t = e.target;
  const ok = async (p, body, msg) => { await api(p, { method: 'POST', body }); toast(msg); await refresh(true); renderPeople(); };
  try {
    if (t.dataset.claim) {
      if (t.dataset.me) return ok('/people/claim', { cluster: Number(t.dataset.claim), me: 1 }, '好！「⭐ 与我相关」现在包括所有拍到你的照片了');
      const name = prompt('这个人叫什么？'); if (!name) return;
      return ok('/people/claim', { cluster: Number(t.dataset.claim), name }, `已命名为「${name}」`);
    }
    if (t.dataset.unassign) return ok('/people/unassign', { face: Number(t.dataset.unassign) }, '已移出，以后不会再自动归给 TA');
    if (t.dataset.rename) { const name = prompt('新名字'); if (!name) return; return ok('/people/rename', { person: Number(t.dataset.rename), name }, '已改名'); }
    if (t.dataset.see) { S.person = Number(t.dataset.see); S.quick = 'all'; goTab('grid'); return renderAll(); }
    const f = t.closest('[data-fh]');
    if (f) { const i = S.data.items.findIndex(x => x.h === f.dataset.fh); if (i >= 0) { S.view = [S.data.items[i]]; openLb(0); } }
  } catch (err) { toast(err.message); }
});
$('#people').addEventListener('change', async e => {
  const s = e.target.closest('[data-merge]'); if (!s || !s.value) return;
  await api('/people/claim', { method: 'POST', body: { cluster: Number(s.dataset.merge), person: Number(s.value) } });
  toast('已归到 ' + s.selectedOptions[0].textContent); await refresh(true); renderPeople();
});

/* ================= 分析 ================= */
function bars(rows, attr) {
  const max = Math.max(1, ...rows.map(r => r[2]));
  return `<div class="bars">${rows.map(([k, label, n, extra]) => `<button class="brow" ${attr ? `data-${attr}="${esc(k)}"` : ''}>
    <span class="bl">${label}</span><span class="bb"><i style="width:${n / max * 100}%"></i></span><span class="bn">${n}${extra || ''}</span></button>`).join('')}</div>`;
}
async function renderInsight() {
  const d = S.data, its = d.items;
  let st = {}; try { st = await api('/stats'); } catch { /* 下面用本地数 */ }
  const count = f => { const m = new Map(); for (const it of its) for (const k of [].concat(f(it))) if (k != null) m.set(k, (m.get(k) || 0) + 1); return [...m.entries()]; };
  const up = count(it => it.u).sort((a, b) => b[1] - a[1]).map(([u, n]) => [u, esc(S.users.get(u) || '?'), n]);
  const days = count(dayOf).sort().map(([k, n]) => [k, dayLabel(k), n]);
  const places = count(placeKey).sort((a, b) => b[1] - a[1]).slice(0, 12).map(([k, n]) => [k, esc(k), n]);
  const cams = count(camKey).sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, esc(k), n]);
  const sp = count(special).sort((a, b) => b[1] - a[1]).map(([k, n]) => [k, esc(k), n]);
  const bursts = new Set(its.filter(it => it.b).map(it => it.b)).size, inB = its.filter(it => it.b).length;
  const hl = its.filter(isHL).length;
  const moms = [...S.moments.values()].sort((a, b) => (b.memo || 0) - (a.memo || 0) || b.n - a.n).slice(0, 12);
  const k = localStorage.np_k;
  $('#insight').innerHTML = `
    <div class="stats">
      <div><div class="v">${its.filter(x => x.k === 'i').length}</div><div class="k">照片</div></div>
      <div><div class="v">${its.filter(x => x.k === 'v').length}</div><div class="k">视频</div></div>
      <div><div class="v">${fmtB(its.reduce((s, x) => s + x.s, 0))}</div><div class="k">原画质总量</div></div>
      <div><div class="v">${its.filter(x => x.a).length}/${its.length}</div><div class="k">AI 已分析 · ${d.pipe ? '<span class="ok">在线</span>' : '离线'}</div></div>
      <div><div class="v">${st.faces ?? '—'}</div><div class="k">张脸 → ${d.persons.length} 个已认出的人</div></div>
      <div><div class="v">${bursts}</div><div class="k">组相似照片（${inB} 张，每组 AI 挑出最好的一张）</div></div>
      <div><div class="v">${hl}</div><div class="k">张精选（极光/合影/日落…）</div></div>
      <div><div class="v">${st.qvecs ?? '—'}</div><div class="k">个搜索词向量已缓存 · 结果缓存 ${st.rcache ?? '—'} 条</div></div>
    </div>
    ${k ? `<p class="s" style="margin-top:14px">邀请同伴：<button class="chip" id="inv">复制邀请链接</button>（链接里带口令，点开直接进，只发到群里）</p>` : ''}
    <div class="cols">
      <div><h3>每天</h3>${bars(days, 'day')}</div>
      <div><h3>谁传的</h3>${bars(up)}<h3>设备</h3>${bars(cams, 'cam')}</div>
      <div><h3>地点</h3>${places.length ? bars(places) : '<p class="s">等 AI 查地名</p>'}</div>
      <div><h3>精选类别</h3>${sp.length ? bars(sp, 'sp') : '<p class="s">等 AI 分析</p>'}
        ${moms.length ? `<h3>值得纪念的时刻</h3><ol class="moms">${moms.map(m => `<li>${m.memo >= 4 ? '★ ' : ''}${esc(m.title)} <span class="s">${m.start ? dayLabel(m.start.slice(0, 10)).split(' · ')[0] : ''} · ${m.n} 张</span></li>`).join('')}</ol>` : ''}</div>
      <div><h3>场景聚类</h3>${(d.scenes || []).length ? `<div class="chips wrapc">${d.scenes.map(s => `<button class="chip" data-q="${esc(s.label)}">${esc(s.label)} <i>${s.n}</i></button>`).join('')}</div>` : '<p class="s">等 AI 分析</p>'}
        <h3>这次打开以来的搜索</h3>${S.searches.length ? `<table class="mini"><tr><th>词</th><th>结果</th><th>耗时</th><th></th></tr>${S.searches.map(s => `<tr><td>${esc(s.q)}</td><td>${s.n}</td><td>${s.took} ms</td><td class="s">${s.cached ? '缓存' : s.sem ? '语义' : '关键词'}</td></tr>`).join('')}</table>` : '<p class="s">还没搜过</p>'}</div>
    </div>`;
  const inv = $('#inv');
  if (inv) inv.onclick = async () => {
    const u = `${location.origin}/photos/#k=${encodeURIComponent(k)}`;
    try { await navigator.clipboard.writeText(u); toast('已复制，发到群里就行'); } catch { prompt('复制这个链接', u); }
  };
}
$('#insight').addEventListener('click', e => { if (e.target.closest('[data-day],[data-cam],[data-sp]')) goTab('grid'); });

/* ================= 标签页 ================= */
function goTab(t) {
  S.tab = t;
  $$('.tabs [data-tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === t)));
  for (const n of ['grid', 'people', 'insight']) $('#tab-' + n).hidden = n !== t;
  if (t === 'people') renderPeople();
  if (t === 'insight') renderInsight();
  renderSel();
}
$('#me').onclick = async () => {
  if (!confirm(`当前身份：${S.me.name}\n退出登录？`)) return;
  await fetch(API + '/logout', { credentials: 'same-origin' }); location.reload();
};

/* ================= 上传 =================
 * 一个文件的一生：指纹 → init（服务端判断秒传 / 续传 / 新传）→ 缩略图（和分块并行）→ 分块 → complete
 * 本机记住每个文件的指纹（按 名字|大小|修改时间），所以重选同一批文件时，已经传完的瞬间跳过、
 * 传一半的直接从缺的那块接着传 —— 这就是「断点续传」在网页上的做法（网页不能自己在后台重新打开文件）。
 */
const UQ = [];
let running = 0;
const MAXF = 3, MAXP = 3;
const fkey = f => `${f.name}|${f.size}|${f.lastModified}`;
const FP = {
  all() { try { return JSON.parse(localStorage.np_fp || '{}'); } catch { return {}; } },
  get(k) { return this.all()[k] || null; },
  put(k, v) {
    const a = this.all(); a[k] = { ...(a[k] || {}), ...v, at: Date.now() };
    const ks = Object.keys(a); if (ks.length > 4000) ks.sort((x, y) => a[x].at - a[y].at).slice(0, ks.length - 4000).forEach(x => delete a[x]);
    try { localStorage.np_fp = JSON.stringify(a); } catch { /* 满了就不记，下次重算 */ }
  },
  del(k) { const a = this.all(); delete a[k]; localStorage.np_fp = JSON.stringify(a); },
};
const MEDIA_EXT = /\.(jpe?g|png|webp|gif|avif|heic|heif|dng|tiff?|raw|arw|cr2|cr3|nef|orf|rw2|raf|mov|mp4|m4v|3gp|mkv|avi|webm|insv|insp)$/i;

function enqueue(files) {
  let add = 0, skip = 0, same = 0, again = 0;
  for (const f of files) {
    if (!f.size || !(/^(image|video)\//.test(f.type) || MEDIA_EXT.test(f.name))) { skip++; continue; }
    const key = fkey(f);
    const old = UQ.find(t => t.key === key);
    if (old) { if (old.state === 'failed') { old.state = 'queued'; old.f = f; again++; } else same++; continue; }
    UQ.push({ f, key, state: 'queued', sent: 0, msg: '排队中' }); add++;
  }
  if (skip || same) toast([skip && `跳过 ${skip} 个不是照片/视频的文件`, same && `${same} 个这次已经选过了，不重复传`].filter(Boolean).join(' · '));
  if (add || again) { openSheet(); pump(); }
  renderUp();
}
function pump() {
  while (running < MAXF) {
    const t = UQ.find(t => t.state === 'queued'); if (!t) break;
    running++; t.state = 'active'; t.t0 = Date.now();
    runTask(t).catch(e => { t.state = 'failed'; t.msg = '失败：' + e.message + ' · 点这行重试'; })
      .finally(() => { running--; renderUp(); pump(); });
  }
  wake(); renderUp();
}

async function retry(fn, t) {
  for (let i = 0; ; i++) {
    try { return await fn(); } catch (e) {
      if (e.status && e.status >= 400 && e.status < 500 && ![408, 425, 429].includes(e.status)) throw e;
      if (i >= 30) throw e;
      if (!navigator.onLine) { t.msg = '断网了，联网后自动继续'; renderUpSoon(); await new Promise(r => addEventListener('online', r, { once: true })); }
      else { const w = Math.min(30, 2 ** i); t.msg = `${e.message}，${w} 秒后重试（第 ${i + 1} 次）`; renderUpSoon(); await sleep(w * 1000); }
    }
  }
}

async function runTask(t) {
  const f = t.f;
  let fp = FP.get(t.key);
  if (!fp || !fp.h) {
    t.msg = '计算指纹…';
    fp = await fingerprint(f, p => { t.msg = `计算指纹 ${Math.round(p * 100)}%`; renderUpSoon(); });
    FP.put(t.key, fp);
  }
  t.h = fp.h;
  const ex = /^image\/jpe?g$/i.test(f.type) || /\.jpe?g$/i.test(f.name) ? await readExif(f).catch(() => ({})) : {};
  const meta = {
    h: fp.h, size: f.size, name: f.name, type: f.type || guessType(f.name), crc: fp.crc,
    taken: ex.taken || localIso(f.lastModified), lat: ex.lat, lon: ex.lon, cam: ex.cam,
  };
  let r, tries = 0;
  for (;;) {
    t.msg = '和相册对一下…';
    r = await retry(() => api('/upload/init', { method: 'POST', body: meta }), t);
    if (r.status !== 'wait') break;
    t.msg = '另一台设备正在传同一个文件，等一下…'; renderUpSoon(); await sleep(3000);
    if (++tries > 40) throw new Error('等太久了');
  }
  if (r.status === 'exists') { t.state = 'dup'; t.sent = f.size; t.msg = '相册里已经有了（秒传）'; FP.put(t.key, { done: 1 }); listSoon(); return; }
  FP.put(t.key, { u: 1, name: f.name });
  const thumbs = fp.tb ? Promise.resolve() : makeAux(t, fp).catch(() => { /* GPU 端会补 */ });
  const psize = r.psize, n = r.nparts;
  const done = new Set(r.done);
  for (let round = 0; round < 3; round++) {
    const todo = []; for (let i = 1; i <= n; i++) if (!done.has(i)) todo.push(i);
    const partLen = i => i < n ? psize : f.size - psize * (n - 1);
    let base = [...done].reduce((s, i) => s + partLen(i), 0);
    const inflight = new Map();
    const prog = () => { t.sent = base + [...inflight.values()].reduce((a, b) => a + b, 0); renderUpSoon(); };
    if (done.size) t.resumed = done.size;
    t.msg = done.size ? `接着传（已有 ${done.size}/${n} 块）` : '上传中';
    let next = 0;
    const worker = async () => {
      while (next < todo.length) {
        const i = todo[next++];
        const blob = f.slice((i - 1) * psize, (i - 1) * psize + partLen(i));
        const hdr = fp.shas && fp.shas[i - 1] ? { 'x-part-sha256': fp.shas[i - 1] } : {};
        await retry(() => xput(`${API}/upload/part?h=${fp.h}&n=${i}`, blob, hdr, l => { inflight.set(i, l); prog(); }), t);
        inflight.delete(i); base += partLen(i); done.add(i); prog();
        t.msg = n > 1 ? `上传中 ${done.size}/${n} 块` : '上传中';
      }
    };
    await Promise.all(Array.from({ length: Math.min(MAXP, todo.length) }, worker));
    t.msg = '收尾…';
    const c = await retry(() => api('/upload/complete', { method: 'POST', body: { h: fp.h } }), t);
    if (c.status === 'done' || c.status === 'exists') {
      await thumbs;
      t.state = 'ok'; t.sent = f.size; t.msg = t.resumed ? `完成（断点续传，省了 ${t.resumed} 块）` : '完成';
      FP.put(t.key, { u: 0, done: 1 }); listSoon(); return;
    }
    if (c.status === 'missing') { done.clear(); c.done.forEach(x => done.add(x)); continue; }
    if (c.status === 'corrupt') { FP.del(t.key); throw new Error('文件在传输中损坏了，重新计算指纹再传一次'); }
    throw new Error('未知状态 ' + c.status);
  }
  throw new Error('几块一直传不上去');
}

function xput(url, body, headers, onprog) {
  return new Promise((res, rej) => {
    const x = new XMLHttpRequest();
    x.open('PUT', url); x.withCredentials = true; x.timeout = 10 * 60e3;
    for (const [k, v] of Object.entries(headers || {})) x.setRequestHeader(k, v);
    x.upload.onprogress = e => onprog && onprog(e.loaded);
    x.onload = () => {
      let j = null; try { j = JSON.parse(x.responseText); } catch { /* */ }
      if (x.status >= 200 && x.status < 300) res(j); else rej(new ApiErr(x.status, (j && j.error) || 'HTTP ' + x.status));
    };
    x.onerror = () => rej(new ApiErr(0, '网络中断'));
    x.ontimeout = () => rej(new ApiErr(0, '超时'));
    x.send(body);
  });
}

/* ---------- 指纹：逐块 SHA-256 + 整份 CRC32（给 zip 用） ---------- */
const CRC_T = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(u8, crc) {
  let c = ~crc >>> 0;
  for (let i = 0; i < u8.length; i++) c = CRC_T[(c ^ u8[i]) & 0xFF] ^ (c >>> 8);
  return ~c >>> 0;
}
const hexOf = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
async function fingerprint(f, onp) {
  const n = Math.max(1, Math.ceil(f.size / PART));
  const cat = new Uint8Array(n * 32), shas = [];
  let crc = 0;
  for (let i = 0; i < n; i++) {
    const buf = await f.slice(i * PART, Math.min(f.size, (i + 1) * PART)).arrayBuffer();
    const d = await crypto.subtle.digest('SHA-256', buf);
    cat.set(new Uint8Array(d), i * 32); shas.push(hexOf(d));
    crc = crc32(new Uint8Array(buf), crc);
    onp((i + 1) / n);
  }
  return { h: hexOf(await crypto.subtle.digest('SHA-256', cat)), crc, shas: n > 1 ? shas : undefined };
}
function guessType(n) {
  const e = (n.split('.').pop() || '').toLowerCase();
  return { heic: 'image/heic', heif: 'image/heif', mov: 'video/quicktime', mp4: 'video/mp4', m4v: 'video/mp4', dng: 'image/x-adobe-dng', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png' }[e] || 'application/octet-stream';
}

/* ---------- EXIF（只读 JPEG 开头 256 KB）：拍摄时间、GPS、相机 ---------- */
async function readExif(f) {
  const v = new DataView(await f.slice(0, 256 * 1024).arrayBuffer());
  if (v.getUint16(0) !== 0xFFD8) return {};
  let o = 2;
  while (o + 4 < v.byteLength) {
    const mk = v.getUint16(o), len = v.getUint16(o + 2);
    if (mk === 0xFFE1 && v.getUint32(o + 4) === 0x45786966) return parseTiff(v, o + 10);
    if ((mk & 0xFF00) !== 0xFF00 || mk === 0xFFDA) break;
    o += 2 + len;
  }
  return {};
}
function parseTiff(v, T) {
  const le = v.getUint16(T) === 0x4949;
  const u16 = p => v.getUint16(p, le), u32 = p => v.getUint32(p, le);
  const str = (p, n) => { let s = ''; for (let i = 0; i < n; i++) { const c = v.getUint8(p + i); if (!c) break; s += String.fromCharCode(c); } return s.trim(); };
  const ifd = p => {
    const out = {}; const n = u16(T + p);
    for (let i = 0; i < n; i++) {
      const e = T + p + 2 + i * 12, tag = u16(e), type = u16(e + 2), cnt = u32(e + 4);
      const sz = [0, 1, 1, 2, 4, 8, 1, 1, 2, 4, 8, 4, 8][type] * cnt;
      const vp = sz > 4 ? T + u32(e + 8) : e + 8;
      if (vp + sz > v.byteLength) continue;
      if (type === 2) out[tag] = str(vp, cnt);
      else if (type === 3) out[tag] = u16(vp);
      else if (type === 4) out[tag] = u32(vp);
      else if (type === 5) out[tag] = Array.from({ length: cnt }, (_, k) => u32(vp + k * 8) / (u32(vp + k * 8 + 4) || 1));
      else if (type === 1 || type === 7) out[tag] = v.getUint8(vp);
    }
    return out;
  };
  const r = {};
  const i0 = ifd(u32(T + 4));
  const make = i0[0x010F] || '', model = i0[0x0110] || '';
  if (model) r.cam = model.toLowerCase().startsWith(make.split(' ')[0].toLowerCase()) || !make ? model : `${make.split(' ')[0]} ${model}`;
  let dt = i0[0x0132];
  if (i0[0x8769]) { const ex = ifd(i0[0x8769]); dt = ex[0x9003] || ex[0x9004] || dt; }
  const m = /^(\d{4}):(\d\d):(\d\d) (\d\d):(\d\d):(\d\d)/.exec(dt || '');
  if (m && m[1] !== '0000') r.taken = `${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}`;
  if (i0[0x8825]) {
    const g = ifd(i0[0x8825]);
    const dms = a => Array.isArray(a) && a.length === 3 ? a[0] + a[1] / 60 + a[2] / 3600 : null;
    const la = dms(g[2]), lo = dms(g[4]);
    if (la != null && lo != null && (la || lo)) { r.lat = g[1] === 'S' ? -la : la; r.lon = g[3] === 'W' ? -lo : lo; }
  }
  return r;
}

/* ---------- 缩略图 / 预览图：浏览器自己能解码的就当场做，最快出图；做不了的（HEIC 在 Chrome 上等）GPU 端补 ---------- */
async function decode(f, kind) {
  if (kind === 'v') return videoFrame(f);
  try { const b = await createImageBitmap(f, { imageOrientation: 'from-image' }); return { src: b, W: b.width, H: b.height, close: () => b.close() }; } catch { /* 走 <img> */ }
  const url = URL.createObjectURL(f);
  try { const img = new Image(); img.src = url; await img.decode(); return { src: img, W: img.naturalWidth, H: img.naturalHeight, close: () => URL.revokeObjectURL(url) }; }
  catch { URL.revokeObjectURL(url); return null; }
}
function videoFrame(f) {
  return new Promise(res => {
    const v = document.createElement('video'), url = URL.createObjectURL(f);
    v.muted = true; v.playsInline = true; v.preload = 'auto';
    let fin = false;
    const done = r => { if (fin) return; fin = true; clearTimeout(to); res(r); if (!r) URL.revokeObjectURL(url); };
    const to = setTimeout(() => done(null), 8000);
    v.onloadedmetadata = () => { v.currentTime = Math.min(1, (v.duration || 0) / 3); };
    v.onseeked = () => v.videoWidth ? done({ src: v, W: v.videoWidth, H: v.videoHeight, dur: v.duration, close: () => { v.removeAttribute('src'); v.load(); URL.revokeObjectURL(url); } }) : done(null);
    v.onerror = () => done(null);
    v.src = url;
  });
}
function canvasOf(src, W, H, scale) {
  const c = document.createElement('canvas');
  c.width = Math.max(1, Math.round(W * scale)); c.height = Math.max(1, Math.round(H * scale));
  const g = c.getContext('2d'); g.imageSmoothingQuality = 'high'; g.drawImage(src, 0, 0, c.width, c.height);
  return c;
}
const jpeg = (c, q) => new Promise(r => c.toBlob(r, 'image/jpeg', q));
async function makeAux(t, fp) {
  const kind = /^video\//.test(t.f.type) || /\.(mov|mp4|m4v|3gp|mkv|avi|webm)$/i.test(t.f.name) ? 'v' : 'i';
  const d = await decode(t.f, kind);
  if (!d || !d.W) return;
  try {
    const pc = canvasOf(d.src, d.W, d.H, Math.min(1, 1600 / Math.max(d.W, d.H)));
    const tc = canvasOf(pc, pc.width, pc.height, Math.min(1, 360 / Math.min(pc.width, pc.height)));
    const [pb, tb] = [await jpeg(pc, 0.82), await jpeg(tc, 0.75)];
    const dims = `&w=${d.W}&hh=${d.H}${d.dur ? `&dur=${d.dur.toFixed(2)}` : ''}`;
    if (tb) await retry(() => xput(`${API}/upload/aux?h=${fp.h}&k=t${dims}`, tb), t);
    if (pb) await retry(() => xput(`${API}/upload/aux?h=${fp.h}&k=p`, pb), t);
    FP.put(t.key, { tb: 1 });
  } finally { d.close && d.close(); }
}

/* ---------- 上传面板 ---------- */
let upRaf = 0;
function renderUpSoon() { if (!upRaf) upRaf = requestAnimationFrame(() => { upRaf = 0; renderUp(); }); }
function renderUp() {
  const tot = UQ.reduce((s, t) => s + t.f.size, 0), sent = UQ.reduce((s, t) => s + (t.sent || 0), 0);
  const ok = UQ.filter(t => t.state === 'ok').length, dup = UQ.filter(t => t.state === 'dup').length;
  const bad = UQ.filter(t => t.state === 'failed').length, act = UQ.filter(t => t.state === 'active' || t.state === 'queued').length;
  const now = Date.now();
  if (!renderUp.s || now - renderUp.s.t > 1500) { const s0 = renderUp.s; renderUp.s = { t: now, b: sent, rate: s0 ? Math.max(0, (sent - s0.b) / ((now - s0.t) / 1000)) : 0 }; }
  const rate = renderUp.s.rate;
  const line = UQ.length ? `${ok + dup}/${UQ.length} 完成${dup ? ` · ${dup} 个秒传` : ''}${bad ? ` · <span class="err">${bad} 个失败</span>` : ''} · ${fmtB(sent)} / ${fmtB(tot)}${act && rate > 1e4 ? ` · ${fmtB(rate)}/s` : ''}` : '';
  $('#up-sum').innerHTML = line;
  const btn = $('#btn-up');
  btn.innerHTML = act ? `⬆ ${Math.round(sent / Math.max(1, tot) * 100)}%` : '＋ 上传';
  btn.classList.toggle('busy', !!act);
  const rows = UQ.slice().sort((a, b) => ({ active: 0, failed: 1, queued: 2, ok: 3, dup: 3 }[a.state] - { active: 0, failed: 1, queued: 2, ok: 3, dup: 3 }[b.state])).slice(0, 200);
  $('#uplist').innerHTML = rows.map(t => `<div class="ur ${t.state}" data-k="${esc(t.key)}">
      <span class="un">${esc(t.f.name)}</span><span class="us">${fmtB(t.f.size)}</span>
      <span class="um">${esc(t.msg)}</span>
      <span class="ub"><i style="width:${Math.round((t.sent || 0) / t.f.size * 100)}%"></i></span></div>`).join('') +
    (UQ.length > 200 ? `<p class="s">…还有 ${UQ.length - 200} 个</p>` : '');
  const left = Object.values(FP.all()).filter(x => x.u === 1 && !UQ.some(t => t.f.name === x.name));
  $('#resume-hint').hidden = !left.length;
  if (left.length) $('#resume-hint').innerHTML = `⏸ 上次有 ${left.length} 个文件没传完（${left.slice(0, 3).map(x => esc(x.name)).join('、')}${left.length > 3 ? '…' : ''}）—— 重新选这些文件，会从断点接着传。`;
}
$('#uplist').addEventListener('click', e => {
  const r = e.target.closest('.ur.failed'); if (!r) return;
  const t = UQ.find(t => t.key === r.dataset.k); if (t) { t.state = 'queued'; t.msg = '排队中'; pump(); }
});
function openSheet() { $('#upsheet').hidden = false; renderUp(); }
$('#btn-up').onclick = () => openSheet();
$('#up-close').onclick = () => { $('#upsheet').hidden = true; };
$('#file').addEventListener('change', e => { enqueue([...e.target.files]); e.target.value = ''; });
let listT; function listSoon() { clearTimeout(listT); listT = setTimeout(() => refresh(), 1200); }

/* 电脑上直接把文件拖进窗口 */
let dragN = 0;
addEventListener('dragenter', e => { if (e.dataTransfer?.types?.includes('Files') && !$('#app').hidden) { dragN++; $('#dragcover').hidden = false; e.preventDefault(); } });
addEventListener('dragleave', () => { if (--dragN <= 0) { dragN = 0; $('#dragcover').hidden = true; } });
addEventListener('dragover', e => e.preventDefault());
addEventListener('drop', async e => {
  e.preventDefault(); dragN = 0; $('#dragcover').hidden = true;
  if ($('#app').hidden) return;
  const files = [];
  const walk = async en => {
    if (!en) return;
    if (en.isFile) files.push(await new Promise(r => en.file(r, () => r(null))));
    else if (en.isDirectory) { const rd = en.createReader(); for (;;) { const b = await new Promise(r => rd.readEntries(r, () => r([]))); if (!b.length) break; for (const x of b) await walk(x); } }
  };
  const its = [...(e.dataTransfer.items || [])];
  if (its.length && its[0].webkitGetAsEntry) { for (const en of its.map(i => i.webkitGetAsEntry())) await walk(en); }
  else files.push(...e.dataTransfer.files);
  enqueue(files.filter(Boolean));
});

/* 上传期间：手机保持亮屏（熄屏后浏览器会暂停网络）；关页面前提醒 */
let lock = null;
async function wake() {
  const busy = UQ.some(t => t.state === 'active' || t.state === 'queued');
  if (busy && !lock && 'wakeLock' in navigator && document.visibilityState === 'visible') {
    try { lock = await navigator.wakeLock.request('screen'); lock.addEventListener('release', () => { lock = null; }); } catch { /* 不支持就算了 */ }
  } else if (!busy && lock) { lock.release(); lock = null; }
}
document.addEventListener('visibilitychange', () => { wake(); if (document.visibilityState === 'visible' && S.me) refresh(); });
addEventListener('beforeunload', e => { if (UQ.some(t => t.state === 'active' || t.state === 'queued')) { e.preventDefault(); e.returnValue = ''; } });

/* ================= 启动 ================= */
async function boot() {
  const k = /[#&]k=([^&]+)/.exec(location.hash);
  if (k) history.replaceState(null, '', location.pathname + location.search);
  try {
    const r = await fetch(API + '/me', { credentials: 'same-origin' });
    if (r.status === 401) {
      showGate();
      if (k) { const p = decodeURIComponent(k[1]); $('#pass').value = p; doPass(p); }
      return;
    }
    S.me = (await r.json()).user;
  } catch { toast('连不上服务器，检查一下网络', 0); return; }
  $('#gate').hidden = true; $('#app').hidden = false;
  await refresh(true);
  loadSuggest();
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 15000);
}
if (typeof nav === 'function') document.body.insertAdjacentHTML('afterbegin', nav());   // 全站统一导航（/app.js）
boot();

// 给自动化测试用：不影响正常使用
window.__album = { S, enqueue, UQ, refresh, runSearch };
