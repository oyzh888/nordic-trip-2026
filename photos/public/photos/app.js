/* 北欧 2026 · 共享相册前端 —— 一个 ES module，无依赖、无构建，手机和电脑同一份
 *
 * 数据流：/api/list 第一次拿全量元数据，之后每次只拿增量（变过的那几张，见 §列表）
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
  tab: 'grid', group: localStorage.np_group || 'day', desc: localStorage.np_desc !== '0',          // 默认新的在前（点过「旧的在前」的人记住他的选择）
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

/* ================= 列表 =================
 * 第一次打开拿全量（?stale=1：服务端可以给几分钟前拼好的那份），之后每次只要「我手上这一版之后变了什么」（?since=）：
 * 1.4 万张时全量 1.7 MB（压缩后），而 GPU 端一直在写结果、版本号几秒一变 —— 以前每 15 秒整份重下一遍，
 * 手机上解析 9 MB 的 JSON 也卡。增量通常几百字节；服务端答不了的时候（它重启过、中间有大改动）自己回全量。 */
function setList(d) {
  S.data = d; S.ver = d.ver;
  S.byH = new Map(d.items.map(it => [it.h, it]));
  S.users = new Map(d.users.map(u => [u.id, u.name]));
  S.persons = new Map(d.persons.map(p => [p.id, p]));
  S.moments = new Map((d.moments || []).map(m => [m.id, m]));
  S.myPerson = d.persons.find(p => p.uid === S.me.id)?.id ?? null;
  for (const h of [...S.sel]) if (!S.byH.has(h)) S.sel.delete(h);
}
/** 把增量合进手上的列表：改了的原地换（同一时刻拍的几张顺序不变）、新的接在后面、撤掉的拿走 */
function mergeDelta(d) {
  const upd = new Map(d.items.map(it => [it.h, it])), gone = new Set(d.gone);
  const items = [];
  for (const it of S.data.items) {
    if (gone.has(it.h)) continue;
    const n = upd.get(it.h);
    if (n) upd.delete(it.h);
    items.push(n || it);
  }
  for (const it of upd.values()) items.push(it);
  const g = {};
  for (const k of ['users', 'persons', 'scenes', 'moments', 'pipe', 'ai']) g[k] = k in d ? d[k] : S.data[k];
  setList({ ...S.data, ...g, ver: d.ver, items });
}
async function loadList() {
  const get = q => fetch(API + '/list' + q, { credentials: 'same-origin', cache: 'no-cache' });
  let r = await get(S.data ? `?since=${S.ver}` : '?stale=1');
  if (r.status === 401) { showGate(); return false; }
  let d = await r.json(), first = false;
  if (!S.data) {                                               // 第一次：全量（可能是几分钟前的）→ 马上补一次增量
    setList(d); first = true;
    r = await get(`?since=${S.ver}`);
    if (!r.ok) return true;
    d = await r.json();
  }
  if (d.ver === S.ver) return first;
  if (d.delta) mergeDelta(d);
  else setList(d);
  return true;
}
async function refresh(force, bg) {
  const before = S.byH;
  const changed = await loadList();
  if (!changed && !force) return;
  if (S.q) await runSearch(S.q, true);
  renderAll(before, bg);
}

/* ---- 后台刷新（上传完一张、每 15 秒轮询、切回页面）：不打断正在做的事 ----
 * 以前每传完一张就整页重画：时间线是「新的在前」，新照片插在最上面把正在看的往下推；大图里的上一张 / 下一张
 * 按位置算，位置一变就跳错；人物页整页重建，正开着的下拉框直接关掉。连续传几百张时这每一两秒发生一次。
 * 现在：用户正在操作（开着大图、在输入框里、刚滚动 / 点过、开着下拉框）就先记下「有更新」，停手 2.5 秒后再画；
 * 画的时候保持正在看的那张照片在屏幕上的位置不动；滚到下面时，新照片只在顶上冒一个「↑ N 张新照片」。 */
S.touched = 0;
for (const ev of ['pointerdown', 'keydown', 'wheel', 'touchmove', 'scroll']) addEventListener(ev, () => { S.touched = Date.now(); }, { passive: true, capture: true });
function busy() {
  if (S.lb >= 0) return true;                                   // 开着大图
  const a = document.activeElement;
  if (a && a.matches && a.matches('input, textarea, select, [contenteditable]')) return true;
  if (document.querySelector('#people details[open], #people select:focus')) return true;
  return Date.now() - S.touched < 2500;
}
let bgPending = false;
async function bgRefresh() {
  if (!S.me) return;
  if (busy()) { bgPending = true; return; }
  bgPending = false;
  await refresh(false, true);
}
setInterval(() => { if (bgPending && !busy()) bgRefresh(); }, 800);

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
    it.lv ? '<em class="bd lv" title="Live Photo：点开会动">◉ LIVE</em>' : '',
  ].join('');
  return `<a class="tl${S.sel.has(it.h) ? ' on' : ''}" data-h="${it.h}" href="${F(it.h, 'o')}">${img}${badges}<b class="ck"></b></a>`;
}

