/* site/anim.js —— 动效的行为层（样式在 style.css 末尾那一节）
 *
 * 三条自律：
 *   1. **降级要安全**：所有效果都是"锦上添花"。JS 挂了、IntersectionObserver 不存在、
 *      或者用户开了「减少动态效果」——页面必须仍然完整可读（所以 .rv 只在确认能观察时才加）。
 *   2. **不碰布局**：只改 opacity / transform，不改 width/height/margin，避免重排和横向溢出。
 *   3. **一次性**：元素露出后就取消观察，不做来回抽动 —— 反复动的页面显得廉价。
 */
(() => {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* 极光 + 颗粒：两层纯装饰的 fixed 元素，用 JS 插入而不是写死在每个 HTML 里 */
  if (!reduce) {
    document.body.insertAdjacentHTML('afterbegin',
      '<div class="aurora" aria-hidden="true"><i></i><i></i><i></i></div><div class="grain" aria-hidden="true"></div>');
  }

  if (reduce || !('IntersectionObserver' in window)) return;

  /* 滚动揭示。
   * 两处按实测改过（2026-09-07）：
   *   · **不再给 section 加 .rv** —— 整个 section 的 opacity 归零风险太大：它一旦没被触发，
   *     里面所有内容跟着看不见。只给「块级内容」加，最坏情况也只是某一块没淡入。
   *   · threshold 从 0.06 降到 0：只要露出一个像素就算进场。0.06 对比视口更高的元素
   *     几乎不可能满足，实测有 7 个元素因此永远停在 opacity:0。
   */
  const targets = [];
  document.querySelectorAll('.day, .card, .carcard, .tw, .gantt, .stats > div, section > .wrap > h2, section > .wrap > .lede')
    .forEach(el => { el.classList.add('rv'); targets.push(el); });

  const reveal = (el, i) => {
    el.style.transitionDelay = Math.min(i, 6) * 70 + 'ms';
    el.classList.add('in');
    if (el.parentElement?.classList.contains('stats')) countUp(el);
  };

  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      const el = e.target;
      const sibs = [...(el.parentElement?.children || [])].filter(x => x.classList.contains('rv'));
      reveal(el, Math.max(0, sibs.indexOf(el)));
      io.unobserve(el);
    });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0 });
  targets.forEach(t => io.observe(t));

  /* 🔴 安全网：2.5 秒后把还没进场的一律显示出来。
   * 这条是「降级要安全」的真正实现 —— 任何原因（IO 没派发、元素比视口高、
   * 浏览器差异、打印）都不允许让内容永久停在 opacity:0。内容可读 > 动效好看。 */
  setTimeout(() => targets.forEach((el, i) => {
    if (!el.classList.contains('in')) { el.style.transitionDelay = '0ms'; el.classList.add('in'); }
  }), 2500);

  /* 环境光跟着段落走：视口中心落在哪个 section，就把 :root --glow 换成它的 --acc。
   * 这是"往下走换成另一种颜色的渐变"那句话的实现 —— 光晕在 2.4 秒里化过去（CSS transition），
   * 所以你看不到切换那一下，只觉得整页的色温在慢慢变。 */
  {
    const zones = [...document.querySelectorAll('section[data-hue], .hero[data-hue]')];
    let cur = null;
    const pick = () => {
      const mid = innerHeight * 0.42;
      let best = null, bestD = 1e9;
      for (const z of zones) {
        const r = z.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight) continue;
        const d = Math.abs((r.top + r.bottom) / 2 - mid);
        if (d < bestD) { bestD = d; best = z; }
      }
      if (!best) return;
      const c = getComputedStyle(best).getPropertyValue('--acc').trim();
      if (c && c !== cur) { cur = c; document.documentElement.style.setProperty('--glow', c); }
    };
    let tick = false;
    addEventListener('scroll', () => {
      if (tick) return; tick = true;
      requestAnimationFrame(() => { pick(); tick = false; });
    }, { passive: true });
    pick();
  }

  /* 数字滚动：只动数字部分，货币符号/单位原样保留（$2,409.83 → 前缀 $ 不动） */
  function countUp(scope) {
    scope.querySelectorAll('.v').forEach(v => {
      if (v.dataset.done) return;
      const raw = v.textContent.trim();
      const m = raw.match(/^([^\d]*)([\d,]+(?:\.\d+)?)(.*)$/);
      if (!m) return;
      const [, pre, numStr, post] = m;
      const target = parseFloat(numStr.replace(/,/g, ''));
      if (!isFinite(target) || target === 0) return;
      const dec = (numStr.split('.')[1] || '').length;
      const grouped = numStr.includes(',');
      v.dataset.done = '1';
      const t0 = performance.now(), dur = 1100;
      const fmt = n => (grouped ? n.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
                                : n.toFixed(dec));
      (function step(now) {
        const p = Math.min(1, (now - t0) / dur);
        const e = 1 - Math.pow(1 - p, 3);              /* ease-out cubic */
        v.textContent = pre + fmt(target * e) + post;
        if (p < 1) requestAnimationFrame(step);
        else v.textContent = raw;                       /* 收尾用原始串，避免格式漂移 */
      })(t0);
    });
  }
})();
