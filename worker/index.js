/**
 * nordic.airacle.com —— 静态站 + 一个极小的打包清单同步 API
 *
 * 为什么需要后端：Steve 要在**手机和电脑上都能勾**打包清单。
 * localStorage / cookie 是**按设备**存的 —— 手机上勾的电脑看不到，
 * 所以「自动存 cookie」解决不了跨设备，必须有一个共同的存储点。
 * 这里用 Workers KV（已建命名空间 PACK），整站本来就是 Worker，零额外部署。
 *
 * 冲突怎么处理（两台设备同时开着的情况）：
 * **不整份覆盖**，而是按条目做 last-write-wins —— 每条存 {c:是否勾选, t:毫秒时间戳}，
 * 合并时同一条取 t 更大的那个。所以「手机勾了 A、电脑同时勾了 B」两条都会留下，
 * 而不是后写的那台把前一台的进度抹掉。这是这个 API 唯一一处需要想清楚的逻辑。
 *
 * ⚠️ KV 是最终一致的（跨 colo 最多约 60 秒）→ 另一台设备上看到更新可能有几秒到一分钟延迟。
 * 因为合并是按条目 LWW 的，延迟只会让人「晚点看到」，不会「丢掉进度」。
 *
 * ⚠️ 没有鉴权：这个站是公开的，任何嵌在页面里的密钥同样是公开的，加了等于没加。
 * 存的内容是打包清单的勾选状态（无个人信息、无证件号、无预订号），最坏情况是有人来
 * 把勾清掉 —— 所以页面**同时把状态写在本机 localStorage**，云端被清也能从本机恢复。
 */

const KEY = 'pack:v1';

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',       // 进度不能被 CDN 缓存，否则会看到旧勾选
    },
  });

/** 按条目取时间戳更大的那个。items 形如 { 'b1-passport': {c:true, t:1758...} } */
function merge(a = {}, b = {}) {
  const out = { ...a };
  for (const [id, v] of Object.entries(b)) {
    if (!v || typeof v.t !== 'number') continue;         // 脏数据直接丢，不要让它污染存储
    if (!out[id] || v.t > out[id].t) out[id] = { c: !!v.c, t: v.t };
  }
  return out;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 共享相册（photos/ 下的独立 worker，见 wrangler.jsonc 的 services）
    if (url.pathname === '/photos' || url.pathname.startsWith('/photos/')) return env.PHOTOS.fetch(request);

    if (url.pathname === '/api/pack') {
      const stored = (await env.PACK.get(KEY, 'json')) || {};

      if (request.method === 'GET') return json({ items: stored });

      if (request.method === 'POST') {
        let body;
        try { body = await request.json(); } catch { return json({ error: 'bad json' }, 400); }
        const merged = merge(stored, body && body.items);
        // 上限防呆：清单只有几十条，多出来的必然是 bug 或有人乱写
        if (Object.keys(merged).length > 500) return json({ error: 'too many items' }, 413);
        await env.PACK.put(KEY, JSON.stringify(merged));
        return json({ items: merged });
      }

      return json({ error: 'method not allowed' }, 405);
    }

    // 其余全部交给静态资源（目录直出、404 页都由 assets 处理）
    return env.ASSETS.fetch(request);
  },
};
