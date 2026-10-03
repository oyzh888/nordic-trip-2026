/**
 * nordic-photos —— 北欧 2026 共享相册（挂在 nordic.airacle.com/photos/ 下）
 *
 * 分工：
 *   · 这个 Worker：鉴权、文件字节的进出（上传分片 → R2、下载/视频拖动 → R2 Range、打包 zip 流）
 *   · Album（Durable Object，album.js）：所有元数据和搜索，强一致、长驻内存
 *   · GPU 分析端（photos/pipeline/）：只做「锦上添花」—— 它不在线时上传/浏览/下载全部照常
 *
 * 为什么放在 Cloudflare 而不是在 GPU 机上起一个 Immich：
 * GPU 机是 pod，随时可能被重建（hostname 今年漂了 4 次）。照片是**旅途中唯一不可再生的东西**，
 * 必须存在一个不会跟着机器消失的地方。R2 + Worker 没有服务器要维护，也不会因为 pod 重建而打不开。
 *
 * 鉴权：整个站是公开的，但照片不是。进相册要一个口令（Worker secret ALBUM_PASS，不在仓库里），
 * 输对之后发一个 HMAC 签名的 cookie（30 天）。邀请链接 /photos/#k=口令 可以直接发到群里。
 */
import { Album } from './album.js';
import { zipPlan, zipWrite, uniqueNames } from './zip.js';

export { Album };

const PART = 8 * 2 ** 20;
const ONESHOT = 8 * 2 ** 20;                   // 一步上传（/api/upload/file）的上限 = 一块，见那里的注释                      // 8 MB：R2 分片下限 5 MB，8 MB 在手机网络上重传代价也小
const COOKIE = 'np_sess';
const enc = new TextEncoder();

const J = (d, s = 200, h = {}) => new Response(typeof d === 'string' ? d : JSON.stringify(d), {
  status: s, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...h },
});
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const b64u = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

