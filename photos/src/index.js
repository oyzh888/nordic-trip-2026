/**
 * nordic-photos —— 北欧 2026 共享相册（挂在 nordic.airacle.com/photos/ 下）
 *
 * 这个文件只是「宿主」：网页前端（public/photos/，静态文件）+ 把 /photos/api/*、/photos/f/* 交给相册引擎（engine.js）。
 * 引擎不关心页面长什么样 —— 换一套前端 / 再挂一个前端，只改这里（分层和接口契约见 ENGINE.md）。
 *
 * 为什么放在 Cloudflare 而不是在 GPU 机上起一个 Immich：
 * GPU 机是 pod，随时可能被重建（hostname 今年漂了 4 次）。照片是**旅途中唯一不可再生的东西**，
 * 必须存在一个不会跟着机器消失的地方。R2 + Worker 没有服务器要维护，也不会因为 pod 重建而打不开。
 */
import { Album } from './album.js';
import { handle } from './engine.js';

export { Album };

const BASE = '/photos';

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const p = url.pathname;
    // 跑在本机时（ORIGIN_KEY 有值）：经 Cloudflare 进来的请求（带 cf-ray）必须是主站 Worker 转发的、带着共享密钥，
    // 不许绕过主站直接打 tunnel 域名（否则可以伪造 x-real-ip 躲开登录失败限流）。本机直连（GPU 端）不受影响
    if (env.ORIGIN_KEY && req.headers.get('cf-ray') && !safeEq(req.headers.get('x-origin-key') || '', env.ORIGIN_KEY))
      return new Response('forbidden', { status: 403 });
    // 相对地址：经主站转发时 url.origin 是 tunnel 域名，绝对地址会把浏览器带过去
    if (p === BASE) return new Response(null, { status: 301, headers: { location: BASE + '/' + url.search } });
    if (p.startsWith(BASE + '/api/') || p.startsWith(BASE + '/f/')) return handle(req, env, ctx, { base: BASE });
    return env.ASSETS.fetch(req);                     // 网页前端
  },
};

function safeEq(a, b) {
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
