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

const PART = 8 * 2 ** 20;                      // 8 MB：R2 分片下限 5 MB，8 MB 在手机网络上重传代价也小
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
function safeEq(a, b) {
  a = String(a); b = String(b);
  if (a.length !== b.length) return false;
  let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
async function who(req, env) {
  const auth = req.headers.get('authorization') || '';
  if (env.PIPE_TOKEN && safeEq(auth, 'Bearer ' + env.PIPE_TOKEN)) return { pipe: true };
  const m = /(?:^|;\s*)np_sess=([^;]+)/.exec(req.headers.get('cookie') || '');
  if (!m) return null;
  const [uid, exp, sig] = m[1].split('.');
  if (!sig || Number(exp) < Date.now() / 1000) return null;
  if (!safeEq(sig, await sign(env, `${uid}.${exp}`))) return null;
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
    if (p === '/photos') return Response.redirect(url.origin + '/photos/' + url.search + url.hash, 301);
    if (!p.startsWith('/photos/api/') && !p.startsWith('/photos/f/')) return env.ASSETS.fetch(req);

    const album = env.ALBUM.get(env.ALBUM.idFromName('nordic-2026'));
    p = p.slice('/photos'.length);
    const method = req.method;
    const body = async () => { try { return await req.json(); } catch { return {}; } };

    /* ---- 登录（唯一不需要身份的接口） ---- */
    if (p === '/api/login' && method === 'POST') {
      const ip = req.headers.get('cf-connecting-ip') || 'x';
      if (!(await album.loginAllowed(ip))) return J({ error: '尝试太多次了，一小时后再试' }, 429);
      const { pass, name } = await body();
      if (!env.ALBUM_PASS || !safeEq(String(pass || '').trim(), env.ALBUM_PASS)) {
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

    const me = await who(req, env);
    if (!me) return J({ error: 'login' }, 401);
    const uid = me.uid;
    const needUser = () => { if (!uid) throw new HttpError(403, 'user only'); };
    const needPipe = () => { if (!me.pipe) throw new HttpError(403, 'pipeline only'); };

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
        const { ver, body: b } = await album.list();
        const etag = `"v${ver}"`;
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

      /* ---- 上传：init → part × N → complete ---- */
      if (p === '/api/upload/init' && method === 'POST') {
        needUser();
        const m = await body();
        m.psize = PART;
        const r = await album.initUpload(uid, m);
        return J({ ...r, psize: PART });
      }
      if (p === '/api/upload/part' && method === 'PUT') {
        needUser();
        const h = url.searchParams.get('h'), n = Number(url.searchParams.get('n'));
        const info = await album.partInfo(h);
        if (!info || info.status !== 'uploading') return J({ error: 'no such upload' }, 404);
        if (!(n >= 1 && n <= info.nparts)) return J({ error: 'bad part' }, 400);
        const expect = n < info.nparts ? info.psize : info.size - info.psize * (info.nparts - 1);
        const buf = await req.arrayBuffer();
        if (buf.byteLength !== expect) return J({ error: `part size ${buf.byteLength} != ${expect}` }, 400);
        // 服务端自己算这一块的 SHA-256，不信客户端 —— complete 时要用它复核整份文件
        const sha = hex(await crypto.subtle.digest('SHA-256', buf));
        const claimed = req.headers.get('x-part-sha256');
        if (claimed && claimed !== sha) return J({ error: 'part hash mismatch' }, 422);
        let etag = '';
        if (info.nparts === 1) {
          await env.BUCKET.put('o/' + h, buf, { httpMetadata: { contentType: info.type } });
        } else {
          const mp = env.BUCKET.resumeMultipartUpload('o/' + h, info.upload_id);
          etag = (await mp.uploadPart(n, buf)).etag;
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