let CRC_T = null;
function crc32(u8) {
  if (!CRC_T) {
    CRC_T = new Uint32Array(256);
    for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; CRC_T[n] = c >>> 0; }
  }
  let c = 0xFFFFFFFF;
  for (let i = 0; i < u8.length; i++) c = CRC_T[(c ^ u8[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

let hkey = null;
async function sign(env, msg) {
  if (!hkey) hkey = await crypto.subtle.importKey('raw', enc.encode(env.SESSION_SECRET), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return b64u(await crypto.subtle.sign('HMAC', hkey, enc.encode(msg)));
}
/** 口令宽松比较：手机键盘会自动把首字母大写、中文输入法会打出全角字符和「—」—— 这些都不该算错 */
function normPass(s) { return String(s || '').normalize('NFKC').toLowerCase().replace(/[\s\u2010-\u2015\u2212_-]+/g, '-').replace(/^-|-$/g, ''); }

function safeEq(a, b) {
  a = String(a); b = String(b);
  if (a.length !== b.length) return false;
  let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
async function who(req, env, album) {
  const auth = req.headers.get('authorization') || '';
  if (env.PIPE_TOKEN && safeEq(auth, 'Bearer ' + env.PIPE_TOKEN)) return { pipe: true };
  // 个人 API 密钥（np_ 开头）：和登录后的 cookie 等价，只是给脚本用；库里只存哈希
  const k = /^Bearer (np_[A-Za-z0-9_-]{20,80})$/.exec(auth);
  if (k) { const uid = await album.keyUser(hex(await crypto.subtle.digest('SHA-256', enc.encode(k[1])))); return uid ? { uid, key: true } : null; }
  const m = /(?:^|;\s*)np_sess=([^;]+)/.exec(req.headers.get('cookie') || '');
  if (!m) return null;
  const [uid, exp, sig] = m[1].split('.');
  if (!sig || Number(exp) < Date.now() / 1000) return null;
  if (!safeEq(sig, await sign(env, `${uid}.${exp}`))) return null;
  // 签名对、但库里没有这个人（换过库 / 用户被删）→ 当没登录，让他重新报名字；否则旧 cookie 会冒充新库里同编号的另一个人
  if (!(await album.user(Number(uid)))) return null;
  return { uid: Number(uid) };
}

async function serveObject(req, env, key, { dl, name, type } = {}) {
  const obj = await env.BUCKET.get(key, { range: req.headers, onlyIf: req.headers });
  if (!obj) return new Response('not found', { status: 404, headers: { 'cache-control': 'no-store' } });
  const h = new Headers();
  obj.writeHttpMetadata(h);
  if (type) h.set('content-type', type);
  h.set('etag', obj.httpEtag);
  // 内容寻址（文件名就是内容哈希）→ 永远不会变 → 浏览器可以永久缓存，翻相册第二次是零流量
  h.set('cache-control', 'private, max-age=31536000, immutable');
  h.set('accept-ranges', 'bytes');
  if (dl) h.set('content-disposition', `attachment; filename*=UTF-8''${encodeURIComponent(name || 'file')}`);
  if (!('body' in obj) || !obj.body) return new Response(null, { status: 304, headers: h });
  let status = 200;
  if (obj.range && req.headers.has('range')) {
    const r = obj.range;
    // 注意 R2 返回的对象里 suffix 键可能存在但值是 undefined —— 用 'suffix' in r 判断会得到 NaN
    const suf = r.suffix != null;
    const off = suf ? obj.size - r.suffix : (r.offset || 0);
    const len = suf ? r.suffix : (r.length ?? obj.size - off);
    h.set('content-range', `bytes ${off}-${off + len - 1}/${obj.size}`);
    h.set('content-length', String(len));
    status = 206;
  } else h.set('content-length', String(obj.size));
  return new Response(obj.body, { status, headers: h });
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    let p = url.pathname;
    // 跑在本机时（ORIGIN_KEY 有值）：经 Cloudflare 进来的请求（带 cf-ray）必须是主站 Worker 转发的、带着共享密钥，
    // 不许绕过主站直接打 tunnel 域名（否则可以伪造 x-real-ip 躲开登录失败限流）。本机直连（GPU 端）不受影响
    if (env.ORIGIN_KEY && req.headers.get('cf-ray') && !safeEq(req.headers.get('x-origin-key') || '', env.ORIGIN_KEY))
      return new Response('forbidden', { status: 403 });
    // 相对地址：经主站转发时 url.origin 是 tunnel 域名，绝对地址会把浏览器带过去
    if (p === '/photos') return new Response(null, { status: 301, headers: { location: '/photos/' + url.search } });
    if (!p.startsWith('/photos/api/') && !p.startsWith('/photos/f/')) return env.ASSETS.fetch(req);

    const album = env.ALBUM.get(env.ALBUM.idFromName('nordic-2026'));
    p = p.slice('/photos'.length);
    const method = req.method;
    const body = async () => { try { return await req.json(); } catch { return {}; } };

    /* ---- 登录（唯一不需要身份的接口） ---- */
    if (p === '/api/login' && method === 'POST') {
      const ip = (env.ORIGIN_KEY && req.headers.get('x-real-ip')) || req.headers.get('cf-connecting-ip') || 'x';
      if (!(await album.loginAllowed(ip))) return J({ error: '尝试太多次了，一小时后再试' }, 429);
      const { pass, name } = await body();
      if (!env.ALBUM_PASS || !safeEq(normPass(pass), normPass(env.ALBUM_PASS))) {
        await album.loginFailed(ip);
        return J({ error: '口令不对' }, 403);
      }
      // 口令对了但还没报名字 → 把已有的名字给前端，点一下就行，不用每个人重新打字
      if (!name) return J({ ok: true, need: 'name', users: JSON.parse((await album.list()).body).users });
      const user = await album.login(name);
      const exp = Math.floor(Date.now() / 1000) + 30 * 86400;
      const v = `${user.id}.${exp}.${await sign(env, `${user.id}.${exp}`)}`;
      return J({ user }, 200, { 'set-cookie': `${COOKIE}=${v}; Path=/photos; Max-Age=${30 * 86400}; HttpOnly; Secure; SameSite=Lax` });
    }
    if (p === '/api/logout') return J({ ok: true }, 200, { 'set-cookie': `${COOKIE}=; Path=/photos; Max-Age=0; HttpOnly; Secure; SameSite=Lax` });

    const me = await who(req, env, album);
    if (!me) return J({ error: 'login' }, 401);
    const uid = me.uid;
    const needUser = () => { if (!uid) throw new HttpError(403, 'user only'); };
    const needPipe = () => { if (!me.pipe) throw new HttpError(403, 'pipeline only'); };

    // 同一个文件被多个线程同时写（R2 对同一个对象有并发上限）：返回可重试的 503，而不是一个 500 错误页
    const busy = h => J({ error: '同一个文件正在被另一处同时上传，稍后重试', h, retry: true }, 503, { 'retry-after': '2' });
    const settle = async h => {
      for (let i = 0; i < 20; i++) {
        const m = await album.partInfo(h);
        if (m && m.status === 'ready') return J({ h, status: 'exists' });
        await new Promise(r => setTimeout(r, 500));
      }
      return busy(h);
    };

    try {
      /* ---- 文件字节 ---- */
      const fm = /^\/f\/([0-9a-f]{64})\/(o|t|p|v)$/.exec(p);
      if (fm && (method === 'GET' || method === 'HEAD')) {
        const [, h, k] = fm;
        if (k === 'o') {
          const m = await album.meta(h);
          if (!m || m.status !== 'ready') return J({ error: 'not found' }, 404);
          return serveObject(req, env, 'o/' + h, { dl: url.searchParams.has('dl'), name: m.name, type: m.type });
        }
        return serveObject(req, env, `${k}/${h}.${k === 'v' ? 'mp4' : 'jpg'}`, { type: k === 'v' ? 'video/mp4' : 'image/jpeg' });
      }

      if (p === '/api/me') { needUser(); return J({ user: await album.user(uid) }); }

      if (p === '/api/list') {
        const { ver, epoch, body: b } = await album.list();
        const etag = `"v${epoch}-${ver}"`;           // 带库编号：换了库版本号会从头数，不能和浏览器缓存里旧库的撞上
        // CF 边缘压缩时会把强 ETag 改成弱的 W/"v12"，浏览器原样带回来 → 比较时去掉 W/
        const inm = (req.headers.get('if-none-match') || '').split(',').map(x => x.trim().replace(/^W\//, ''));
        if (inm.includes(etag)) return new Response(null, { status: 304, headers: { etag } });
        return J(b, 200, { etag, 'cache-control': 'private, no-cache' });
      }
      if (p === '/api/stats') return J(await album.stats());
      if (p === '/api/search') {
        const q = url.searchParams.get('q') || (await body()).q;
        return J(await album.search(q));
      }
      if (p === '/api/suggest') return J(await album.suggest());
      if (p === '/api/people') return J(await album.people());

      /* ---- API 密钥：只能在登录的网页里建（拿着密钥不能再建密钥） ---- */
      if (p === '/api/keys' && method === 'POST') {
        needUser(); if (me.key) return J({ error: '请在网页里登录后创建' }, 403);
        const key = 'np_' + b64u(crypto.getRandomValues(new Uint8Array(24)));
        const r = await album.createKey(uid, (await body()).name, hex(await crypto.subtle.digest('SHA-256', enc.encode(key))));
        return J({ ...r, key });
      }
      if (p === '/api/keys' && method === 'GET') { needUser(); return J(await album.listKeys(uid)); }
      if (p === '/api/keys/revoke' && method === 'POST') { needUser(); return J(await album.revokeKey(uid, (await body()).id)); }

      /* ---- 一步上传：一个请求传一个文件（≤ 8 MB，手机照片足够）。脚本最省事的接口；大文件走下面的分块接口。
       * 上限是线上压测定的（2026-10-02，64 线程）：3 MB / 8 MB 全过，12 MB 起开始 500 ——
       * 免费版 Worker 每个请求只有 10 ms CPU，文件越大算哈希越久。分块接口每块 8 MB，同样 64 线程全过 ---- */
      if (p === '/api/upload/file' && (method === 'PUT' || method === 'POST')) {
        needUser();
        const name = (url.searchParams.get('name') || '').slice(0, 200);
        if (!name) return J({ error: '缺 ?name=文件名' }, 400);
        const len = Number(req.headers.get('content-length') || 0);
        if (!(len > 0)) return J({ error: '要带 content-length' }, 411);
        if (len > ONESHOT) return J({ error: '超过 8 MB，用分块接口（/api/upload/init → part → complete）或 np_upload.py' }, 413);
        const buf = new Uint8Array(await req.arrayBuffer());
        if (!buf.byteLength) return J({ error: 'empty' }, 400);
        if (buf.byteLength > ONESHOT) return J({ error: '超过 8 MB，用分块接口' }, 413);
        const n = Math.max(1, Math.ceil(buf.byteLength / PART)), cat = new Uint8Array(n * 32), shas = [];
        for (let i = 0; i < n; i++) {
          const d = await crypto.subtle.digest('SHA-256', buf.subarray(i * PART, Math.min(buf.byteLength, (i + 1) * PART)));
          cat.set(new Uint8Array(d), i * 32); shas.push(hex(d));
        }
        const h = hex(await crypto.subtle.digest('SHA-256', cat));
        const type = req.headers.get('content-type') && !/octet-stream|form/.test(req.headers.get('content-type')) ? req.headers.get('content-type') : '';
        // crc（打包下载要用）不在这里算：JS 逐字节算 CRC 很费 CPU，免费版每个请求只有 10 ms。填 0，GPU 端下载原件时补上
        const r = await album.initUpload(uid, { h, size: buf.byteLength, name, type, crc: 0, psize: PART, taken: url.searchParams.get('taken') || null });
        if (r.status === 'exists') return J({ h, status: 'exists' });
        if (r.status === 'full') return J({ h, status: 'full', error: r.error }, 413);
        if (r.status === 'wait') return busy(h);
        const info = await album.partInfo(h);
        for (let i = 1; i <= n; i++) {
          if (r.done.includes(i)) continue;
          const lease = await album.leasePart(h, i);
          if (lease === 'done') continue;
          if (lease === 'busy') return await settle(h);
          const part = buf.subarray((i - 1) * PART, Math.min(buf.byteLength, i * PART));
          let etag = '';
          try {
            if (n === 1) await env.BUCKET.put('o/' + h, part, { httpMetadata: { contentType: info.type } });
            else etag = (await env.BUCKET.resumeMultipartUpload('o/' + h, info.upload_id).uploadPart(i, part)).etag;
          } catch (e) {
            await album.partFailed(h, i);
            if (!/concurrent request rate|10058/.test(String(e))) throw e;
            return await settle(h);                     // 同一个文件被好几个线程同时传：等先到的那个传完，按「已存在」返回
          }
          await album.partDone(h, i, etag, shas[i - 1]);
        }
        const c = await album.complete(h);
        if (c.status === 'missing') return await settle(h);   // 还有块在别的线程手里 → 等它们传完
        return J({ h, status: c.status === 'done' ? 'uploaded' : c.status }, c.status === 'done' || c.status === 'exists' ? 200 : 500);
      }

      /* ---- 上传：init → part × N → complete ---- */
      if (p === '/api/upload/probe' && method === 'POST') { needUser(); return J(await album.probe(uid, (await body()).items)); }
      if (p === '/api/upload/init' && method === 'POST') {
        needUser();
        const m = await body();
        m.psize = PART;
        const r = await album.initUpload(uid, m);
        if (r.status === 'full') return J(r, 413);     // 4xx：网页和 np_upload.py 都不会重试
        return J({ ...r, psize: PART });
      }
      if (p === '/api/upload/part' && method === 'PUT') {
        needUser();
        const h = url.searchParams.get('h'), n = Number(url.searchParams.get('n'));
        const info = await album.partInfo(h);
        if (info && info.status === 'ready') return J({ ok: true, n, skipped: true, complete: true });   // 别的线程已经整份传完了
        if (!info || info.status !== 'uploading') return J({ error: 'no such upload' }, 404);
        if (!(n >= 1 && n <= info.nparts)) return J({ error: 'bad part' }, 400);
        const expect = n < info.nparts ? info.psize : info.size - info.psize * (info.nparts - 1);
        // 整块读进内存、用原生 crypto 算哈希。试过边收边写的流式版本：免费版 Worker 每个请求只有 10 ms CPU，
        // 在 JS 里逐段喂哈希会超时（Worker exceeded CPU time limit），64 线程时全部失败；整块原生算反而稳（实测 64 线程全过）
        const buf = await req.arrayBuffer();
        if (buf.byteLength !== expect) return J({ error: `part size ${buf.byteLength} != ${expect}` }, 400);
        const sha = hex(await crypto.subtle.digest('SHA-256', buf));
        const claimed = req.headers.get('x-part-sha256');
        if (claimed && claimed !== sha) return J({ error: 'part hash mismatch' }, 422);
        const lease = await album.leasePart(h, n);
        if (lease === 'done') return J({ ok: true, n, skipped: true });       // 别的线程已经传过这一块
        if (lease === 'busy') return busy(h);
        let etag = '';
        try {
          if (info.nparts === 1) await env.BUCKET.put('o/' + h, buf, { httpMetadata: { contentType: info.type } });
          else etag = (await env.BUCKET.resumeMultipartUpload('o/' + h, info.upload_id).uploadPart(n, buf)).etag;
        } catch (e) {
          await album.partFailed(h, n);
          if (/concurrent request rate|10058/.test(String(e))) return busy(h);   // 同一块被多个线程同时写：让客户端退避重试
          // 刚读完状态，别的线程就把整份收尾了（分片上传随之关闭）→ 不是错，告诉客户端已经完成
          if (/10024|does not exist/.test(String(e)) && (await album.partInfo(h))?.status === 'ready') return J({ ok: true, n, skipped: true, complete: true });
          throw e;
        }
        await album.partDone(h, n, etag, sha);
        return J({ ok: true, n });
      }
      if (p === '/api/upload/complete' && method === 'POST') {
        needUser();
        const { h } = await body();
        return J(await album.complete(h));
      }
      // 缩略图 / 预览图：上传时浏览器顺手生成（最快出图）；HEIC/视频浏览器做不了的，GPU 端补
      if (p === '/api/upload/aux' && method === 'PUT') {
        const h = url.searchParams.get('h'), k = url.searchParams.get('k');
        if (!/^[0-9a-f]{64}$/.test(h || '') || !['t', 'p', 'v'].includes(k)) return J({ error: 'bad' }, 400);
        if (!me.pipe && !(await album.isContrib(h, uid))) return J({ error: 'not yours' }, 403);
        if (k === 'v') needPipe();
        const buf = await req.arrayBuffer();
        if (k !== 'v' && buf.byteLength > 3 * 2 ** 20) return J({ error: 'too big' }, 413);
        await env.BUCKET.put(`${k}/${h}.${k === 'v' ? 'mp4' : 'jpg'}`, buf, { httpMetadata: { contentType: k === 'v' ? 'video/mp4' : 'image/jpeg' } });
        if (url.searchParams.has('w')) await album.setDims(h, url.searchParams.get('w'), url.searchParams.get('hh'), url.searchParams.get('dur'));
        await album.setFlag(h, { t: 1, p: 2, v: 4 }[k]);
        return J({ ok: true });
      }

      /* ---- AI 改图：这里只排队；真正调模型的是 GPU 端（它手里有模型网关的凭证） ---- */
      if (p === '/api/edit' && method === 'POST') {
        needUser();
        const b = await body();
        if (!/^[0-9a-f]{64}$/.test(b.h || '')) return J({ error: 'bad' }, 400);
        const r = await album.editCreate(uid, { h: b.h, prompt: b.prompt, model: b.model });
        return J(r, r.error ? 400 : 200);
      }
      if (p === '/api/edit') {
        needUser();
        const r = await album.editGet(uid, url.searchParams.get('id'));
        return r ? J(r) : J({ error: 'not found' }, 404);
      }

      if (p === '/api/pick' && method === 'POST') { needUser(); return J(await album.pick((await body()).h)); }
      if (p === '/api/delete' && method === 'POST') { needUser(); return J(await album.remove(uid, (await body()).h)); }

      /* ---- 人物 ---- */
      if (p === '/api/people/claim' && method === 'POST') {
        needUser();
        const b = await body();
        const target = b.me ? { uid } : b.person ? { person: Number(b.person) } : { name: b.name };
        return J(await album.claim({ cluster: b.cluster ?? null, face: b.face ?? null }, target));
      }
      if (p === '/api/people/unassign' && method === 'POST') { needUser(); return J(await album.unassign(Number((await body()).face))); }
      if (p === '/api/people/merge' && method === 'POST') {
        needUser(); const b = await body();
        const r = b.into === 'me' ? await album.claimPerson(Number(b.from), uid) : await album.mergePersons(Number(b.from), Number(b.into));
        return J(r, r.error ? 400 : 200);
      }
      if (p === '/api/people/rename' && method === 'POST') { needUser(); const b = await body(); return J(await album.renamePerson(Number(b.person), b.name)); }

      /* ---- 打包下载：先 POST 选中的 id 拿 token，再用普通链接下载（走浏览器自带的下载管理器） ---- */
      if (p === '/api/zip' && method === 'POST') {
        const { ids, name } = await body();
        if (!Array.isArray(ids) || !ids.length) return J({ error: 'empty' }, 400);
        const token = await album.zipCreate(ids.filter(x => /^[0-9a-f]{64}$/.test(x)));
        const fname = String(name || 'nordic-photos').replace(/[\\/:*?"<>|]/g, '_').slice(0, 60);
        return J({ url: `/photos/api/zip/${token}/${encodeURIComponent(fname)}.zip` });
      }
      const zm = /^\/api\/zip\/([0-9a-f-]{36})\/(.+)$/.exec(p);
      if (zm) {
        const entries = await album.zipEntries(zm[1]);
        if (!entries) return J({ error: '链接过期了，重新点一次下载' }, 404);
        const names = uniqueNames(entries.map(e => e.name));
        const plan = zipPlan(entries.map((e, i) => ({ ...e, name: names[i] })));
        const { readable, writable } = new FixedLengthStream(plan.total);
        ctx.waitUntil(zipWrite(writable, plan, async i => (await env.BUCKET.get('o/' + entries[i].h)).body));
        return new Response(readable, { headers: {
          'content-type': 'application/zip', 'content-length': String(plan.total), 'cache-control': 'no-store',
          'content-disposition': `attachment; filename*=UTF-8''${zm[2]}`,
        } });
      }

      /* ---- GPU 分析端专用 ---- */
      if (p.startsWith('/api/pipe/')) {
        needPipe();
        if (p === '/api/pipe/ws') {
          if (req.headers.get('upgrade') !== 'websocket') return J({ error: 'need websocket' }, 426);
          return album.fetch(req);
        }
        if (p === '/api/pipe/pending') return J(await album.pending(Number(url.searchParams.get('aver') || 1), Number(url.searchParams.get('limit') || 50)));
        if (p === '/api/pipe/result' && method === 'POST') return J(await album.result(await body()));
        if (p === '/api/pipe/clusters' && method === 'POST') return J(await album.clusters(await body()));
        if (p === '/api/pipe/vecs' && method === 'POST') return J(await album.putQvecs((await body()).items));
        if (p === '/api/pipe/status') return J(await album.pipeStatus());
        if (p === '/api/pipe/known') return J(await album.knownQueries());
        if (p === '/api/pipe/faces') return J(await album.dumpFaces());
        if (p === '/api/pipe/media') return J(await album.media4pipe());
        if (p === '/api/pipe/embs') return J(await album.embs());
        if (p === '/api/pipe/edits') return J(await album.editsPending());
        if (p === '/api/pipe/edit/start' && method === 'POST') return J(await album.editStart((await body()).id));
        if (p === '/api/pipe/edit/fail' && method === 'POST') { const b = await body(); return J(await album.editFail(b.id, b.err)); }
        // 改好的图：内容 ID 在这边按和浏览器上传一样的算法重算（不信任调用方），再登记成新照片
        if (p === '/api/pipe/edit/out' && method === 'PUT') {
          const buf = new Uint8Array(await req.arrayBuffer());
          if (!buf.byteLength || buf.byteLength > 40 * 2 ** 20) return J({ error: 'bad size' }, 400);
          const type = req.headers.get('content-type') === 'image/png' ? 'image/png' : 'image/jpeg';
          const n = Math.ceil(buf.byteLength / PART), cat = new Uint8Array(n * 32);
          for (let i = 0; i < n; i++) cat.set(new Uint8Array(await crypto.subtle.digest('SHA-256', buf.subarray(i * PART, (i + 1) * PART))), i * 32);
          const h = hex(await crypto.subtle.digest('SHA-256', cat));
          await env.BUCKET.put('o/' + h, buf, { httpMetadata: { contentType: type } });
          const q = url.searchParams;
          return J(await album.editDone(q.get('id'), { h, size: buf.byteLength, crc: crc32(buf), type, w: q.get('w'), hh: q.get('hh'), mid: q.get('mid') }));
        }
        if (p === '/api/pipe/dump' && method === 'GET') return J(await album.dumpAll());
        if (p === '/api/pipe/restore' && method === 'POST') return J(await album.restoreAll(await body()));
        if (p === '/api/pipe/import' && method === 'POST') return J(await album.importMedia((await body()).items));
        if (p === '/api/pipe/blob' && method === 'PUT') {      // 搬家：把本地存储里的字节原样写回 BUCKET
          const k = url.searchParams.get('k') || '';
          if (!/^(o\/[0-9a-f]{64}|[tp]\/[0-9a-f]{64}\.jpg|v\/[0-9a-f]{64}\.mp4)$/.test(k)) return J({ error: 'bad key' }, 400);
          await env.BUCKET.put(k, await req.arrayBuffer(), { httpMetadata: { contentType: req.headers.get('content-type') || 'application/octet-stream' } });
          return J({ ok: true });
        }
        if (p === '/api/pipe/disk' && method === 'POST') return J(await album.setDisk(await body()));
        if (p === '/api/pipe/purge' && method === 'POST') {
          const { keys } = await album.purge(await body());
          for (let i = 0; i < keys.length; i += 1000) await env.BUCKET.delete(keys.slice(i, i + 1000));
          return J({ ok: true, deleted: keys.length / 4 });
        }
      }
      return J({ error: 'not found' }, 404);
    } catch (e) {
      if (e instanceof HttpError) return J({ error: e.message }, e.status);
      return J({ error: String(e && e.message || e) }, 500);
    }
  },
};


class HttpError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
