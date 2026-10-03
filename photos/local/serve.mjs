// 本机正式跑相册 Worker：直接用 Miniflare（wrangler dev 底下的那个库），不经过 wrangler dev。
// 为什么不用 wrangler dev：它会挂调试器（inspector），把 Worker 发出的每个请求连同响应体抄一份给 Node 主进程 ——
// 照片字节从 blobd 取回来时全被抄一遍，下载慢、Node 内存随下载量涨，大文件能把整个 workerd 拖死（2026-10-03 实测）。
//   用法：node serve.mjs   （配置全走环境变量，run_local.sh 会设好）
import { Miniflare } from '/mnt/localssd/colligo_home/.local/lib/node_modules/wrangler/node_modules/miniflare/dist/src/index.js';
import fs from 'node:fs';
import path from 'node:path';

const APP = process.env.APP_DIR, STATE = process.env.STATE_DIR, PORT = Number(process.env.PORT);
const vars = Object.fromEntries(fs.readFileSync(path.join(APP, '.dev.vars'), 'utf8').split('\n')
  .filter(l => /^[A-Z_]+=/.test(l)).map(l => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1)]));

const mf = new Miniflare({
  name: 'nordic-photos',            // DO 的存储目录名（nordic-photos-Album）由它决定，必须和 wrangler 一致
  host: '127.0.0.1', port: PORT,
  modules: true, scriptPath: path.join(APP, 'src/index.js'), modulesRoot: APP,
  modulesRules: [{ type: 'ESModule', include: ['**/*.js'] }],
  compatibilityDate: '2026-01-01',
  bindings: vars,
  durableObjects: { ALBUM: { className: 'Album', useSQLite: true } },
  r2Buckets: { BUCKET: 'nordic-photos' },
  assets: { directory: path.join(APP, 'public'), binding: 'ASSETS', assetConfig: { html_handling: 'auto-trailing-slash' }, routerConfig: { has_user_worker: true } },
  defaultPersistRoot: path.join(STATE, 'v3'),   // 和 wrangler dev --persist-to 同一个布局：DO 的 SQLite 原样沿用
});
await mf.ready;
console.log(`[serve] miniflare 已就绪 · 127.0.0.1:${PORT} · state ${STATE}`);
for (const s of ['SIGINT', 'SIGTERM']) process.on(s, async () => { await mf.dispose(); process.exit(0); });
