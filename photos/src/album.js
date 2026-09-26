/**
 * Album —— 整个相册的「大脑」：一个 Durable Object（自带 SQLite）
 *
 * 为什么是一个 DO 而不是 D1/KV：
 *   · KV 是最终一致的（跨机房最多 60 秒）—— 两个人同时传同一张照片时，去重判断必须是强一致的；
 *   · 整个相册只有一个实例 → 所有写入天然串行，不用锁；
 *   · 它是**长驻内存**的：搜索索引建一次、查询结果缓存一次，后续查询直接在内存里答。
 *     这正是「快速 cache query」的落点 —— 见下面 search() 上方那段说明。
 *
 * 数据真相都在这里（SQLite）；文件字节在 R2（o/ 原件 · t/ 缩略图 · p/ 预览图 · v/ 视频预览）。
 * GPU 分析端（photos/pipeline/）通过一条 WebSocket 连进来：有新文件就推给它，
 * 有没见过的搜索词就让它算向量。它掉线不影响上传/浏览/下载，只是新照片暂时没有 AI 标签。
 */
import { DurableObject } from 'cloudflare:workers';

const PIPE_VERSION_KEY = 'pipe_ver';
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
const unhex = s => Uint8Array.from(s.match(/../g), h => parseInt(h, 16));
const b64dec = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const now = () => Date.now();
const CJK = /[㐀-鿿]/;

/** AI 改图能选的模型（前端只显示 GPU 端报了「能用」的那几个）。实际调哪个模型 id 由 GPU 端决定并回报 */
export const EDIT_MODELS = {
  nano: 'Nano Banana 2',
  pro: 'Nano Banana Pro',
  gpt: 'GPT Image 2',
};
const EDIT_PER_DAY = 60;          // 每人每 24 小时
const EDIT_INFLIGHT = 3;          // 每人同时排队/进行中

