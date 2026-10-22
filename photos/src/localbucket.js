/**
 * 本机部署时代替 R2：同样的调用方式（put / get / delete / createMultipartUpload / resumeMultipartUpload），
 * 底下是 blobd（photos/local/blobd.mjs）—— 一个直接读写本地磁盘、多进程的小程序。
 * 字节只在原生的流里走（请求体直接转给 blobd），不在 JS 里拷贝；哈希也在 blobd 里算，结果随返回值带回来（sha256）。
 * 只实现了相册用到的那一小撮 R2 接口。
 */
export function localBucket(base, token) {
  const H = extra => ({ 'x-blobd-token': token || '', ...extra });
  const enc = k => k.split('/').map(encodeURIComponent).join('/');
  const ok = async (r, what) => {
    if (r.ok) return r;
    const t = await r.text().catch(() => '');
    throw new Error(`blobd ${what} ${r.status} ${t.slice(0, 120)}`);
  };
  // fetch 的 body 只认这几种；Uint8Array 的子视图要按它自己的范围传
  const bodyOf = b => (b == null ? null : b);

  const obj = (key, r, withBody) => {
    const size = Number(r.headers.get('x-size') || r.headers.get('content-length') || 0);
    const cr = /bytes (\d+)-(\d+)\/(\d+)/.exec(r.headers.get('content-range') || '');
    const o = {
      key, size, etag: (r.headers.get('etag') || '').replace(/"/g, ''), httpEtag: r.headers.get('etag') || '',
      writeHttpMetadata(h) { h.set('content-type', /^v\/|\.mp4$/.test(key) ? 'video/mp4' : /^[tpf]\//.test(key) ? 'image/jpeg' : 'application/octet-stream'); },
      range: cr ? { offset: Number(cr[1]), length: Number(cr[2]) - Number(cr[1]) + 1 } : undefined,
    };
    if (withBody) { o.body = r.body; o.arrayBuffer = () => r.arrayBuffer(); }
    return o;
  };

  return {
    async put(key, body) {
      const r = await ok(await fetch(`${base}/o/${enc(key)}`, { method: 'PUT', headers: H(), body: bodyOf(body) }), 'put');
      const j = await r.json();
      return { key, size: j.size, etag: j.sha256, sha256: j.sha256 };
    },
    /** opts.range / opts.onlyIf 传进来的是请求头（serveObject 的用法），原样转给 blobd */
    async get(key, opts = {}) {
      const h = H();
      const src = opts.range instanceof Headers ? opts.range : null;
      if (src && src.get('range')) h.range = src.get('range');
      const cond = opts.onlyIf instanceof Headers ? opts.onlyIf : null;
      if (cond && cond.get('if-none-match')) h['if-none-match'] = cond.get('if-none-match');
      const r = await fetch(`${base}/o/${enc(key)}`, { headers: h });
      if (r.status === 404) return null;
      if (r.status === 304) return obj(key, r, false);
      await ok(r, 'get');
      return obj(key, r, true);
    },
    async head(key) {
      const r = await fetch(`${base}/o/${enc(key)}`, { method: 'HEAD', headers: H() });
      return r.status === 404 ? null : obj(key, await ok(r, 'head'), false);
    },
    async delete(keys) {
      keys = Array.isArray(keys) ? keys : [keys];
      await ok(await fetch(`${base}/delete`, { method: 'POST', headers: H({ 'content-type': 'application/json' }), body: JSON.stringify({ keys }) }), 'delete');
    },
    async createMultipartUpload(key) {
      const r = await ok(await fetch(`${base}/mp/${enc(key)}`, { method: 'POST', headers: H() }), 'mp');
      return mpu(key, (await r.json()).uploadId);
    },
    resumeMultipartUpload(key, uploadId) { return mpu(key, uploadId); },
  };

  function mpu(key, uploadId) {
    const u = `${base}/mp/${enc(key)}/${uploadId}`;
    return {
      key, uploadId,
      async uploadPart(n, body) {
        const r = await fetch(`${u}/${n}`, { method: 'PUT', headers: H(), body: bodyOf(body) });
        if (r.status === 404) throw new Error('multipart upload does not exist (10024)');
        const j = await (await ok(r, 'part')).json();
        return { partNumber: n, etag: j.etag, sha256: j.sha256, size: j.size };
      },
      async complete(parts) {
        const r = await fetch(`${u}/complete`, { method: 'POST', headers: H({ 'content-type': 'application/json' }), body: JSON.stringify({ parts }) });
        if (r.status === 409) throw new Error('part could not be found (10025)');
        if (r.status === 404) throw new Error('multipart upload does not exist (10024)');
        await ok(r, 'complete');
        return { key };
      },
      async abort() { await fetch(u, { method: 'DELETE', headers: H() }); },
    };
  }
}

/**
 * 分层存储（热 R2 + 冷 NAS）：同一份对象「在哪就从哪读」，上层代码（engine / album）不用知道。
 *   · 写：永远写热（R2）—— 上传又快又稳，不依赖家里的网
 *   · 读：先热后冷。只有冷前缀（默认 o = 原件、g = 视频 H.264 新版）在热里没有时才去问冷；缩略图 / 预览 / 720p 视频永远在热里，
 *     所以翻相册一次也不碰 NAS，只有「看原图 / 下载 / 打包」才会
 *   · 删：两边都删
 * 搬运工（NAS 上的 cold_mover.py）把原件拷到冷、核对无误后，由引擎删掉热里那份 —— 搬了一半的、没搬的、搬完的，读起来都一样。
 * 冷存储连不上时：读冷前缀返回 503（不是 500、也不卡住），上传 / 翻相册 / 缩略图 / 预览照常。
 */
export function tieredBucket(hot, cold, prefixes = ['o', 'g'], coldFirst = false) {
  const isCold = key => prefixes.includes(String(key).split('/', 1)[0]);
  const down = e => Object.assign(new Error('冷存储暂时连不上（原件和视频新版暂时取不到，缩略图 / 预览不受影响）：' + String(e && e.message || e).slice(0, 100)), { status: 503 });
  return {
    hot, cold, isCold,
    async get(key, opts) {
      if (coldFirst && isCold(key)) {
        // NAS 优先（COLD_FIRST）：先问 NAS，NAS 没有（还没搬 / 新传的）或连不上就用 R2 里的；两边都没有才 404 / 503。
        // 回包的 store 字段 = 'nas'，serveObject 会写进 x-store 响应头，方便确认读的是哪边
        let err;
        try { const c = await cold.get(key, opts); if (c) { c.store = 'nas'; return c; } }
        catch (e) { err = e; console.error('[cold] NAS 读失败，退回 R2：', key, String(e && e.message || e).slice(0, 100)); }
        const r = await hot.get(key, opts);
        if (r) { if (err) try { r.store = 'r2-fallback'; } catch {} return r; }
        if (err) throw down(err);
        return null;
      }
      const r = await hot.get(key, opts);
      if (r || !isCold(key)) return r;
      try { return await cold.get(key, opts); } catch (e) { throw down(e); }
    },
    async head(key) {
      const r = await hot.head(key);
      if (r || !isCold(key)) return r;
      try { return await cold.head(key); } catch (e) { throw down(e); }
    },
    put: (...a) => hot.put(...a),
    createMultipartUpload: (...a) => hot.createMultipartUpload(...a),
    resumeMultipartUpload: (...a) => hot.resumeMultipartUpload(...a),
    async delete(keys) {
      keys = [].concat(keys);
      await hot.delete(keys);
      const c = keys.filter(isCold);
      if (c.length) await cold.delete(c).catch(e => console.error('[cold] delete 失败（冷存储里可能留着孤儿文件，之后 cold_mover.py gc 会清）', String(e).slice(0, 120)));
    },
  };
}

/** 换存储：BLOBD（整个本机部署，全部走 blobd）或 COLD_URL（热 R2 + 冷 NAS 分层）；都没配就原样用 R2。其余绑定原样不动 */
const stores = new WeakMap();
export function withStore(env) {
  if (!env.BLOBD && !env.COLD_URL) return env;
  let w = stores.get(env);
  if (!w) {
    const bucket = env.BLOBD ? localBucket(env.BLOBD, env.BLOBD_TOKEN)
      : tieredBucket(env.BUCKET, localBucket(env.COLD_URL.replace(/\/+$/, ''), env.COLD_TOKEN),
        String(env.COLD_PREFIXES || 'o,g').split(',').map(x => x.trim()).filter(Boolean), env.COLD_FIRST === '1');
    w = Object.create(env, { BUCKET: { value: bucket } });
    stores.set(env, w);
  }
  return w;
}
