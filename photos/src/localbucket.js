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

/** 本机部署（配了 BLOBD）时把 BUCKET 换成直接读写磁盘的 blobd；其余绑定原样不动 */
let storeEnv = null;
export function withStore(env) {
  if (!env.BLOBD) return env;
  if (!storeEnv || storeEnv.base !== env) storeEnv = { base: env, env: Object.create(env, { BUCKET: { value: localBucket(env.BLOBD, env.BLOBD_TOKEN) } }) };
  return storeEnv.env;
}