const tileCache = new Map(), grpCache = new Map();
/** 同一张照片、tile() 生成的 HTML 一个字都没变 → 直接复用上次那个元素（图片不用重新加载 / 解码） */
function tileEl(it) {
  const html = tile(it), c = tileCache.get(it.h);
  if (c && c.html === html) return c.el;
  const t = document.createElement('template'); t.innerHTML = html;
  const el = t.content.firstElementChild;
  tileCache.set(it.h, { html, el });
  return el;
}
const sameKids = (parent, nodes) => parent.children.length === nodes.length && nodes.every((n, i) => parent.children[i] === n);
function renderGrid() {
  if (!S.data) return;
  const cur = S.lb >= 0 ? S.view[S.lb] : null;
  const xs = filtered(); S.view = xs;
  if (cur) {                                                    // 开着大图时列表变了：大图还停在同一张，上一张 / 下一张按新列表走
    const i = xs.findIndex(x => x.h === cur.h);
    if (i >= 0) S.lb = i; else { xs.splice(Math.min(S.lb, xs.length), 0, cur); }
  }
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
  // 不再整片拆掉重建：相册几千张时，每次 innerHTML 重建都要重新创建几千个 <img>、重新解码，
  // Safari 来不及画就露出黑块 / 细条（「闪」）。现在按 h 复用已有的缩略图元素，只有内容真变了的那几张才新建；
  // 什么都没变就一个节点都不动
  const used = new Set(), usedG = new Set();
  const groupsEls = gs.map(g => {
    const head = g.title ? `<h3>${esc(g.title)}</h3><span class="s">${esc(g.sub || '')} · ${g.items.length}</span>
        ${g.map ? `<a class="s" href="${g.map}" target="_blank" rel="noopener">地图 ↗</a>` : ''}
        <span class="grow"></span><button class="chip sm" data-selg="${esc(g.key)}">选这组</button>` : '';
    let c = grpCache.get(g.key);
    if (!c) {
      const el = document.createElement('div'); el.className = 'grp'; el.dataset.g = g.key;
      const gh = document.createElement('div'); gh.className = 'gh';
      const tiles = document.createElement('div'); tiles.className = 'tiles';
      el.append(gh, tiles); c = { el, gh, tiles, head: null }; grpCache.set(g.key, c);
    }
    usedG.add(g.key);
    if (c.head !== head) { c.gh.innerHTML = head; c.gh.hidden = !head; c.head = head; }
    const nodes = g.items.map(it => { used.add(it.h); return tileEl(it); });
    if (!sameKids(c.tiles, nodes)) c.tiles.replaceChildren(...nodes);
    return c.el;
  });
  const grid = $('#grid');
  if (!sameKids(grid, groupsEls)) grid.replaceChildren(...groupsEls);
  for (const k of tileCache.keys()) if (!used.has(k)) tileCache.delete(k);
  for (const k of grpCache.keys()) if (!usedG.has(k)) grpCache.delete(k);
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
const uploading = () => UQ.some(t => t.state === 'active' || t.state === 'queued');
function renderAll(before, bg) {
  renderTop();
  const fresh = before ? S.data.items.filter(it => !before.has(it.h)).length : 0;
  // 正在上传时，后台刷新不重画时间线：重画 250 张在慢手机上要 0.25 秒，每隔几秒来一次会让翻看、编辑都一卡一卡
  // （实测主线程最长卡顿 122 → 314 ms）。只在顶上数「↑ N 张新照片」，点一下立刻显示；全部传完再画一次
  if (bg && uploading()) { if (fresh) newPill(fresh); S.gridStale = true; return; }
  S.gridStale = false;
  renderChips();
  const anchor = gridAnchor();
  renderGrid();
  restoreAnchor(anchor);
  if (anchor && fresh) newPill(fresh);                          // 滚在下面时，新来的照片只提示，不把画面往下推
  else if (!anchor) hidePill();
  renderSel();
  if (S.tab === 'people') renderPeople();
  if (S.tab === 'insight') renderInsight();
}
/** 记下屏幕最上面那张照片和它离窗口顶部的距离（滚在最顶上时不用记 —— 那时就该看到新的） */
function gridAnchor() {
  if (S.tab !== 'grid' || scrollY < 120) return null;
  for (const el of document.querySelectorAll('#grid .tl')) {
    const r = el.getBoundingClientRect();
    if (r.bottom > 60) return { h: el.dataset.h, top: r.top };
  }
  return null;
}
function restoreAnchor(a) {
  if (!a) return;
  const el = document.querySelector(`#grid .tl[data-h="${a.h}"]`);
  // 必须瞬间跳：页面开了平滑滚动（scroll-behavior: smooth），普通 scrollBy 会「先被推下去再滑回来」，看着更晃
  if (el) scrollBy({ top: el.getBoundingClientRect().top - a.top, behavior: 'instant' });
}
function hidePill() { const p = $('#newpill'); if (p) { p.hidden = true; p.dataset.n = 0; } }
function newPill(n) {
  let p = $('#newpill');
  if (!p) {
    p = document.createElement('button'); p.id = 'newpill'; p.className = 'newpill';
    // 离顶上远（几千像素）就直接跳，平滑滚要好几秒；近的才平滑滚
    p.onclick = () => { hidePill(); if (S.gridStale) { S.gridStale = false; renderChips(); renderGrid(); renderSel(); } scrollTo({ top: 0, behavior: scrollY > 3000 ? 'instant' : 'smooth' }); };
    document.body.appendChild(p);
  }
  p.dataset.n = Number(p.dataset.n || 0) + n;
  p.textContent = `↑ ${p.dataset.n} 张新照片`;
  p.hidden = false;
}
addEventListener('scroll', () => { const p = $('#newpill'); if (p && !p.hidden && scrollY < 120 && !S.gridStale) hidePill(); }, { passive: true });

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
  const ss = it => it.gs || it.s;                               // 视频有 H.264 新版就存新版（手机相册直接能放、颜色正常）
  const size = items.reduce((s, it) => s + ss(it), 0);
  if (items.length > 60 || size > 800 * 2 ** 20) return toast(`一次最多 60 个 / 800 MB（现在 ${items.length} 个 / ${fmtB(size)}），分几次选，或者用「打包下载」`, 5000);
  btn.dataset.l = btn.dataset.l || btn.textContent;
  const files = []; let got = 0;
  try {
    for (const it of items) {
      btn.textContent = `下载中 ${Math.round(got / size * 100)}%`;
      const b = await (await fetch(F(it.h, it.gs ? 'g' : 'o'), { credentials: 'same-origin' })).blob();
      got += ss(it);
      files.push(new File([b], it.gs ? it.n.replace(/\.[^.]+$/, '') + '.mp4' : it.n, { type: b.type || 'application/octet-stream' }));
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
    if (it.lv && src) livePhoto(media, it, src);
  }
  renderLbInfo(it);
  for (const j of [i + 1, i - 1]) { const n = S.view[j]; if (n && n.k === 'i' && n.f & 2) new Image().src = F(n.h, 'p'); }
}
// Live Photo：和 iPhone 相册一样，点开先动一遍再停在照片上；按住「◉ LIVE」（或按住照片）再看一遍
function livePhoto(box, it, src) {
  const vsrc = it.lvf & 4 ? F(it.lv, 'v') : F(it.lv, 'o');      // 720p H.264 预览所有浏览器都能放；还没转好就先用原件（Safari 能放 HEVC）
  box.innerHTML = `<div class="live"><img src="${src}" alt=""><video muted playsinline preload="auto" src="${vsrc}"></video>
    <button class="livebtn" title="按住看 Live Photo">◉ LIVE</button></div>`;
  const w = box.firstElementChild, v = w.querySelector('video');
  const play = () => { v.currentTime = 0; w.classList.add('play'); v.play().catch(() => w.classList.remove('play')); };
  const stop = () => { w.classList.remove('play'); v.pause(); };
  v.addEventListener('ended', stop);
  v.addEventListener('canplay', () => { if (!w.dataset.once) { w.dataset.once = 1; play(); } }, { once: true });
  for (const el of [w.querySelector('.livebtn'), w.querySelector('img')]) {
    el.addEventListener('pointerdown', e => { e.preventDefault(); play(); });
    el.addEventListener('pointerup', stop); el.addEventListener('pointerleave', () => w.classList.contains('play') && el.matches('.livebtn') && stop());
  }
}
// 视频新版是怎么来的（GPU 端转码 + 调色，见 pipeline/video.py）
const GP = { transcode: 'H.264（颜色没动）', 'clog3-cg': 'H.264 · 佳能 Canon Log 3 → Canon 709 调色', 'clog3-2020': 'H.264 · 佳能 Canon Log 3（BT.2020）→ BT.709 调色',
  pq: 'H.264 · HDR（PQ）→ 普通屏幕', hlg: 'H.264 · HDR（HLG）→ 普通屏幕' };
function renderLbInfo(it) {
  const tg = it.tg || {};
  const tags = [...new Set([...(tg.special || []), ...(tg.objects || []), ...(tg.tags || [])])].slice(0, 16);
  const ppl = it.p.map(p => S.persons.get(p)).filter(Boolean);
  const mine = it.u.includes(S.me.id);
  const mo = it.mo != null ? S.moments.get(it.mo) : null;
  const group = it.b ? S.data.items.filter(x => x.b === it.b).sort((a, b) => (b.q ?? -1) - (a.q ?? -1)) : [];
  $('#lb-info').innerHTML = `
    <div class="lb-row"><b>${md(it)}</b>${it.pl ? `<span>📍 ${esc(it.pl)}</span>` : ''}${it.cam ? `<span>📷 ${esc(it.cam)}</span>` : ''}
      <span class="s">${esc(it.n)} · ${fmtB(it.s)}${it.w ? ` · ${it.w}×${it.hh}` : ''}${it.d ? ` · ${fmtD(it.d)}` : ''}${it.gs ? ` · 🎞 ${esc(GP[it.gp] || 'H.264')}` : ''}</span></div>
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
      ${it.gs ? `<a class="btn pri sm" href="${F(it.h, 'g')}?dl=1" title="${esc(GP[it.gp] || 'H.264')}">⬇ 下载视频 · ${fmtB(it.gs)}</a>
        <a class="btn sm" href="${F(it.h, 'o')}?dl=1" title="上传上来的那份，一个字节没动">⬇ 相机原片 · ${fmtB(it.s)}</a>`
        : `<a class="btn pri sm" href="${F(it.h, 'o')}?dl=1">⬇ 下载原${it.k === 'v' ? '视频' : '图'}</a>`}
      ${it.lv ? `<a class="btn sm" href="${F(it.lv, 'o')}?dl=1">⬇ Live 视频</a>` : ''}
      <button class="btn sm" id="lb-share">📲 存到手机</button>
      <button class="btn sm" id="lb-sel">${S.sel.has(it.h) ? '✓ 已选' : '选中'}</button>
      ${it.k === 'v' && it.f & 4 ? `<button class="btn ghost sm" id="lb-orig">${it.gs ? '看高清' : '看原画质'}</button>` : ''}
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
  if (t.id === 'lb-orig') { const v = $('#lb-media video'); const pos = v.currentTime; v.src = F(it.h, it.gs ? 'g' : 'o'); v.currentTime = pos; v.play(); t.remove(); return; }
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
  // 有人脸小图条（GPU 端生成，每张脸 160×160 横排，~10 KB/张）就直接取第 fi 格
  if (it.f & 8 && f.fn > 0 && f.fi < f.fn)
    return `<span class="${cls}" data-face="${f.id}" data-fh="${f.h}" data-bg="${F(f.h, 'f')}" style="background-size:${f.fn * 100}% 100%;background-position:${f.fn > 1 ? f.fi / (f.fn - 1) * 100 : 0}% 0"></span>`;
  const W = it.w || 1, H = it.hh || 1;
  const side = Math.max(f.w * W, f.hh * H) * 1.6;
  const sw = Math.min(1, side / W), sh = Math.min(1, side / H);
  const cx = f.x + f.w / 2, cy = f.y + f.hh / 2;
  const x0 = Math.min(Math.max(cx - sw / 2, 0), 1 - sw), y0 = Math.min(Math.max(cy - sh / 2, 0), 1 - sh);
  // 缩略图（长边 ~480，平均 35 KB）里这张脸裁出来够 80 像素就用它；合照里的小脸才用预览图（1600，平均 313 KB）
  const inThumb = Math.max(sw * W, sh * H) / Math.max(W, H) * 480;
  const src = it.f & 1 && (inThumb >= 80 || !(it.f & 2)) ? F(f.h, 't') : it.f & 2 ? F(f.h, 'p') : F(f.h, 't');
  const px = sw >= 1 ? 50 : x0 / (1 - sw) * 100, py = sh >= 1 ? 50 : y0 / (1 - sh) * 100;
  return `<span class="${cls}" data-face="${f.id}" data-fh="${f.h}" data-bg="${src}" style="background-size:${100 / sw}% ${100 / sh}%;background-position:${px}% ${py}%"></span>`;
}
async function renderPeople() {
  const el = $('#people');
  if (!el.innerHTML) el.innerHTML = '<p class="s">加载中…</p>';
  let d; try { d = await api('/people'); } catch (e) { el.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
  // 人物数据一个字都没变就不重画（后台每 15 秒刷新一次，以前每次都把整页人物和头像重建一遍 → 一闪）
  const sig = JSON.stringify(d) + '|' + S.me.id;
  if (sig === S.peopleSig && el.querySelector('.pcard, .s')) return;
  S.peopleSig = sig;
  S.peopleData = d;
  const iAmKnown = d.persons.some(p => p.uid === S.me.id);
  const opts = d.persons.map(p => `<option value="${p.id}">${esc(p.name || '未命名')}</option>`).join('');
  el.innerHTML = `
    ${d.persons.length ? `<h3>已认出的人</h3><div class="pgrid">${d.persons.map(p => `
      <div class="pcard${p.uid === S.me.id ? ' me' : ''}">
        <div class="faces">${p.faces.map(f => `<span class="fw">${faceDiv(f)}<button class="fx" data-unassign="${f.id}" title="这张不是 TA">✕</button></span>`).join('')}</div>
        <div class="pn"><b>${esc(p.name || '未命名')}</b>${p.uid === S.me.id ? ' <span class="badge ok">就是你</span>' : ''}<span class="s">${p.n} 张</span></div>
        <div class="pa"><button class="btn sm pri" data-see="${p.id}">看 TA 的照片</button><button class="btn sm ghost" data-rename="${p.id}">改名</button>
          ${!iAmKnown && !p.uid ? `<button class="btn sm ghost" data-mine="${p.id}">🙋 这是我</button>` : ''}
          ${d.persons.length > 1 ? `<select data-pmerge="${p.id}"><option value="">和…是同一个人</option>${d.persons.filter(q => q.id !== p.id && !(p.uid && q.uid)).map(q => `<option value="${q.id}">${esc(q.name || '未命名')}</option>`).join('')}</select>` : ''}</div>
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
  lazyBg(el);
}
/** 头像是 CSS 背景图，浏览器的 loading=lazy 管不到 —— 滚到附近（上下 600px 内）才真正去下载 */
const bgIO = 'IntersectionObserver' in window ? new IntersectionObserver(es => {
  for (const e of es) if (e.isIntersecting) { e.target.style.backgroundImage = `url('${e.target.dataset.bg}')`; bgIO.unobserve(e.target); }
}, { rootMargin: '600px 0px' }) : null;
function lazyBg(root) {
  for (const n of root.querySelectorAll('[data-bg]')) {
    if (bgIO) bgIO.observe(n); else n.style.backgroundImage = `url('${n.dataset.bg}')`;
  }
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
    if (t.dataset.mine) return ok('/people/merge', { from: Number(t.dataset.mine), into: 'me' }, '好！「⭐ 与我相关」现在包括所有拍到你的照片了');
    if (t.dataset.see) { S.person = Number(t.dataset.see); S.quick = 'all'; goTab('grid'); return renderAll(); }
    const f = t.closest('[data-fh]');
    if (f) { const i = S.data.items.findIndex(x => x.h === f.dataset.fh); if (i >= 0) { S.view = [S.data.items[i]]; openLb(0); } }
  } catch (err) { toast(err.message); }
});
$('#people').addEventListener('change', async e => {
  const pm = e.target.closest('[data-pmerge]');
  if (pm && pm.value) {
    const into = pm.selectedOptions[0].textContent;
    if (!confirm(`把这张卡的照片都并到「${into}」，并删掉这张卡？`)) { pm.value = ''; return; }
    try { await api('/people/merge', { method: 'POST', body: { from: Number(pm.dataset.pmerge), into: Number(pm.value) } }); toast('已合并到 ' + into); }
    catch (err) { toast(err.message); }
    await refresh(true); return renderPeople();
  }
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
const MAXF = 4, MAXP = 2;                 // 同时传 4 个文件、每个文件 2 块 → 最多 8 个请求在飞（手机照片多数只有 1 块，以前实际只有 3 路）
const fkey = f => `${f.name}|${f.size}|${f.lastModified}`;
// 本机指纹缓存：内存里一份，写盘攒 400 ms 一次 —— 以前每次读写都把 4000 条 JSON 整个解析 + 序列化一遍，
// 几百个文件同时在传时这就是手机上「卡」的主要来源之一
const FP = {
  m: null, tm: 0,
  all() { if (!this.m) { try { this.m = JSON.parse(localStorage.np_fp || '{}'); } catch { this.m = {}; } } return this.m; },
  get(k) { return this.all()[k] || null; },
  put(k, v) { const a = this.all(); a[k] = { ...(a[k] || {}), ...v, at: Date.now() }; this.save(); },
  del(k) { delete this.all()[k]; this.save(); },
  save() {
    clearTimeout(this.tm);
    this.tm = setTimeout(() => {
      const a = this.all(), ks = Object.keys(a);
      if (ks.length > 4000) ks.sort((x, y) => a[x].at - a[y].at).slice(0, ks.length - 4000).forEach(x => delete a[x]);
      try { localStorage.np_fp = JSON.stringify(a); } catch { /* 满了就不记，下次重算 */ }
    }, 400);
  },
  flush() { if (this.tm) { clearTimeout(this.tm); this.tm = 0; try { localStorage.np_fp = JSON.stringify(this.all()); } catch { /* */ } } },
};
addEventListener('pagehide', () => FP.flush());
const MEDIA_EXT = /\.(jpe?g|png|webp|gif|avif|heic|heif|hif|dng|tiff?|raw|arw|srf|sr2|cr2|cr3|crw|nef|nrw|orf|rw2|raf|pef|srw|rwl|3fr|iiq|x3f|mov|mp4|m4v|3gp|mkv|avi|webm|insv|insp)$/i;

/* ---- 选中的文件本身存进浏览器（IndexedDB），页面被系统杀掉后重新打开能自动接着传，不用重选 ----
 * 学的是 Uppy 的 Golden Retriever 插件：iPhone 内存不够时会把 Safari 标签页杀掉，以前选的几百张就白选了 ——
 * 重选还得让手机再从 iCloud 下载、再转一遍 JPEG。现在没传完的文件先在浏览器里存一份，传完一张删一张。
 * 一次只存一个、在后台存；正在传或已经传完的不存；单个超过 200 MB（大视频）不存；浏览器剩余配额不够就不存；存了 3 天还没传完就丢掉 */
const KEEP_MAX = 200 * 2 ** 20, KEEP_DAYS = 3;
const keepDB = (() => {
  let p = null;
  return () => p || (p = new Promise((res, rej) => {
    const r = indexedDB.open('np-upload', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('files');
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  }).catch(() => null));
})();
const idb = async (mode, fn) => { const db = await keepDB(); if (!db) return null;
  return new Promise((res, rej) => { const tx = db.transaction('files', mode), st = tx.objectStore('files'); const r = fn(st);
    tx.oncomplete = () => res(r && 'result' in r ? r.result : undefined); tx.onerror = tx.onabort = () => rej(tx.error); }); };
const keepQ = [];
let keeping = false;
function keepLater(ts) { keepQ.push(...ts); keepNext(); }
async function keepNext() {
  if (keeping) return;
  keeping = true;
  try {
    while (keepQ.length) {
      const t = keepQ.shift();
      if (t.state !== 'queued' || t.f.size > KEEP_MAX || t.kept) continue;       // 已经在传 / 传完了，存它没意义
      const est = await navigator.storage?.estimate?.().catch(() => null);
      if (est && est.quota && est.usage + t.f.size > est.quota * 0.8) break;    // 浏览器配额快满了：不存了
      try { await idb('readwrite', st => st.put({ f: t.f, name: t.f.name, at: Date.now() }, t.key)); t.kept = true; }
      catch { break; }                                                           // 存不进去（隐私模式等）：算了
      if (t.state !== 'queued') unkeep(t);                                       // 存的时候它已经传完了
    }
  } finally { keeping = false; }
}
function unkeep(t) { if (t.kept) { t.kept = false; idb('readwrite', st => st.delete(t.key)).catch(() => {}); } }
async function keptFiles() {
  const rows = await idb('readonly', st => st.getAll()).catch(() => null);
  const keys = await idb('readonly', st => st.getAllKeys()).catch(() => null);
  if (!rows || !keys) return [];
  const old = Date.now() - KEEP_DAYS * 86400e3, out = [];
  rows.forEach((r, i) => { if (r && r.f && r.at > old) out.push(r.f); else idb('readwrite', st => st.delete(keys[i])).catch(() => {}); });
  return out;
}

/* ---- 每一批的用时记下来（一批一行，存服务端）：同学说「传得特别慢」时，看得出是慢在手机准备、还是慢在网络 ---- */
// 页面在后台的累计时间（锁屏 / 切到别的 App 时 iPhone 会暂停网页，上传也停）
let hidAcc = 0, hidAt = document.visibilityState === 'hidden' ? Date.now() : 0;
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') hidAt = Date.now(); else if (hidAt) { hidAcc += Date.now() - hidAt; hidAt = 0; }
});
const hiddenTotal = () => hidAcc + (hidAt ? Date.now() - hidAt : 0);
function newBatch(files, info) {
  const kinds = {};
  for (const f of files) { const e = (f.name.split('.').pop() || '?').toLowerCase(); kinds[e] = (kinds[e] || 0) + 1; }
  return { t0: Date.now(), h0: hiddenTotal(), pickMs: info?.pickMs ?? null, src: info?.src || 'drop', n: 0, bytes: 0, kinds, left: 0, tasks: [] };
}
function batchDone(b) {
  const ts = b.tasks, ok = ts.filter(t => t.state === 'ok'), tm = k => ok.length ? Math.round(ok.reduce((s, t) => s + (t.tm?.[k] || 0), 0) / ok.length) : null;
  const upMs = Date.now() - b.t0, sent = ok.reduce((s, t) => s + t.f.size, 0);
  const sum = { src: b.src, pickMs: b.pickMs, upMs, n: ts.length, ok: ok.length, dup: ts.filter(t => t.state === 'dup').length,
    fail: ts.filter(t => t.state === 'failed').length, bytes: b.bytes, sent, kinds: b.kinds, fp: tm('fp'), init: tm('init'), net: tm('net'),
    mbps: upMs ? +(sent * 8 / upMs / 1000).toFixed(1) : null, ua: navigator.userAgent.slice(0, 160),
    conn: navigator.connection?.effectiveType || null, hiddenMs: hiddenTotal() - b.h0 };
  S.lastBatch = sum; renderUp();
  api('/uplog', { method: 'POST', body: sum }).catch(() => { /* 记不上就算了 */ });
}
function enqueue(files, info) {
  let add = 0, skip = 0, same = 0, again = 0, aae = 0;
  const fresh = [];
  const batch = newBatch(files, info);
  for (const f of files) {
    if (/\.aae$/i.test(f.name)) { aae++; continue; }       // iPhone「所有照片数据」里附带的编辑记录，不是照片
    if (!f.size || !(/^(image|video)\//.test(f.type) || MEDIA_EXT.test(f.name))) { skip++; continue; }
    const key = fkey(f);
    const old = UQ.find(t => t.key === key);
    if (old) { if (old.state === 'failed') { old.state = 'queued'; old.f = f; again++; } else same++; continue; }
    const t = { f, key, state: 'queued', sent: 0, msg: '排队中', hold: true, b: batch }; UQ.push(t); fresh.push(t); add++;
    batch.tasks.push(t); batch.n++; batch.bytes += f.size; batch.left++;
    if (!FP.get(key)?.done) FP.put(key, { q: 1, name: f.name });   // 页面万一被系统杀掉，下次打开能告诉你还剩哪些
  }
  // 不拦，只提醒：几十 MB 一张的多半是相机原片，1000 张就是 50 GB
  const big = files.filter(f => /^image\//.test(f.type) && f.size > 25 * 2 ** 20).length;
  if (skip || same || big || aae) toast([aae && `跳过 ${aae} 个 .AAE（iPhone 的编辑记录，不是照片）`, skip && `跳过 ${skip} 个不是照片/视频的文件`, same && `${same} 个这次已经选过了，不重复传`,
    big && `有 ${big} 张超过 25 MB（相机原片 / RAW）—— 都能传、能看，就是传得慢一些`].filter(Boolean).join(' · '), big ? 8000 : undefined);
  if (add || again) openSheet();
  // 先整批问一次服务端「哪些已经有了」，有的直接秒传 —— 重选同一批几百张时，不用把每个文件读一遍算指纹
  if (fresh.length) probe(fresh).finally(() => { fresh.forEach(t => { t.hold = false; }); pump(); if (info?.src !== 'restore') keepLater(fresh); });
  else if (again) pump();
  renderUp();
}
async function probe(ts) {
  for (let i = 0; i < ts.length; i += 1000) {
    const part = ts.slice(i, i + 1000);
    part.forEach(t => { t.msg = '和相册对一下…'; });
    renderUpSoon();
    try {
      const r = await Promise.race([api('/upload/probe', { method: 'POST', body: { items: part.map(t => [t.f.name, t.f.size]) } }), sleep(8000).then(() => null)]);
      for (const j of r?.hit || []) { const t = part[j]; t.state = 'dup'; t.sent = t.f.size; t.msg = '相册里已经有了（秒传）'; FP.put(t.key, { q: 0, done: 1 }); settled(t); }
      if (r?.hit?.length) listSoon();
    } catch { /* 问不到就一个个走正常流程，服务端照样会按指纹去重 */ }
    part.forEach(t => { if (t.state === 'queued') t.msg = '排队中'; });
  }
}
function settled(t) {
  if (t.state === 'ok' || t.state === 'dup') unkeep(t);         // 传完了：浏览器里存的那份删掉
  if (t.b && !t.counted) { t.counted = true; if (--t.b.left === 0) batchDone(t.b); }
  if (!uploading()) setTimeout(drainAux, 0);                    // 上传队列空了 → 开始补缩略图
}
function pump() {
  while (running < MAXF) {
    const t = UQ.find(t => t.state === 'queued' && !t.hold); if (!t) break;
    running++; t.state = 'active'; t.t0 = Date.now();
    runTask(t).catch(e => { t.state = 'failed'; t.msg = '失败：' + e.message + ' · 点这行重试'; })
      .finally(() => { running--; settled(t); renderUpSoon(); pump(); if (!uploading()) listSoon(); });   // 全部传完 → 补画一次时间线
  }
  wake(); renderUpSoon();
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
  // 每个文件各阶段用时（毫秒）：fp 算指纹 · init 和相册对一下 · net 传字节 · thumb 等缩略图 —— 慢在哪一看就知道
  const tm = t.tm = { t0: performance.now() }, lap = k => { tm[k] = Math.round(performance.now() - (tm._ || tm.t0)); tm._ = performance.now(); };
  let fp = FP.get(t.key);
  if (!fp || !fp.h) {
    t.msg = '计算指纹…';
    fp = await fingerprint(f, p => { t.msg = `计算指纹 ${Math.round(p * 100)}%`; renderUpSoon(); });
    FP.put(t.key, fp);
  }
  lap('fp');
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
  lap('init');
  if (r.status === 'exists') { t.state = 'dup'; t.sent = f.size; t.msg = '相册里已经有了（秒传）'; FP.put(t.key, { q: 0, done: 1 }); listSoon(); return; }
  FP.put(t.key, { q: 0, u: 1, name: f.name });
  // 缩略图在后台补，不占上传名额：以前每个文件传完还要排队等自己那张缩略图（一次只解一张，防 Safari 内存不够），
  // 网快的时候 78% 的时间花在等缩略图上（实测：每张 1.4 秒里有 1.1 秒在等）。现在字节传完、服务端确认就算完成
  if (!fp.tb) makeAux(t, fp).catch(() => { /* GPU 端会补 */ });
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
    let next = 0, finished = false;
    const worker = async () => {
      while (next < todo.length) {
        const i = todo[next++];
        const blob = f.slice((i - 1) * psize, (i - 1) * psize + partLen(i));
        const hdr = fp.shas && fp.shas[i - 1] ? { 'x-part-sha256': fp.shas[i - 1] } : {};
        const pr = await retry(() => xput(`${API}/upload/part?h=${fp.h}&n=${i}`, blob, hdr, l => { inflight.set(i, l); prog(); }), t);
        if (pr && (pr.status === 'done' || pr.complete)) finished = 'done';   // 单块的文件服务端顺手收了尾
        if (pr && pr.status === 'corrupt') finished = 'corrupt';
        inflight.delete(i); base += partLen(i); done.add(i); prog();
        t.msg = n > 1 ? `上传中 ${done.size}/${n} 块` : '上传中';
      }
    };
    await Promise.all(Array.from({ length: Math.min(MAXP, todo.length) }, worker));
    t.msg = '收尾…';
    // 单块文件（绝大多数手机照片）在传那一块时服务端已经收尾了：省一个来回（手机 → 边缘 → 美国西部的数据库）
    const c = finished ? { status: finished } : await retry(() => api('/upload/complete', { method: 'POST', body: { h: fp.h } }), t);
    if (c.status === 'done' || c.status === 'exists') {
      lap('net'); tm.total = Math.round(performance.now() - tm.t0);
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
// 指纹（每 8 MB 一块的 SHA-256 + 整个文件的 CRC32）放到后台线程（Web Worker）里算 —— Immich 网页版也是这么做的。
// CRC32 是逐字节的 JS 循环，在主线程上算会让页面一卡一卡（慢手机上一张 3 MB 的照片约 50 ms）；两个后台线程还能并行算。
// 后台线程起不来（老浏览器）就退回在主线程算
const FP_SRC = `
const T = new Uint32Array(256);
for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; T[n] = c >>> 0; }
const crc32 = (u8, crc) => { let c = ~crc >>> 0; for (let i = 0; i < u8.length; i++) c = T[(c ^ u8[i]) & 0xFF] ^ (c >>> 8); return ~c >>> 0; };
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
onmessage = async e => {
  const { id, f, PART } = e.data;
  try {
    const n = Math.max(1, Math.ceil(f.size / PART)), cat = new Uint8Array(n * 32), shas = [];
    let crc = 0;
    for (let i = 0; i < n; i++) {
      const buf = await f.slice(i * PART, Math.min(f.size, (i + 1) * PART)).arrayBuffer();
      const d = await crypto.subtle.digest('SHA-256', buf);
      cat.set(new Uint8Array(d), i * 32); shas.push(hex(d));
      crc = crc32(new Uint8Array(buf), crc);
      postMessage({ id, p: (i + 1) / n });
    }
    postMessage({ id, done: { h: hex(await crypto.subtle.digest('SHA-256', cat)), crc, shas: n > 1 ? shas : undefined } });
  } catch (err) { postMessage({ id, err: String(err) }); }
};`;
const fpPool = (() => {
  try {
    const url = URL.createObjectURL(new Blob([FP_SRC], { type: 'text/javascript' }));
    const ws = [0, 1].map(() => new Worker(url)), jobs = new Map();
    let next = 0, seq = 0;
    for (const w of ws) w.onmessage = e => { const j = jobs.get(e.data.id); if (!j) return;
      if (e.data.p != null) j.onp(e.data.p);
      else { jobs.delete(e.data.id); e.data.err ? j.rej(new Error(e.data.err)) : j.res(e.data.done); } };
    return (f, onp) => new Promise((res, rej) => { const id = ++seq; jobs.set(id, { res, rej, onp }); ws[next++ % ws.length].postMessage({ id, f, PART }); });
  } catch { return null; }
})();
async function fingerprint(f, onp) {
  if (fpPool) { try { return await fpPool(f, onp); } catch { /* 后台线程出错 → 主线程再算一次 */ } }
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
  return { heic: 'image/heic', heif: 'image/heif', hif: 'image/heif', avif: 'image/avif', webp: 'image/webp', gif: 'image/gif', tif: 'image/tiff', tiff: 'image/tiff',
    mov: 'video/quicktime', mp4: 'video/mp4', m4v: 'video/mp4', mkv: 'video/x-matroska', webm: 'video/webm', avi: 'video/x-msvideo', '3gp': 'video/3gpp',
    dng: 'image/x-adobe-dng', cr2: 'image/x-canon-cr2', cr3: 'image/x-canon-cr3', nef: 'image/x-nikon-nef', arw: 'image/x-sony-arw', raf: 'image/x-fuji-raf',
    orf: 'image/x-olympus-orf', rw2: 'image/x-panasonic-rw2', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png' }[e] || 'application/octet-stream';
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
/** JPEG 的尺寸（已按 EXIF 方向转正）：从 SOF 段读宽高、从 EXIF 读方向（5–8 = 转了 90°，宽高互换）。只读前 128 KB */
async function jpegDims(f) {
  if (!(/^image\/jpe?g$/i.test(f.type) || /\.jpe?g$/i.test(f.name))) return null;
  const v = new DataView(await f.slice(0, 128 * 1024).arrayBuffer());
  if (v.getUint16(0) !== 0xFFD8) return null;
  let o = 2, w = 0, h = 0, rot = 1;
  while (o + 9 < v.byteLength) {
    const mk = v.getUint16(o), len = v.getUint16(o + 2);
    if (mk === 0xFFE1 && v.getUint32(o + 4) === 0x45786966) {
      const T = o + 10, le = v.getUint16(T) === 0x4949, i0 = T + v.getUint32(T + 4, le), n = v.getUint16(i0, le);
      for (let i = 0; i < n; i++) { const e = i0 + 2 + i * 12; if (e + 10 <= v.byteLength && v.getUint16(e, le) === 0x0112) rot = v.getUint16(e + 8, le); }
    }
    if (mk >= 0xFFC0 && mk <= 0xFFCF && ![0xFFC4, 0xFFC8, 0xFFCC].includes(mk)) { h = v.getUint16(o + 5); w = v.getUint16(o + 7); break; }
    if ((mk & 0xFF00) !== 0xFF00 || mk === 0xFFDA) break;
    o += 2 + len;
  }
  if (!w || !h) return null;
  return rot >= 5 && rot <= 8 ? { w: h, h: w } : { w, h };
}
async function decode(f, kind, max) {
  if (kind === 'v') return videoFrame(f);
  try {
    // 解码时直接缩到预览图的尺寸（长边 1600）：JPEG 能按 1/2、1/4 直接解，比先解出 1200 万像素再缩快得多、也省内存。
    // 只给宽度，高度按比例；竖图就只给高度。不认这个参数的浏览器会忽略它，照旧解全尺寸
    const p = max ? await jpegDims(f).catch(() => null) : null;   // 只读文件头拿尺寸 + 方向，不解码
    const sc = p ? Math.min(1, max / Math.max(p.w, p.h)) : 1;
    if (sc < 1) {                                                // 只给一条边：不管浏览器先转方向还是先缩放，长宽比都不会错
      const b = await createImageBitmap(f, { imageOrientation: 'from-image', resizeQuality: 'medium', ...(p.w >= p.h ? { resizeWidth: Math.round(p.w * sc) } : { resizeHeight: Math.round(p.h * sc) }) });
      return { src: b, W: p.w, H: p.h, close: () => b.close() };
    }
    const b = await createImageBitmap(f, { imageOrientation: 'from-image' }); return { src: b, W: b.width, H: b.height, close: () => b.close() };
  } catch { /* 走 <img> */ }
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
// 缩略图一次只解一张：一张 2400 万像素的 iPhone 照片解码出来约 96 MB，以前 3 张同时解 ≈ 300 MB，
// 几百张连续传时 Safari 会因为内存把整个页面杀掉（「卡死、选的全白选了」）
// 上传和后处理完全分开：缩略图（解码 + 两次 JPEG 编码 + 两个小上传）等这一批全部传完、上传队列空了才开始，
// 不和上传抢手机 CPU、抢上行带宽；排到时 GPU 端已经做好了就跳过（GPU 端本来就会补）
const auxQ = [];
let auxRunning = false;
function makeAux(t, fp) { auxQ.push([t, fp]); drainAux(); return Promise.resolve(); }
async function drainAux() {
  if (auxRunning) return;
  auxRunning = true;
  try {
    while (auxQ.length && !uploading()) {
      const [t, fp] = auxQ.shift();
      await makeAux1(t, fp).catch(() => { /* GPU 端会补 */ });
    }
  } finally { auxRunning = false; }
}
async function makeAux1(t, fp) {
  const it = S.byH.get(fp.h);
  if (it && (it.f & 3) === 3) return;                           // 排到它的时候 GPU 端已经做好了：省下手机的 CPU
  const kind = /^video\//.test(t.f.type) || /\.(mov|mp4|m4v|3gp|mkv|avi|webm)$/i.test(t.f.name) ? 'v' : 'i';
  const d = await decode(t.f, kind, 1600);
  if (!d || !d.W) return;
  try {
    const sw = d.src.width || d.W, sh = d.src.height || d.H;     // 解码时可能已经缩过了
    const pc = canvasOf(d.src, sw, sh, Math.min(1, 1600 / Math.max(sw, sh)));
    const tc = canvasOf(pc, pc.width, pc.height, Math.min(1, 360 / Math.min(pc.width, pc.height)));
    const [pb, tb] = [await jpeg(pc, 0.82), await jpeg(tc, 0.75)];
    const dims = `&w=${d.W}&hh=${d.H}${d.dur ? `&dur=${d.dur.toFixed(2)}` : ''}`;
    if (tb) await retry(() => xput(`${API}/upload/aux?h=${fp.h}&k=t${dims}`, tb), t);
    if (pb) await retry(() => xput(`${API}/upload/aux?h=${fp.h}&k=p`, pb), t);
    FP.put(t.key, { tb: 1 });
  } finally { d.close && d.close(); }
}

/* ---------- 上传面板 ---------- */
// 进度一秒刷 4 次就够了；以前每一帧（60 次/秒）都重建 200 行列表
let upRaf = 0, upLast = 0;
function renderUpSoon() {
  if (upRaf) return;
  upRaf = setTimeout(() => requestAnimationFrame(() => { upRaf = 0; upLast = Date.now(); renderUp(); }), Math.max(0, 250 - (Date.now() - upLast)));
}
function renderUp() {
  const tot = UQ.reduce((s, t) => s + t.f.size, 0), sent = UQ.reduce((s, t) => s + (t.sent || 0), 0);
  const ok = UQ.filter(t => t.state === 'ok').length, dup = UQ.filter(t => t.state === 'dup').length;
  const bad = UQ.filter(t => t.state === 'failed').length, act = UQ.filter(t => t.state === 'active' || t.state === 'queued').length;
  const now = Date.now();
  if (!renderUp.s || now - renderUp.s.t > 1500) { const s0 = renderUp.s; renderUp.s = { t: now, b: sent, rate: s0 ? Math.max(0, (sent - s0.b) / ((now - s0.t) / 1000)) : 0 }; }
  const rate = renderUp.s.rate;
  const act2 = UQ.some(t => t.state === 'active' || t.state === 'queued');
  $('#pick-more').hidden = !act2;
  const k = PREP.batch(), tip = $('#pick-tip');
  tip.hidden = !k;
  if (k) tip.innerHTML = `📱 这台手机准备一张照片约 <b>${PREP.get().toFixed(1)} 秒</b>（从 iCloud 下载 + 转 JPEG，这段在手机里做，网页插不上手）→
    建议<b>每批选 ${k} 张左右</b>（只等 ~20 秒），这批传的时候就可以选下一批`;
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
  const lb = S.lastBatch, el = $('#up-last');
  if (el) {
    el.hidden = !lb;
    if (lb) el.innerHTML = `上一批 ${lb.n} 个 · ${lb.pickMs != null ? `手机准备 <b>${mmss(lb.pickMs)}</b>（从 iCloud 下载 + 转格式）· ` : ''}上传 <b>${mmss(lb.upMs)}</b>`
      + `${lb.mbps ? `（${lb.mbps} Mbps）` : ''}${lb.dup ? ` · ${lb.dup} 个秒传` : ''}${lb.hiddenMs > 5000 ? ` · 其中 ${mmss(lb.hiddenMs)} 页面在后台（暂停了）` : ''}`;
  }
  const names = new Set(UQ.map(t => t.f.name)), wk = Date.now() - 7 * 86400e3;
  const left = Object.values(FP.all()).filter(x => (x.q === 1 || x.u === 1) && !x.done && x.at > wk && !names.has(x.name));
  $('#resume-hint').hidden = !left.length;
  if (left.length) $('#resume-hint').innerHTML = `⏸ 上次选的照片里还有 <b>${left.length}</b> 个没传完（${left.slice(0, 3).map(x => esc(x.name)).join('、')}${left.length > 3 ? '…' : ''}）。<br>
    页面多半是被手机系统关掉了。<b>重新把那一批全选上就行</b> —— 已经传过的会秒跳过，传一半的从断点接着传。
    <button class="btn ghost sm" id="resume-clear">不传了，清掉</button>`;
}
$('#resume-hint').addEventListener('click', e => {
  if (e.target.id !== 'resume-clear') return;
  const a = FP.all(); for (const k in a) if (a[k].q === 1 || a[k].u === 1) { a[k].q = 0; a[k].u = 0; }
  FP.save(); idb('readwrite', st => st.clear()).catch(() => {}); renderUp();
});
$('#uplist').addEventListener('click', e => {
  const r = e.target.closest('.ur.failed'); if (!r) return;
  const t = UQ.find(t => t.key === r.dataset.k); if (t) { t.state = 'queued'; t.msg = '排队中'; pump(); }
});
/* ---------- API 密钥：给脚本批量传用。原文只显示这一次（服务端只存哈希） ---------- */
async function renderKeys(fresh) {
  const box = $('#keys-box');
  let ks = []; try { ks = await api('/keys'); } catch (e) { box.innerHTML = `<p class="err">${esc(e.message)}</p>`; return; }
  const day = t => t ? new Date(t).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : '还没用过';
  box.innerHTML = `
    <p>电脑上一条命令把整个文件夹传上来（断点续传、自动去重、原图原样传）。<a href="api.html" target="_blank">📖 API 文档</a></p>
    ${fresh ? `<div class="keynew"><b>新密钥（只显示这一次，复制好）：</b><code id="key-val">${esc(fresh)}</code>
      <button class="btn sm" id="key-copy">复制</button>
      <pre>curl -O ${location.origin}/photos/np_upload.py
NP_KEY=${esc(fresh)} python3 np_upload.py ~/Pictures/冰岛</pre></div>` : ''}
    <button class="btn sm pri" id="key-new">＋ 生成一个密钥</button>
    ${ks.length ? `<ul class="keys">${ks.map(k => `<li>🔑 ${esc(k.name)} <span class="s">· ${day(k.created)} 建 · 最近使用 ${day(k.used)}</span>
      <button class="btn ghost sm danger" data-revoke="${k.id}">撤销</button></li>`).join('')}</ul>` : ''}
    <p class="s">密钥 = 你本人的身份，用它传的照片记在你名下。别发到群里；不用了就撤销。</p>`;
}
$('#apikeys').addEventListener('toggle', e => { if (e.target.open) renderKeys(); });
$('#keys-box').addEventListener('click', async e => {
  const t = e.target;
  try {
    if (t.id === 'key-new') {
      const name = prompt('给这个密钥起个名字（比如「家里的 Mac」）', '我的电脑'); if (name == null) return;
      const r = await api('/keys', { method: 'POST', body: { name } }); return renderKeys(r.key);
    }
    if (t.id === 'key-copy') { await navigator.clipboard.writeText($('#key-val').textContent); return toast('已复制'); }
    if (t.dataset.revoke && confirm('撤销后用这个密钥的脚本马上就传不了了。撤销？')) { await api('/keys/revoke', { method: 'POST', body: { id: Number(t.dataset.revoke) } }); renderKeys(); }
  } catch (err) { toast(err.message); }
});
function openSheet() { $('#upsheet').hidden = false; renderUp(); showQuota(); }
// 存储用量（只有设了上限时才显示）：快满了标黄，满了标红
async function showQuota() {
  let q; try { q = (await api('/stats')).quota; } catch { return; }
  const el = $('#quota'); if (!q || !q.cap) { el.hidden = true; return; }
  const gb = b => (b / 1e9).toFixed(1), pct = q.used / q.cap;
  el.hidden = false; el.classList.toggle('warn', pct > 0.9);
  el.innerHTML = `💾 相册存储：已用 <b>${gb(q.used)}</b> / ${gb(q.cap)} GB${pct >= 1 ? ' —— <b>已满，暂停接收新文件</b>' : ''}`;
}
$('#btn-up').onclick = () => openSheet();
$('#up-close').onclick = () => { $('#upsheet').hidden = true; };
$('#pick-more').onclick = () => $('#file').click();   // 和点大框一样：开照片选择器，选中的排在正在传的后面
// iPhone 上点完 ✓，系统要先把每张照片转好、拷给网页（几百张 + 视频要好几分钟），这段时间网页收不到任何东西 ——
// 不提示的话看起来就是「点了上传没反应」。所以一点开选择器就挂一条常驻提示，文件到了再换成「收到 N 个」
// 这台手机准备一张照片要几秒（指数平均，存本机）：用来建议「每批选多少张」—— 让每次只等 ~20 秒，等的同时上一批在传
const PREP = {
  get() { const v = Number(localStorage.np_prep); return v > 0 ? v : null; },
  add(ms, n) { if (!(ms > 2000 && n > 0)) return; const per = ms / n / 1000, o = this.get(); localStorage.np_prep = String(o ? o * 0.6 + per * 0.4 : per); },
  batch() { const v = this.get(); return v ? Math.max(10, Math.min(100, Math.round(20 / v / 5) * 5)) : null; },
};
// 「手机准备照片」这一段（从 iCloud 下载原图 + 转 JPEG / 重新压缩视频）网页看不见，只能量「点开选择器 → 拿到文件」一共多久
let pickT0 = 0, pickTick = 0;
const mmss = ms => { const s = Math.round(ms / 1000); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; };
for (const sel of ['#file', '#file-v']) {
  const kind = sel === '#file' ? '照片' : '视频';
  $(sel).addEventListener('click', () => {
    pickT0 = Date.now(); clearInterval(pickTick);
    const show = () => toast(`📲 正在等手机把选中的${kind}交过来… 已等 ${mmss(Date.now() - pickT0)}<br>${kind === '照片'
      ? '手机这时在从 iCloud 下载原图、转成 JPEG —— 选得多会等好几分钟' : '手机这时在把每段视频重新压缩 —— 视频越长越久；下次可以选「选取文件」，不用压缩'}，别关页面、别锁屏`, 0);
    show(); pickTick = setInterval(() => { if (document.visibilityState === 'visible') show(); }, 1000);
  });
  $(sel).addEventListener('cancel', () => { clearInterval(pickTick); $('#toast').hidden = true; });
  $(sel).addEventListener('change', e => {
    clearInterval(pickTick);
    const fs = [...e.target.files]; e.target.value = '';
    const pickMs = pickT0 && Date.now() - pickT0 < 3 * 3600e3 ? Date.now() - pickT0 : null; pickT0 = 0;
    if (sel === '#file') PREP.add(pickMs, fs.length);
    const k = PREP.batch();
    if (fs.length) toast(`收到 ${fs.length} 个文件${pickMs > 5000 ? `（手机准备用了 ${mmss(pickMs)}）` : ''}，开始上传` +
      (k && fs.length > k * 1.5 ? `<br>💡 这台手机每张要准备约 ${PREP.get().toFixed(1)} 秒，下次每批选 ${k} 张左右，传的同时点「再选一批」会更顺` : ''), 7000);
    else $('#toast').hidden = true;
    enqueue(fs, { src: sel === '#file' ? 'picker' : 'picker-video', pickMs });
  });
}
$('#dir').addEventListener('change', e => { enqueue([...e.target.files], { src: 'dir' }); e.target.value = ''; });
// 上传完一张就要刷新列表：第一张 1.2 秒后刷，之后连续上传时最多每 10 秒刷一次（以前是每次都往后推，
// 一直在传就一直不刷，传完才一下子全部跳出来）。重画 250 张的时间线在慢手机上约 0.25 秒，10 秒一次是折中
let listT = 0, listLast = 0;
function listSoon() {
  if (listT) return;
  const wait = Math.max(1200, 10000 - (Date.now() - listLast));
  listT = setTimeout(() => { listT = 0; listLast = Date.now(); bgRefresh(); }, wait);
}

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
document.addEventListener('visibilitychange', () => { wake(); if (document.visibilityState === 'visible' && S.me) bgRefresh(); });
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
  // 上次没传完就被关掉了（多半是 iPhone 内存不够把页面杀了）→ 一进来就把上传面板打开，提示重选同一批
  // 上次没传完：浏览器里存着的文件直接接着传（不用重选）；没存下来的（太大 / 配额不够）照旧提示重选同一批
  const kept = await keptFiles();
  if (kept.length) {
    toast(`📦 上次没传完的 ${kept.length} 个文件还在这台手机的浏览器里，接着传`, 6000);
    enqueue(kept, { src: 'restore' });
    UQ.forEach(t => { if (kept.includes(t.f)) t.kept = true; });              // 传完删存档
  }
  if (Object.values(FP.all()).some(x => (x.q === 1 || x.u === 1) && !x.done && x.at > Date.now() - 7 * 86400e3)) openSheet();
  setInterval(() => { if (document.visibilityState === 'visible') bgRefresh(); }, 15000);
}
if (typeof nav === 'function') document.body.insertAdjacentHTML('afterbegin', nav());   // 全站统一导航（/app.js）
boot();

// 给自动化测试用：不影响正常使用
window.__album = { S, enqueue, UQ, refresh, runSearch };