/** 搜索词归一化：全角→半角、大小写、标点 → 空格。缓存键就是它，所以「极光 」和「极光」命中同一条 */
export function normQ(q) {
  return String(q || '').normalize('NFKC').toLowerCase()
    .replace(/[，。、；：！？,.;:!?·()（）\[\]【】"'“”‘’]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80);
}

export class Album extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.idx = null;             // 内存搜索索引（按 ver 失效）
    this.rcache = new Map();     // 查询结果 LRU：key = ver|query|hasVec
    this.qvecs = new Map();      // 查询向量（永不失效：模型不变，同一个词的向量就不变）
    this.waiters = new Map();    // 正在等 GPU 端算向量的查询
    this.listCache = null;       // list() 的序列化结果（按 ver 失效）
    ctx.blockConcurrencyWhile(async () => this.migrate());
    ctx.setWebSocketAutoResponse(new WebSocketRequestResponsePair('ping', 'pong'));
  }

  migrate() {
    this.sql.exec(`
      CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
      CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT UNIQUE, created INTEGER);
      CREATE TABLE IF NOT EXISTS media (
        h TEXT PRIMARY KEY, kind TEXT, type TEXT, name TEXT, size INTEGER, crc INTEGER,
        nparts INTEGER, psize INTEGER, upload_id TEXT, status TEXT, created INTEGER, deleted INTEGER DEFAULT 0,
        taken TEXT, lat REAL, lon REAL, w INTEGER, hh INTEGER, dur REAL,
        flags INTEGER DEFAULT 0, aver INTEGER DEFAULT 0, place TEXT, caption TEXT, tags TEXT,
        burst TEXT, cover INTEGER DEFAULT 1, scene INTEGER, sharp REAL,
        cam TEXT, score REAL, moment INTEGER, pinned INTEGER DEFAULT 0);
      CREATE TABLE IF NOT EXISTS contrib (h TEXT, uid INTEGER, at INTEGER, PRIMARY KEY (h, uid));
      CREATE TABLE IF NOT EXISTS parts (h TEXT, n INTEGER, etag TEXT, sha TEXT, PRIMARY KEY (h, n));
      CREATE TABLE IF NOT EXISTS faces (id INTEGER PRIMARY KEY, h TEXT, x REAL, y REAL, w REAL, hh REAL,
        score REAL, emb TEXT, cluster INTEGER, person INTEGER, confirmed INTEGER DEFAULT 0);
      CREATE INDEX IF NOT EXISTS faces_h ON faces(h);
      CREATE TABLE IF NOT EXISTS persons (id INTEGER PRIMARY KEY, name TEXT, uid INTEGER);
      CREATE TABLE IF NOT EXISTS emb (h TEXT PRIMARY KEY, scale REAL, vec BLOB);
      CREATE TABLE IF NOT EXISTS qvec (q TEXT PRIMARY KEY, vec BLOB, at INTEGER);
      CREATE TABLE IF NOT EXISTS qqueue (q TEXT PRIMARY KEY, at INTEGER);
      CREATE TABLE IF NOT EXISTS scenes (id INTEGER PRIMARY KEY, label TEXT, n INTEGER);
      CREATE TABLE IF NOT EXISTS moments (id INTEGER PRIMARY KEY, title TEXT, start TEXT, end TEXT, place TEXT, n INTEGER, memo REAL, cover TEXT);
      CREATE TABLE IF NOT EXISTS zips (token TEXT PRIMARY KEY, ids TEXT, at INTEGER);
      CREATE TABLE IF NOT EXISTS fails (ip TEXT, at INTEGER);
      CREATE TABLE IF NOT EXISTS edits (id INTEGER PRIMARY KEY, h TEXT, prompt TEXT, model TEXT, uid INTEGER,
        status TEXT, out_h TEXT, err TEXT, tries INTEGER DEFAULT 0, at INTEGER, started INTEGER, done INTEGER);
    `);
    // 后加的列（老库里没有）：AI 改图的产物记着它从哪张来、用什么改的
    const cols = new Set(this.sql.exec(`PRAGMA table_info(media)`).toArray().map(r => r.name));
    for (const [c, t] of [['src', 'TEXT'], ['ai', 'TEXT']]) if (!cols.has(c)) this.sql.exec(`ALTER TABLE media ADD COLUMN ${c} ${t}`);
    if (!this.sql.exec(`SELECT v FROM kv WHERE k='ver'`).toArray().length)
      this.sql.exec(`INSERT INTO kv VALUES ('ver','1')`);
  }

  /* ---------- 版本号：任何影响「列表/搜索结果」的写入都要 bump，所有缓存按它失效 ---------- */
  get ver() { return Number(this.sql.exec(`SELECT v FROM kv WHERE k='ver'`).one().v); }
  bump() {
    this.sql.exec(`UPDATE kv SET v = CAST(v AS INTEGER) + 1 WHERE k='ver'`);
    this.idx = null; this.listCache = null; this.rcache.clear();
  }
  kvGet(k, d = null) { const r = this.sql.exec(`SELECT v FROM kv WHERE k=?`, k).toArray(); return r.length ? r[0].v : d; }
  kvSet(k, v) { this.sql.exec(`INSERT INTO kv VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v`, k, String(v)); }
  /** 单调递增的序号：记下「最后一次分析结果」和「最后一次聚类」各是第几号 → 聚类号更大 = 聚类已经看过全部结果 */
  stamp(k) { const n = Number(this.kvGet('seq', 0)) + 1; this.kvSet('seq', n); this.kvSet(k, n); }
  pipeStatus() { return { res: Number(this.kvGet('res_seq', 0)), cl: Number(this.kvGet('cl_seq', 0)) }; }

  /* ---------- 身份：口令对了之后只问一个名字，不存任何别的个人信息 ---------- */
  loginAllowed(ip) {
    this.sql.exec(`DELETE FROM fails WHERE at < ?`, now() - 3600e3);
    return this.sql.exec(`SELECT COUNT(*) c FROM fails WHERE ip=?`, ip).one().c < 20;
  }
  loginFailed(ip) { this.sql.exec(`INSERT INTO fails VALUES (?,?)`, ip, now()); }
  login(name) {
    name = String(name || '').normalize('NFKC').trim().slice(0, 24);
    if (!name) throw new Error('name required');
    const r = this.sql.exec(`SELECT id, name FROM users WHERE name=?`, name).toArray();
    if (r.length) return r[0];
    this.sql.exec(`INSERT INTO users (name, created) VALUES (?,?)`, name, now());
    this.bump();
    return this.sql.exec(`SELECT id, name FROM users WHERE name=?`, name).one();
  }
  user(uid) { return this.sql.exec(`SELECT id, name FROM users WHERE id=?`, uid).toArray()[0] || null; }

  /* ---------- 上传 ----------
   * 内容 ID（h）= SHA-256( 每 8 MB 块的 SHA-256 依次拼接 )，和 Dropbox 的 content_hash 同一个思路：
   * 浏览器可以逐块算（手机上 2 GB 的视频不用一次读进内存），服务端能用已收到的块哈希**复核**整份文件。
   * 同一个 h = 同一份字节 → 秒传（只登记「我也有这张」）；
   * 同一个 h 但还没传完 → 返回已经收到的块号，客户端只补缺的 → 断点续传，换页面、换网络都能接上。
   */
  async initUpload(uid, m) {
    const h = String(m.h || '');
    if (!/^[0-9a-f]{64}$/.test(h)) throw new Error('bad hash');
    const psize = Number(m.psize), size = Number(m.size);
    const nparts = Math.max(1, Math.ceil(size / psize));
    if (!(size > 0) || !(psize >= 5 * 2 ** 20) || nparts > 10000) throw new Error('bad size');
    const cur = this.sql.exec(`SELECT status, upload_id, nparts, psize, deleted FROM media WHERE h=?`, h).toArray()[0];
    this.sql.exec(`INSERT OR IGNORE INTO contrib VALUES (?,?,?)`, h, uid, now());
    if (cur && cur.status === 'ready') {
      if (cur.deleted) this.sql.exec(`UPDATE media SET deleted=0 WHERE h=?`, h);
      this.bump();
      return { status: 'exists' };
    }
    if (cur) {
      if (cur.nparts > 1 && !cur.upload_id) return { status: 'wait' };   // 另一台设备正在建分片任务
      const done = this.sql.exec(`SELECT n FROM parts WHERE h=?`, h).toArray().map(r => r.n);
      return { status: 'upload', done, psize: cur.psize, nparts: cur.nparts };
    }
    const kind = /^video\//.test(m.type) || /\.(mov|mp4|m4v|3gp|avi|mkv)$/i.test(m.name || '') ? 'video' : 'image';
    this.sql.exec(`INSERT INTO media (h, kind, type, name, size, crc, nparts, psize, status, created, taken, lat, lon, w, hh, dur, cam)
                   VALUES (?,?,?,?,?,?,?,?, 'uploading', ?,?,?,?,?,?,?,?)`,
      h, kind, String(m.type || 'application/octet-stream').slice(0, 80), String(m.name || 'file').slice(0, 200),
      size, (Number(m.crc) >>> 0), nparts, psize, now(), m.taken || null,
      num(m.lat), num(m.lon), num(m.w), num(m.hh), num(m.dur), m.cam ? String(m.cam).slice(0, 60) : null);
    if (nparts > 1) {
      const mp = await this.env.BUCKET.createMultipartUpload('o/' + h, { httpMetadata: { contentType: m.type || 'application/octet-stream' } });
      this.sql.exec(`UPDATE media SET upload_id=? WHERE h=?`, mp.uploadId, h);
    }
    return { status: 'upload', done: [], psize, nparts };
  }

  partInfo(h) {
    return this.sql.exec(`SELECT h, size, type, nparts, psize, upload_id, status FROM media WHERE h=?`, h).toArray()[0] || null;
  }
  partDone(h, n, etag, sha) {
    this.sql.exec(`INSERT OR REPLACE INTO parts VALUES (?,?,?,?)`, h, n, etag, sha);
  }

  async complete(h) {
    const m = this.partInfo(h);
    if (!m) throw new Error('unknown upload');
    if (m.status === 'ready') return { status: 'exists' };
    const parts = this.sql.exec(`SELECT n, etag, sha FROM parts WHERE h=? ORDER BY n`, h).toArray();
    if (parts.length !== m.nparts) return { status: 'missing', done: parts.map(p => p.n) };
    // 复核：块哈希拼起来再哈希一次，必须等于客户端声称的内容 ID —— 否则就是传坏了（或有人乱写）
    const cat = new Uint8Array(parts.length * 32);
    parts.forEach((p, i) => cat.set(unhex(p.sha), i * 32));
    const got = hex(await crypto.subtle.digest('SHA-256', cat));
    if (got !== h) {
      this.sql.exec(`DELETE FROM parts WHERE h=?`, h);
      return { status: 'corrupt' };
    }
    if (m.nparts > 1) {
      const mp = this.env.BUCKET.resumeMultipartUpload('o/' + h, m.upload_id);
      await mp.complete(parts.map(p => ({ partNumber: p.n, etag: p.etag })));
    }
    this.sql.exec(`UPDATE media SET status='ready', upload_id=NULL WHERE h=?`, h);
    this.sql.exec(`DELETE FROM parts WHERE h=?`, h);
    this.bump();
    this.notifyPipe({ t: 'new', h });
    return { status: 'done' };
  }

  /** 浏览器解码缩略图时顺手量到的尺寸/时长；只填空缺，GPU 端的 EXIF/ffprobe 结果优先 */
  setDims(h, w, hh, dur) {
    this.sql.exec(`UPDATE media SET w=COALESCE(w,?), hh=COALESCE(hh,?), dur=COALESCE(dur,?) WHERE h=?`, num(w), num(hh), num(dur), h);
  }
  setFlag(h, bit) { this.sql.exec(`UPDATE media SET flags = flags | ? WHERE h=?`, bit, h); this.bump(); }
  meta(h) { return this.sql.exec(`SELECT h, kind, type, name, size, crc, taken, status, deleted FROM media WHERE h=?`, h).toArray()[0] || null; }
  isContrib(h, uid) { return this.sql.exec(`SELECT 1 FROM contrib WHERE h=? AND uid=?`, h, uid).toArray().length > 0; }

  /** 删除 = 撤回「我传过这张」；没人再认领它才真正从相册里隐藏（别人也传过的不会被我删掉） */
  remove(uid, h) {
    this.sql.exec(`DELETE FROM contrib WHERE h=? AND uid=?`, h, uid);
    const left = this.sql.exec(`SELECT COUNT(*) c FROM contrib WHERE h=?`, h).one().c;
    if (!left) this.sql.exec(`UPDATE media SET deleted=1 WHERE h=?`, h);
    this.bump();
    return { hidden: !left };
  }

  /* ---------- 列表：前端拿到全量元数据后，按天/人/类型筛选都在本机做（瞬时，不用再请求） ---------- */
  list() {
    const ver = this.ver;
    if (this.listCache && this.listCache.ver === ver) return this.listCache;
    const contrib = new Map();
    for (const r of this.sql.exec(`SELECT h, uid FROM contrib ORDER BY at`)) {
      if (!contrib.has(r.h)) contrib.set(r.h, []); contrib.get(r.h).push(r.uid);
    }
    const ppl = new Map();
    for (const r of this.sql.exec(`SELECT DISTINCT h, person FROM faces WHERE person IS NOT NULL`)) {
      if (!ppl.has(r.h)) ppl.set(r.h, []); ppl.get(r.h).push(r.person);
    }
    const nf = new Map();
    for (const r of this.sql.exec(`SELECT h, COUNT(*) c FROM faces GROUP BY h`)) nf.set(r.h, r.c);
    const items = [];
    for (const r of this.sql.exec(`SELECT * FROM media WHERE status='ready' AND deleted=0`)) {
      items.push({
        h: r.h, k: r.kind === 'video' ? 'v' : 'i', n: r.name, s: r.size, t: r.taken, c: r.created,
        w: r.w, hh: r.hh, d: r.dur, f: r.flags, a: r.aver > 0 ? 1 : 0, pl: r.place,
        cap: r.caption, tg: r.tags ? JSON.parse(r.tags) : null,
        b: r.burst, bc: r.cover, sc: r.scene, u: contrib.get(r.h) || [], p: ppl.get(r.h) || [], nf: nf.get(r.h) || 0,
        cam: r.cam, q: r.score, mo: r.moment, pn: r.pinned, la: r.lat, lo: r.lon,
        ...(r.src ? { src: r.src, ai: JSON.parse(r.ai || '{}') } : {}),
      });
    }
    const users = this.sql.exec(`SELECT id, name FROM users`).toArray();
    const persons = this.sql.exec(`SELECT id, name, uid FROM persons`).toArray();
    const scenes = this.sql.exec(`SELECT id, label, n FROM scenes ORDER BY n DESC`).toArray();
    const moments = this.sql.exec(`SELECT * FROM moments ORDER BY start`).toArray();
    const pipe = this.pipeOnline();
    // 能用哪些改图模型 = GPU 端连上来时报的（它那边拿不到网关凭证就是空的）；离线时一个都没有
    const ai = pipe ? JSON.parse(this.kvGet('edit_models', '[]')) : [];
    const body = JSON.stringify({ ver, items, users, persons, scenes, moments, pipe, ai });
    this.listCache = { ver, body };
    return this.listCache;
  }

  stats() {
    const q = s => this.sql.exec(s).one();
    return {
      ver: this.ver,
      items: q(`SELECT COUNT(*) c, COALESCE(SUM(size),0) s FROM media WHERE status='ready' AND deleted=0`),
      uploading: q(`SELECT COUNT(*) c FROM media WHERE status='uploading'`).c,
      analyzed: q(`SELECT COUNT(*) c FROM media WHERE status='ready' AND deleted=0 AND aver>0`).c,
      faces: q(`SELECT COUNT(*) c FROM faces`).c,
      persons: q(`SELECT COUNT(*) c FROM persons`).c,
      qvecs: q(`SELECT COUNT(*) c FROM qvec`).c,
      rcache: this.rcache.size, pipe: this.pipeOnline(),
    };
  }

  /* ---------- 人物：GPU 端把人脸聚成簇，人在页面上点「这是我」认领 ----------
   * 认领后这些脸标为 confirmed，之后新照片里的脸由 GPU 端按「和已确认的脸最像」自动归到这个人；
   * 没认领的簇下次重新聚类可能换 ID，但已确认的归属永远不会被机器改掉。 */
  people() {
    const persons = this.sql.exec(`
      SELECT p.id, p.name, p.uid, COUNT(DISTINCT f.h) n FROM persons p LEFT JOIN faces f ON f.person = p.id
      GROUP BY p.id ORDER BY n DESC`).toArray();
    for (const p of persons) p.faces = this.sampleFaces(`person=?`, p.id, 4);
    const clusters = this.sql.exec(`
      SELECT cluster id, COUNT(DISTINCT h) n FROM faces WHERE person IS NULL AND cluster IS NOT NULL
      GROUP BY cluster HAVING n >= 2 ORDER BY n DESC LIMIT 60`).toArray();
    for (const c of clusters) c.faces = this.sampleFaces(`person IS NULL AND cluster=?`, c.id, 4);
    const loose = this.sql.exec(`SELECT COUNT(*) c FROM faces WHERE person IS NULL`).one().c;
    return { persons, clusters, loose };
  }
  sampleFaces(where, arg, n) {
    return this.sql.exec(`SELECT id, h, x, y, w, hh FROM faces WHERE ${where} ORDER BY score * w DESC LIMIT ${n}`, arg).toArray();
  }
  /** 把一个簇（或单张脸）归给某人：target = {uid} 认领为自己 · {person} 并入已有的人 · {name} 新建一个人 */
  claim({ cluster, face }, target) {
    let pid = target.person;
    if (target.uid) {
      const p = this.sql.exec(`SELECT id FROM persons WHERE uid=?`, target.uid).toArray()[0];
      if (p) pid = p.id;
      else {
        const u = this.user(target.uid);
        this.sql.exec(`INSERT INTO persons (name, uid) VALUES (?,?)`, u.name, u.id);
        pid = this.sql.exec(`SELECT last_insert_rowid() id`).one().id;
      }
    } else if (!pid && target.name) {
      this.sql.exec(`INSERT INTO persons (name) VALUES (?)`, String(target.name).slice(0, 24));
      pid = this.sql.exec(`SELECT last_insert_rowid() id`).one().id;
    }
    if (!pid) throw new Error('no target');
    if (cluster != null) this.sql.exec(`UPDATE faces SET person=?, confirmed=1 WHERE cluster=? AND person IS NULL`, pid, cluster);
    if (face != null) this.sql.exec(`UPDATE faces SET person=?, confirmed=1 WHERE id=?`, pid, face);
    this.bump();
    this.notifyPipe({ t: 'recluster' });
    return { person: pid };
  }
  unassign(face) {
    // 「这张不是他」：标成已确认的「无主」（person=NULL, confirmed=1），机器以后不会再把它自动归回去
    this.sql.exec(`UPDATE faces SET person=NULL, cluster=NULL, confirmed=1 WHERE id=?`, face);
    this.bump();
    return { ok: true };
  }
  renamePerson(pid, name) {
    this.sql.exec(`UPDATE persons SET name=? WHERE id=?`, String(name).slice(0, 24), pid);
    this.bump();
    return { ok: true };
  }

  /* ---------- 相似照片里挑最好的：AI 按分数挑，人可以改；人改过的机器以后不再动 ---------- */
  pick(h) {
    const r = this.sql.exec(`SELECT burst FROM media WHERE h=?`, h).toArray()[0];
    if (!r || !r.burst) return { error: 'not in a group' };
    this.sql.exec(`UPDATE media SET cover=0, pinned=0 WHERE burst=?`, r.burst);
    this.sql.exec(`UPDATE media SET cover=1, pinned=1 WHERE h=?`, h);
    this.bump();
    return { ok: true };
  }

  /* ---------- 打包下载 ---------- */
  zipCreate(ids) {
    const token = crypto.randomUUID();
    this.sql.exec(`DELETE FROM zips WHERE at < ?`, now() - 6 * 3600e3);
    this.sql.exec(`INSERT INTO zips VALUES (?,?,?)`, token, JSON.stringify(ids.slice(0, 500)), now());
    return token;
  }
  zipEntries(token) {
    const z = this.sql.exec(`SELECT ids FROM zips WHERE token=?`, token).toArray()[0];
    if (!z) return null;
    const ids = JSON.parse(z.ids);
    const rows = new Map();
    for (const r of this.sql.exec(`SELECT h, name, size, crc, taken, created FROM media WHERE status='ready' AND h IN (${ids.map(() => '?').join(',')})`, ...ids)) rows.set(r.h, r);
    return ids.filter(h => rows.has(h)).map(h => {
      const r = rows.get(h);
      const t = r.taken || new Date(r.created).toISOString().slice(0, 19);
      return { h, name: `${t.slice(5, 10)}/${r.name}`, size: r.size, crc: r.crc, mtime: t };
    });
  }

  /* ================= 搜索 + 查询缓存 =================
   *
   * 三层缓存，从快到慢：
   *  ① 结果缓存 rcache：key = 版本号|归一化后的查询|有没有向量。版本号在任何写入时 +1，
   *     所以**永远不会返回过期结果**，也不需要手动失效。命中就是一次 Map 查找（<0.1 ms）。
   *  ② 查询向量缓存 qvec（SQLite，永久）：同一个词的语义向量只让 GPU 算一次。
   *     GPU 端还会把相册里出现过的所有标签**预先算好**，所以大部分查询根本不用去问 GPU。
   *  ③ 内存索引 idx：全部照片的标签/描述文本 + int8 量化的图像向量，建一次常驻内存；
   *     5000 张 × 1152 维的相似度 ≈ 600 万次乘加，约 10 ms。
   *
   * 打分 = 关键词（标签完全命中 3 / 部分命中 2 / 描述里出现 1）+ 语义（SigLIP 图文相似度）。
   * 中文没有空格，用「相册自己的词表」做最大正向匹配分词：「瀑布彩虹」→「瀑布」「彩虹」。
   * GPU 端离线时语义那一半跳过，关键词照常工作；没见过的词记进队列，GPU 上线后补算。
   */
  buildIndex() {
    const ver = this.ver;
    const people = new Map(this.sql.exec(`SELECT id, name FROM persons`).toArray().map(p => [p.id, p.name]));
    const users = new Map(this.sql.exec(`SELECT id, name FROM users`).toArray().map(u => [u.id, u.name]));
    const who = new Map();
    for (const r of this.sql.exec(`SELECT DISTINCT h, person FROM faces WHERE person IS NOT NULL`)) {
      if (!who.has(r.h)) who.set(r.h, []); who.get(r.h).push(people.get(r.person));
    }
    for (const r of this.sql.exec(`SELECT h, uid FROM contrib`)) {
      if (!who.has(r.h)) who.set(r.h, []); who.get(r.h).push(users.get(r.uid));
    }
    const docs = [], vocab = new Map();
    const mtitle = new Map(this.sql.exec(`SELECT id, title FROM moments`).toArray().map(m => [m.id, m.title]));
    for (const r of this.sql.exec(`SELECT h, name, caption, tags, place, kind, cam, moment FROM media WHERE status='ready' AND deleted=0`)) {
      const tags = new Set();
      const tg = r.tags ? JSON.parse(r.tags) : {};
      for (const k of ['objects', 'tags', 'scene', 'en', 'alias', 'special']) for (const t of (tg[k] || [])) tags.add(normQ(t));
      if (r.cam) { tags.add(normQ(r.cam)); for (const w of normQ(r.cam).split(' ')) if (w.length >= 3) tags.add(w); }
      if (r.place) for (const p of String(r.place).split(/[·,]/)) tags.add(normQ(p));
      tags.add(r.kind === 'video' ? '视频' : '照片');
      tags.delete('');
      for (const t of tags) vocab.set(t, (vocab.get(t) || 0) + 1);
      const text = normQ([r.caption, r.name, r.place, mtitle.get(r.moment), ...(who.get(r.h) || [])].join(' '));
      docs.push({ h: r.h, tags, text });
    }
    // 图像向量：int8 → 连续的一整块内存，打分时一次顺序扫描
    const pos = new Map(docs.map((d, i) => [d.h, i]));
    let rows = []; const dims = new Map();
    for (const r of this.sql.exec(`SELECT h, scale, vec FROM emb`)) {
      if (!pos.has(r.h)) continue;
      const v = new Int8Array(r.vec instanceof ArrayBuffer ? r.vec : r.vec.buffer || r.vec);
      rows.push([pos.get(r.h), r.scale, v]); dims.set(v.length, (dims.get(v.length) || 0) + 1);
    }
    // 换过图像模型后会短暂混着两种维度 —— 只用多数那一种，少数的等 GPU 端重算
    const D = [...dims.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || 0;
    rows = rows.filter(r => r[2].length === D);
    const E = new Int8Array(docs.length * D), S = new Float32Array(docs.length);
    for (const [i, s, v] of rows) { E.set(v, i * D); S[i] = s; }
    const vocabList = [...vocab.keys()].filter(t => t.length >= 1).sort((a, b) => b.length - a.length);
    this.idx = { ver, docs, vocab, vocabList, E, S, D, a: Number(this.kvGet('siglip_a', 1)), b: Number(this.kvGet('siglip_b', 0)) };
    return this.idx;
  }

  /** 最大正向匹配：用相册词表把没有空格的中文切成词；切不动的字保留成单字段 */
  segment(q, vocabList) {
    const out = [];
    for (const part of q.split(' ')) {
      if (!part) continue;
      if (!CJK.test(part) || part.length <= 2) { out.push(part); continue; }
      let i = 0, buf = '';
      while (i < part.length) {
        let hit = null;
        for (const v of vocabList) if (v.length >= 2 && v.length <= part.length - i && part.startsWith(v, i)) { hit = v; break; }
        if (hit) { if (buf) { out.push(buf); buf = ''; } out.push(hit); i += hit.length; }
        else buf += part[i++];
      }
      if (buf) out.push(buf);
    }
    return [...new Set(out)];
  }

  getQvec(q) {
    if (this.qvecs.has(q)) return this.qvecs.get(q);
    const r = this.sql.exec(`SELECT vec FROM qvec WHERE q=?`, q).toArray()[0];
    if (!r) return null;
    const v = new Float32Array(r.vec instanceof ArrayBuffer ? r.vec : new Uint8Array(r.vec).buffer);
    this.qvecs.set(q, v);
    return v;
  }

  async search(qRaw) {
    const t0 = Date.now();
    const q = normQ(qRaw);
    if (!q) return { q, ids: [], took: 0 };
    let vec = this.getQvec(q);
    if (!vec && this.pipeOnline()) vec = await this.askVec(q, 2500);
    if (!vec) this.sql.exec(`INSERT OR IGNORE INTO qqueue VALUES (?,?)`, q, now());
    const key = `${this.ver}|${q}|${vec ? 1 : 0}`;
    const hit = this.rcache.get(key);
    if (hit) { this.rcache.delete(key); this.rcache.set(key, hit); return { ...hit, cached: true, took: Date.now() - t0 }; }

    const idx = this.idx && this.idx.ver === this.ver ? this.idx : this.buildIndex();
    const terms = this.segment(q, idx.vocabList);
    const n = idx.docs.length;
    const kw = new Float32Array(n);
    idx.docs.forEach((d, i) => {
      let s = 0, matched = 0;
      for (const t of terms) {
        let m = 0;
        if (d.tags.has(t)) m = 3;
        else { for (const g of d.tags) if (g.includes(t) || (t.length >= 2 && t.includes(g) && g.length >= 2)) { m = 2; break; } }
        if (!m && d.text.includes(t)) m = 1;
        if (m) { matched++; s += m; }
      }
      // 全部词都命中的排在只命中一部分的前面
      kw[i] = matched ? (matched / terms.length) * 10 + s : 0;
    });
    const sem = new Float32Array(n);
    let semOn = false;
    if (vec && idx.D && vec.length === idx.D) {
      semOn = true;
      const { E, S, D } = idx;
      for (let i = 0; i < n; i++) {
        if (!S[i]) { sem[i] = -1; continue; }
        let s = 0; const o = i * D;
        for (let j = 0; j < D; j++) s += vec[j] * E[o + j];
        sem[i] = s * S[i];
      }
    }
    // 语义那一半：只取「明显比平均像」的 —— 相对阈值（最高分往下 sem_win 以内）+ 绝对下限。
    // 两个数都由 GPU 端下发（它知道自己用的是哪个模型），默认值是在 SigLIP2 上量出来的
    let top = -1; for (let i = 0; i < n; i++) if (sem[i] > top) top = sem[i];
    const cut = Math.max(top - Number(this.kvGet('sem_win', 0.04)), Number(this.kvGet('sem_floor', 0.05)));
    const scored = [];
    for (let i = 0; i < n; i++) {
      const semHit = semOn && sem[i] >= cut;
      if (!kw[i] && !semHit) continue;
      const sr = semOn && top > 0 ? Math.max(0, sem[i]) / top : 0;   // 0–1
      scored.push([i, kw[i] + sr * 6]);
    }
    scored.sort((x, y) => y[1] - x[1]);
    const res = { q, terms, sem: semOn, ids: scored.slice(0, 400).map(([i]) => idx.docs[i].h) };
    this.rcache.set(key, res);
    if (this.rcache.size > 500) this.rcache.delete(this.rcache.keys().next().value);
    return { ...res, cached: false, took: Date.now() - t0 };
  }

  /** 常用词建议：标签按出现次数排（搜索框下面那排可点的词） */
  suggest() {
    const idx = this.idx && this.idx.ver === this.ver ? this.idx : this.buildIndex();
    return [...idx.vocab.entries()].filter(([t]) => t !== '照片' && t !== '视频')
      .sort((a, b) => b[1] - a[1]).slice(0, 40).map(([t, c]) => ({ t, c }));
  }

  /* ================= GPU 分析端 ================= */
  pipeOnline() { return this.ctx.getWebSockets('pipe').some(ws => ws.readyState === WebSocket.OPEN); }
  notifyPipe(msg) {
    for (const ws of this.ctx.getWebSockets('pipe')) { try { ws.send(JSON.stringify(msg)); } catch { /* 断了就等它重连 */ } }
  }
  askVec(q, ms) {
    return new Promise(resolve => {
      const list = this.waiters.get(q) || [];
      list.push(resolve); this.waiters.set(q, list);
      if (list.length === 1) this.notifyPipe({ t: 'embed', q: [q] });
      setTimeout(() => { const l = this.waiters.get(q); if (l && l.includes(resolve)) { l.splice(l.indexOf(resolve), 1); resolve(null); } }, ms);
    });
  }
  async fetch(request) {
    // 只有 /pipe/ws 会走到这里（外层 Worker 已经验过 PIPE_TOKEN）
    const pair = new WebSocketPair();
    this.ctx.acceptWebSocket(pair[1], ['pipe']);
    this.bump();                  // 列表里带着「GPU 在线」状态，而列表是按版本号缓存的 —— 上下线也得算一次写入
    return new Response(null, { status: 101, webSocket: pair[0] });
  }
  async webSocketMessage(ws, data) {
    let m; try { m = JSON.parse(data); } catch { return; }
    if (m.t === 'vecs') this.putQvecs(m.items);
    if (m.t === 'hello') { this.kvSet('edit_models', JSON.stringify((m.edit || []).filter(k => EDIT_MODELS[k]))); this.bump(); }
  }
  async webSocketClose(ws) { try { ws.close(); } catch { /* 已关闭 */ } this.bump(); }
  async webSocketError() { this.bump(); }

  putQvecs(items) {
    for (const { q, vec } of items || []) {
      const nq = normQ(q); if (!nq) continue;
      const f = new Float32Array(b64dec(vec).buffer);
      this.sql.exec(`INSERT OR REPLACE INTO qvec VALUES (?,?,?)`, nq, f.buffer, now());
      this.sql.exec(`DELETE FROM qqueue WHERE q=?`, nq);
      this.qvecs.set(nq, f);
      const l = this.waiters.get(nq); this.waiters.delete(nq);
      for (const r of l || []) r(f);
    }
    return { ok: true };
  }

  pending(aver, limit = 50) {
    const items = this.sql.exec(`SELECT h, kind, type, name, size, crc, taken, flags FROM media
      WHERE status='ready' AND deleted=0 AND aver < ? ORDER BY created LIMIT ?`, aver, limit).toArray();
    const queries = this.sql.exec(`SELECT q FROM qqueue LIMIT 200`).toArray().map(r => r.q);
    const known = this.sql.exec(`SELECT q FROM qvec`).toArray().map(r => r.q);
    return { items, queries, edits: this.editsPending(), known_queries: known.length, total: this.sql.exec(`SELECT COUNT(*) c FROM media WHERE status='ready' AND deleted=0`).one().c };
  }
  knownQueries() { return this.sql.exec(`SELECT q FROM qvec`).toArray().map(r => r.q); }

  /** 一张照片的分析结果：EXIF/地点/描述/标签/人脸/图像向量。重新分析会整体替换这张的人脸 */
  result(r) {
    const h = r.h;
    if (!this.partInfo(h)) return { error: 'unknown' };
    const set = [], args = [];
    for (const k of ['taken', 'lat', 'lon', 'w', 'hh', 'dur', 'place', 'caption', 'sharp', 'cam', 'score']) if (r[k] !== undefined) { set.push(`${k}=?`); args.push(r[k]); }
    if (r.tags !== undefined) { set.push('tags=?'); args.push(JSON.stringify(r.tags)); }
    if (r.crc !== undefined) { set.push('crc=?'); args.push(r.crc >>> 0); }
    if (r.flags) { set.push('flags = flags | ?'); args.push(r.flags); }
    set.push('aver=?'); args.push(r.aver || 1);
    this.sql.exec(`UPDATE media SET ${set.join(',')} WHERE h=?`, ...args, h);
    this.stamp('res_seq');
    const faceIds = [];
    if (r.faces) {
      // 保留人工确认过的归属：按位置（IoU）把旧脸的 person 过继给新脸
      const old = this.sql.exec(`SELECT x, y, w, hh, person, confirmed FROM faces WHERE h=? AND confirmed=1`, h).toArray();
      this.sql.exec(`DELETE FROM faces WHERE h=?`, h);
      for (const f of r.faces) {
        const o = old.find(o => iou(o, f) > 0.5);
        this.sql.exec(`INSERT INTO faces (h, x, y, w, hh, score, emb, person, confirmed) VALUES (?,?,?,?,?,?,?,?,?)`,
          h, f.x, f.y, f.w, f.hh, f.score, f.emb, o ? o.person : null, o ? 1 : 0);
        faceIds.push(this.sql.exec(`SELECT last_insert_rowid() id`).one().id);
      }
    }
    if (r.emb) this.sql.exec(`INSERT OR REPLACE INTO emb VALUES (?,?,?)`, h, r.emb_scale, b64dec(r.emb).buffer);
    this.bump();
    return { ok: true, faces: faceIds };
  }

  /** 聚类结果整体下发：人脸簇/自动归人、连拍组、场景簇及其名字、SigLIP 标定参数 */
  clusters(c) {
    if (c.faces) for (const [id, cl] of Object.entries(c.faces)) this.sql.exec(`UPDATE faces SET cluster=? WHERE id=?`, cl, Number(id));
    if (c.auto) {
      this.sql.exec(`UPDATE faces SET person=NULL WHERE confirmed=0`);
      for (const [id, p] of Object.entries(c.auto)) this.sql.exec(`UPDATE faces SET person=? WHERE id=? AND confirmed=0`, p, Number(id));
    }
    if (c.bursts) {
      this.sql.exec(`UPDATE media SET burst=NULL, cover=1`);
      for (const [h, [b, cover]] of Object.entries(c.bursts)) this.sql.exec(`UPDATE media SET burst=?, cover=? WHERE h=?`, b, cover ? 1 : 0, h);
      // 人工挑过的那张永远是封面：组被重新划分后，只要它还在某个组里，那个组就听它的
      for (const r of this.sql.exec(`SELECT h, burst FROM media WHERE pinned=1 AND burst IS NOT NULL`).toArray()) {
        this.sql.exec(`UPDATE media SET cover=0 WHERE burst=?`, r.burst);
        this.sql.exec(`UPDATE media SET cover=1 WHERE h=?`, r.h);
      }
    }
    if (c.moments) {
      this.sql.exec(`DELETE FROM moments`);
      this.sql.exec(`UPDATE media SET moment=NULL`);
      for (const m of c.moments.labels) this.sql.exec(`INSERT INTO moments VALUES (?,?,?,?,?,?,?,?)`, m.id, m.title, m.start, m.end, m.place || null, m.n, m.memo ?? null, m.cover || null);
      for (const [h, id] of Object.entries(c.moments.items)) this.sql.exec(`UPDATE media SET moment=? WHERE h=?`, id, h);
    }
    if (c.scenes) {
      this.sql.exec(`DELETE FROM scenes`);
      for (const s of c.scenes.labels) this.sql.exec(`INSERT INTO scenes VALUES (?,?,?)`, s.id, s.label, s.n);
      for (const [h, s] of Object.entries(c.scenes.items)) this.sql.exec(`UPDATE media SET scene=? WHERE h=?`, s, h);
    }
    if (c.siglip) { this.kvSet('siglip_a', c.siglip.a); this.kvSet('siglip_b', c.siglip.b); }
    if (c.sem_floor != null) this.kvSet('sem_floor', c.sem_floor);
    if (c.sem_win != null) this.kvSet('sem_win', c.sem_win);
    this.stamp('cl_seq');
    this.bump();
    return { ok: true };
  }

  /** 真删除（只有 GPU 端令牌能调）：清掉行、人脸、向量，返回要从 R2 删掉的键。
   *  页面上的「撤回」只是隐藏；这个是给测试收尾和「这张必须彻底删掉」用的。 */
  purge({ hs = [], users = [], persons = [], qs = [] } = {}) {
    const keys = [];
    for (const h of hs) {
      if (!/^[0-9a-f]{64}$/.test(h)) continue;
      for (const t of ['media', 'contrib', 'parts', 'faces', 'emb', 'edits']) this.sql.exec(`DELETE FROM ${t} WHERE h=?`, h);
      this.sql.exec(`DELETE FROM edits WHERE out_h=?`, h);
      keys.push('o/' + h, `t/${h}.jpg`, `p/${h}.jpg`, `v/${h}.mp4`);
    }
    for (const n of users) {
      const u = this.sql.exec(`SELECT id FROM users WHERE name=?`, n).toArray()[0];
      if (!u) continue;
      this.sql.exec(`DELETE FROM contrib WHERE uid=?`, u.id);
      this.sql.exec(`DELETE FROM edits WHERE uid=?`, u.id);
      this.sql.exec(`DELETE FROM users WHERE id=?`, u.id);
      for (const p of this.sql.exec(`SELECT id FROM persons WHERE uid=?`, u.id).toArray()) persons.push(p.id);
    }
    for (const pid of persons) {
      this.sql.exec(`UPDATE faces SET person=NULL, confirmed=0 WHERE person=?`, pid);
      this.sql.exec(`DELETE FROM persons WHERE id=?`, pid);
    }
    for (const q of qs) { const nq = normQ(q); this.sql.exec(`DELETE FROM qvec WHERE q=?`, nq); this.sql.exec(`DELETE FROM qqueue WHERE q=?`, nq); this.qvecs.delete(nq); }
    this.bump();
    return { keys };
  }

  /* ================= AI 改图 =================
   * 原图永远不动：改好的图是一张**新照片**（新的内容 ID），记在请求的人名下，带 src 指回原图。
   * 实际的模型调用在 GPU 端（它手里有模型网关的凭证），这边只管排队和记账。 */
  editCreate(uid, { h, prompt, model }) {
    prompt = String(prompt || '').normalize('NFC').trim().slice(0, 400);
    if (!prompt) return { error: '说一下要怎么改' };
    if (!EDIT_MODELS[model]) return { error: '没有这个模型' };
    const m = this.meta(h);
    if (!m || m.status !== 'ready' || m.deleted) return { error: '照片不存在' };
    if (m.kind !== 'image') return { error: '视频不能改' };
    if (!this.pipeOnline()) return { error: 'AI 分析端离线，现在改不了' };
    if (!JSON.parse(this.kvGet('edit_models', '[]')).includes(model)) return { error: '这个模型现在用不了' };
    const busy = this.sql.exec(`SELECT COUNT(*) c FROM edits WHERE uid=? AND status IN ('queued','running')`, uid).one().c;
    if (busy >= EDIT_INFLIGHT) return { error: `你已经有 ${busy} 张在改了，等它们好了再来` };
    const day = this.sql.exec(`SELECT COUNT(*) c FROM edits WHERE uid=? AND at > ?`, uid, now() - 864e5).one().c;
    if (day >= EDIT_PER_DAY) return { error: `今天改了 ${day} 张了，明天再来吧` };
    this.sql.exec(`INSERT INTO edits (h, prompt, model, uid, status, at) VALUES (?,?,?,?, 'queued', ?)`, h, prompt, model, uid, now());
    const id = this.sql.exec(`SELECT last_insert_rowid() id`).one().id;
    this.notifyPipe({ t: 'edit', id });
    return this.editGet(uid, id);
  }
  editGet(uid, id) {
    const e = this.sql.exec(`SELECT id, h, prompt, model, uid, status, out_h, err, at, started, done FROM edits WHERE id=?`, Number(id)).toArray()[0];
    if (!e || (uid && e.uid !== uid)) return null;
    // 排在它前面的（只算还没开始的），给前端显示「前面还有 N 张」
    const ahead = e.status === 'queued' ? this.sql.exec(`SELECT COUNT(*) c FROM edits WHERE status='queued' AND id < ?`, e.id).one().c : 0;
    return { ...e, ahead };
  }
  /** 待处理的：排队中的，加上「开始了 5 分钟还没结果」的（GPU 端半路重启了），最多重试 3 次 */
  editsPending() {
    return this.sql.exec(`SELECT id FROM edits WHERE (status='queued' OR (status='running' AND started < ?)) AND tries < 3 ORDER BY id LIMIT 20`,
      now() - 5 * 60e3).toArray().map(r => r.id);
  }
  editStart(id) {
    const e = this.sql.exec(`SELECT e.id, e.h, e.prompt, e.model, e.status, e.tries, e.started, m.name, m.type, m.taken, m.lat, m.lon FROM edits e JOIN media m ON m.h = e.h WHERE e.id=?`, Number(id)).toArray()[0];
    if (!e || e.tries >= 3 || !(e.status === 'queued' || (e.status === 'running' && e.started < now() - 5 * 60e3))) return { skip: true };
    this.sql.exec(`UPDATE edits SET status='running', started=?, tries=tries+1 WHERE id=?`, now(), e.id);
    return { id: e.id, h: e.h, prompt: e.prompt, model: e.model, name: e.name, type: e.type, taken: e.taken, lat: e.lat, lon: e.lon };
  }
  editFail(id, err) {
    this.sql.exec(`UPDATE edits SET status='error', err=?, done=? WHERE id=?`, String(err || '失败').slice(0, 300), now(), Number(id));
    return { ok: true };
  }
  /** GPU 端把改好的字节放进 R2 之后调这个：登记成一张新照片，时间/地点沿用原图（这样它排在原图旁边） */
  editDone(id, { h, size, crc, type, w, hh, mid }) {
    const e = this.sql.exec(`SELECT * FROM edits WHERE id=?`, Number(id)).toArray()[0];
    if (!e) return { error: 'unknown edit' };
    const s = this.sql.exec(`SELECT * FROM media WHERE h=?`, e.h).toArray()[0];
    if (!s) return { error: 'source gone' };
    const base = String(s.name || 'photo').replace(/\.[^.]+$/, '');
    const ext = type === 'image/png' ? 'png' : 'jpg';
    const n = this.sql.exec(`SELECT COUNT(*) c FROM media WHERE src=?`, e.h).one().c;
    const name = `${base}_AI${n ? n + 1 : ''}.${ext}`;
    const ai = JSON.stringify({ m: e.model, id: String(mid || '').slice(0, 60), p: e.prompt, by: e.uid });
    if (!this.partInfo(h)) {
      this.sql.exec(`INSERT INTO media (h, kind, type, name, size, crc, nparts, psize, status, created, taken, lat, lon, w, hh, place, cam, src, ai)
                     VALUES (?, 'image', ?, ?, ?, ?, 1, ?, 'ready', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        h, type, name, size, crc >>> 0, 8 * 2 ** 20, now(), s.taken, s.lat, s.lon, num(w), num(hh), s.place,
        `AI 编辑 · ${EDIT_MODELS[e.model] || e.model}`, e.h, ai);
    } else this.sql.exec(`UPDATE media SET deleted=0 WHERE h=?`, h);
    this.sql.exec(`INSERT OR IGNORE INTO contrib VALUES (?,?,?)`, h, e.uid, now());
    this.sql.exec(`UPDATE edits SET status='done', out_h=?, err=NULL, done=? WHERE id=?`, h, now(), e.id);
    this.bump();
    this.notifyPipe({ t: 'new', h });
    return { ok: true, h, name };
  }

  /** 给新起的 GPU 端恢复状态用：所有人脸向量 + 归属（pod 重建后不用重新跑人脸） */
  dumpFaces() {
    return this.sql.exec(`SELECT id, h, x, y, w, hh, score, emb, cluster, person, confirmed FROM faces`).toArray();
  }
  media4pipe() {
    return this.sql.exec(`SELECT h, kind, taken, lat, lon, place, sharp, caption, tags, cam, score, pinned, created, src FROM media WHERE status='ready' AND deleted=0`).toArray();
  }
  embs() {
    return this.sql.exec(`SELECT h, scale, vec FROM emb`).toArray().map(r => ({ h: r.h, scale: r.scale, vec: btoa(String.fromCharCode(...new Uint8Array(r.vec))) }));
  }
}

function num(x) { const n = Number(x); return Number.isFinite(n) ? n : null; }
function iou(a, b) {
  const x1 = Math.max(a.x, b.x), y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.w, b.x + b.w), y2 = Math.min(a.y + a.hh, b.y + b.hh);
  const i = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  return i / (a.w * a.hh + b.w * b.hh - i || 1);
}
