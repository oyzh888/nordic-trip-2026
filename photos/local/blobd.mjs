// blobd —— 相册的本地文件存储：照片原样存成普通文件（files/o/<内容哈希>、files/t/<h>.jpg …），
// 替代 wrangler dev 里用 JS 模拟的 R2（那一层把每个字节在单线程 JS 里搬好几遍，是上传速度的瓶颈）。
//
// 只给本机的相册 Worker 调（绑 127.0.0.1 + 共享令牌）。接口是 R2 用到的那一小撮：
//   PUT    /o/<key>                         整个文件（流式写临时文件 → 原子改名），回 {size, sha256}
//   POST   /mp/<key>                        开一个分块上传，回 {uploadId}
//   PUT    /mp/<key>/<uploadId>/<n>         写第 n 块，回 {etag, size, sha256}（etag 就是这一块的 sha256）
//   POST   /mp/<key>/<uploadId>/complete    {parts:[{partNumber, etag}]} → 按顺序拼成最终文件
//   DELETE /mp/<key>/<uploadId>             放弃
//   GET / HEAD /o/<key>                     支持 Range（单段）和 If-None-Match
//   POST   /delete                          {keys:[…]}
// 多进程（node:cluster）：每个进程各自收流、算哈希、写盘，能用上多个核。
//   用法：BLOBD_DIR=… BLOBD_TOKEN=… BLOBD_PORT=41071 BLOBD_PROCS=8 node blobd.mjs
import cluster from 'node:cluster';
import http from 'node:http';
import fs from 'node:fs';
import fsp from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { pipeline } from 'node:stream/promises';

const DIR = path.resolve(process.env.BLOBD_DIR || './files');
const PORT = Number(process.env.BLOBD_PORT || 41071);
const TOKEN = process.env.BLOBD_TOKEN || '';
const PROCS = Number(process.env.BLOBD_PROCS || 8);
const KEY_RE = /^(o\/[0-9a-f]{64}|[tpf]\/[0-9a-f]{64}\.jpg|v\/[0-9a-f]{64}\.mp4|x\/[0-9A-Za-z._-]{1,120})$/;   // x/ = 测试用
const TMP = path.join(DIR, '.tmp'), MP = path.join(DIR, '.mp');

if (cluster.isPrimary) {
  for (const d of [DIR, TMP, MP, ...['o', 't', 'p', 'v', 'f', 'x'].map(k => path.join(DIR, k))]) fs.mkdirSync(d, { recursive: true });
  for (let i = 0; i < PROCS; i++) cluster.fork();
  cluster.on('exit', (w, code) => { console.error(`[blobd] 进程 ${w.process.pid} 退出（${code}），重启`); cluster.fork(); });
  console.log(`[blobd] ${PROCS} 个进程 · 127.0.0.1:${PORT} · ${DIR}`);
} else {
  http.createServer(handle).listen(PORT, '127.0.0.1');
}

const J = (res, code, obj) => { const b = JSON.stringify(obj); res.writeHead(code, { 'content-type': 'application/json', 'content-length': Buffer.byteLength(b) }); res.end(b); };
const rid = () => crypto.randomBytes(12).toString('hex');
const fpath = key => path.join(DIR, key);

/** 把请求体流式写进 file，边写边算 sha256；写完再原子改名到 dest（dest 为空就留在 file） */
async function sink(req, file, dest) {
  const h = crypto.createHash('sha256'); let size = 0;
  const out = fs.createWriteStream(file, { highWaterMark: 1 << 20 });
  req.on('data', c => { h.update(c); size += c.length; });
  await pipeline(req, out);
  if (dest) await fsp.rename(file, dest);
  return { size, sha256: h.digest('hex') };
}

async function readJson(req) { const cs = []; for await (const c of req) cs.push(c); return JSON.parse(Buffer.concat(cs).toString() || '{}'); }

async function handle(req, res) {
  // 不复用连接：Node 默认 5 秒关掉空闲长连接，workerd 恰好拿那条已关的连接发流式请求体时没法重发，
  // 报「Network connection lost」（实测 np_upload 并发时偶发）。本机建连接几乎不花时间，干脆每次都关
  res.shouldKeepAlive = false;
  try {
    if (TOKEN && req.headers['x-blobd-token'] !== TOKEN) return J(res, 403, { error: 'token' });
    const u = new URL(req.url, 'http://x'); const p = decodeURIComponent(u.pathname); const m = req.method;

    if (p.startsWith('/o/')) {
      const key = p.slice(3);
      if (!KEY_RE.test(key)) return J(res, 400, { error: 'bad key' });
      if (m === 'PUT') return J(res, 200, await sink(req, path.join(TMP, rid()), fpath(key)));
      if (m === 'GET' || m === 'HEAD') return serve(req, res, fpath(key));
    }
    if (p.startsWith('/mp/')) {
      const parts = p.slice(4).split('/');
      // /mp/<o>/<h>[/<uploadId>[/<n>|/complete]]  —— key 本身带一个斜杠
      const key = parts.slice(0, 2).join('/'), id = parts[2], n = parts[3];
      if (!KEY_RE.test(key) || (id && !/^[0-9a-f]{24}$/.test(id))) return J(res, 400, { error: 'bad key' });
      if (m === 'POST' && !id) { const up = rid(); await fsp.mkdir(path.join(MP, up)); return J(res, 200, { uploadId: up }); }
      const d = path.join(MP, id);
      if (!fs.existsSync(d)) return J(res, 404, { error: 'no such upload' });
      if (m === 'PUT' && /^\d+$/.test(n)) {
        // 先写临时名、写完再改名：同一块被两个线程同时写时，后到的那个不会写坏先到的
        const r = await sink(req, path.join(d, `${n}.${rid()}.tmp`), path.join(d, String(Number(n))));
        return J(res, 200, { ...r, etag: r.sha256, partNumber: Number(n) });
      }
      if (m === 'POST' && n === 'complete') {
        const { parts: ps = [] } = await readJson(req);
        const tmp = path.join(TMP, rid());
        const out = fs.createWriteStream(tmp);
        try {
          for (const { partNumber } of [...ps].sort((a, b) => a.partNumber - b.partNumber)) {
            const f = path.join(d, String(partNumber));
            if (!fs.existsSync(f)) { out.destroy(); await fsp.rm(tmp, { force: true }); return J(res, 409, { error: `part ${partNumber} could not be found` }); }
            await pipeline(fs.createReadStream(f, { highWaterMark: 1 << 20 }), out, { end: false });
          }
          await new Promise((ok, bad) => out.end(e => (e ? bad(e) : ok())));
        } catch (e) { out.destroy(); await fsp.rm(tmp, { force: true }); throw e; }
        await fsp.rename(tmp, fpath(key));
        await fsp.rm(d, { recursive: true, force: true });
        const st = await fsp.stat(fpath(key));
        return J(res, 200, { size: st.size });
      }
      if (m === 'DELETE') { await fsp.rm(d, { recursive: true, force: true }); return J(res, 200, { ok: true }); }
    }
    if (p === '/delete' && m === 'POST') {
      const { keys = [] } = await readJson(req); let n = 0;
      for (const k of keys) if (KEY_RE.test(k)) { try { await fsp.unlink(fpath(k)); n++; } catch { /* 本来就没有 */ } }
      return J(res, 200, { deleted: n });
    }
    if (p === '/health') return J(res, 200, { ok: true, pid: process.pid });
    J(res, 404, { error: 'not found' });
  } catch (e) {
    console.error('[blobd]', req.method, req.url, e);
    if (!res.headersSent) J(res, 500, { error: String(e) }); else res.destroy();
  }
}

/** 读文件：单段 Range、If-None-Match（etag = 大小-修改时间；内容寻址的文件不会变，够用） */
async function serve(req, res, file) {
  let st; try { st = await fsp.stat(file); } catch { return J(res, 404, { error: 'not found' }); }
  const etag = `"${st.size.toString(36)}-${Math.floor(st.mtimeMs).toString(36)}"`;
  const h = { etag, 'accept-ranges': 'bytes', 'x-size': String(st.size) };
  const inm = req.headers['if-none-match'];
  if (inm && inm.split(',').map(s => s.trim().replace(/^W\//, '')).includes(etag)) { res.writeHead(304, h); return res.end(); }
  let start = 0, end = st.size - 1, code = 200;
  const r = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
  if (r && st.size > 0) {
    if (r[1] === '' && r[2] !== '') { start = Math.max(0, st.size - Number(r[2])); }
    else { start = Number(r[1]); if (r[2] !== '') end = Math.min(end, Number(r[2])); }
    if (start > end || start >= st.size) { res.writeHead(416, { ...h, 'content-range': `bytes */${st.size}` }); return res.end(); }
    code = 206; h['content-range'] = `bytes ${start}-${end}/${st.size}`;
  }
  h['content-length'] = String(end - start + 1);
  res.writeHead(code, h);
  if (req.method === 'HEAD') return res.end();
  await pipeline(fs.createReadStream(file, { start, end, highWaterMark: 1 << 20 }), res);
}
