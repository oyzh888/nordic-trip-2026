/* 四个风格版本共用的行为层：只管「怎么动」，不管「长什么样」。
 * 每个版本自己写 CSS 和 DOM 结构，然后调 NT.init({...}) 把这些行为挂上去。
 *
 * 里面已经处理掉的几件事（每个版本都会用到，不要各写一遍）：
 *  · prefers-reduced-motion → 入场动画/视差全部关掉，内容直接可见（不是留白）
 *  · 图片容器带 aspect-ratio → 懒加载不跳版（CLS）
 *  · 图片可 Tab 聚焦、Enter 开大图、Esc 关闭并把焦点还回去
 *  · Commons 署名（CC-BY 系列的许可条件，不是客套）
 */
const NT = (() => {
  const $  = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const el = (t, c, h) => { const n = document.createElement(t);
    if (c) n.className = c; if (h != null) n.innerHTML = h; return n; };
  const esc = s => (s || '').replace(/[&<>"]/g,
    c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;' }[c]));
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const stripExt = s => (s || '').replace(/\.(jpe?g|png|JPG|JPEG|webp)$/i, '');
  const altOf = i => `${i.slug} — ${stripExt(i.title)}`;
  const credit = i => `${stripExt(i.title)} · ${i.author || '未署名'} · ${i.license || '见文件页'}`;

  /* ---------- 图片：宽高比给容器，图填满 ---------- */
  function figure(i, opts) {
    const o = opts || {};
    const f = el('figure', o.cls || '');
    f.style.aspectRatio = o.ar || (i.w && i.h ? `${i.w} / ${i.h}` : '3 / 2');
    const im = el('img');
    im.src = i.src; im.alt = o.alt || altOf(i);
    im.loading = o.eager ? 'eager' : 'lazy';
    im.decoding = 'async';
    if (o.eager) im.fetchPriority = 'high';
    f.appendChild(im);
    if (o.caption !== false) f.appendChild(el('figcaption', null, esc(credit(i))));
    f.tabIndex = 0;
    f.dataset.zoom = '1';
    const open = () => lightbox(i);
    f.addEventListener('click', open);
    f.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    return f;
  }

  /* 住宿实拍：只有 URL，没有署名信息 */
  function shotFig(url, name, k, ar) {
    const f = el('figure');
    f.style.aspectRatio = ar || '3 / 2';
    const im = el('img');
    im.src = url; im.alt = `${name} 实拍 ${k + 1}`; im.loading = 'lazy'; im.decoding = 'async';
    f.appendChild(im);
    f.tabIndex = 0; f.dataset.zoom = '1';
    const i = { src: url, title: name, author: '房源实拍', license: 'Airbnb / Booking.com' };
    f.addEventListener('click', () => lightbox(i));
    f.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); lightbox(i); } });
    return f;
  }

  /* ---------- Lightbox ---------- */
  let lb = null, lastFocus = null;
  function ensureLb() {
    if (lb) return lb;
    lb = el('div', 'nt-lb');
    lb.setAttribute('role', 'dialog');
    lb.setAttribute('aria-modal', 'true');
    lb.setAttribute('aria-label', '放大查看图片');
    lb.innerHTML =
      `<button class="nt-lb-x" aria-label="关闭">
         <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor"
              stroke-width="1.5"><path d="M1 1l16 16M17 1L1 17" stroke-linecap="round"/></svg>
       </button><img alt=""><div class="nt-lb-cap"></div>`;
    document.body.appendChild(lb);
    $('.nt-lb-x', lb).addEventListener('click', closeLb);
    lb.addEventListener('click', e => { if (e.target === lb) closeLb(); });
    addEventListener('keydown', e => {
      if (e.key === 'Escape' && lb.classList.contains('on')) closeLb(); });
    return lb;
  }
  function lightbox(i) {
    ensureLb(); lastFocus = document.activeElement;
    $('img', lb).src = i.src; $('img', lb).alt = stripExt(i.title);
    $('.nt-lb-cap', lb).innerHTML = esc(credit(i)) +
      (i.page ? ` · <a href="${esc(i.page)}" target="_blank" rel="noopener">文件页 ↗</a>` : '');
    lb.classList.add('on');
    document.body.style.overflow = 'hidden';
    $('.nt-lb-x', lb).focus();
  }
  function closeLb() {
    lb.classList.remove('on'); document.body.style.overflow = '';
    $('img', lb).src = ''; if (lastFocus) lastFocus.focus();
  }

  /* ---------- 入场揭示：reduced-motion 下直接全显示 ---------- */
  function reveal(sel, cls) {
    const nodes = $$(sel);
    if (RM) { nodes.forEach(n => n.classList.add(cls || 'in')); return; }
    const io = new IntersectionObserver(es => {
      es.forEach((e, k) => {
        if (!e.isIntersecting) return;
        setTimeout(() => e.target.classList.add(cls || 'in'), k * 45);  // 40–50ms 递进
        io.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: .1 });
    nodes.forEach(n => io.observe(n));
  }

  /* ---------- 滚动：进度 / 导航显隐 / 当前幕 / 轻微视差 ---------- */
  function scroll(o) {
    const doc = document.documentElement;
    const bars = o.progress ? $$(o.progress) : [];
    const nav = o.nav ? $(o.nav) : null;
    const par = (!RM && o.parallax) ? $$(o.parallax) : [];
    let raf = 0;
    const tick = () => {
      raf = 0;
      const pct = doc.scrollTop / (doc.scrollHeight - doc.clientHeight || 1) * 100;
      bars.forEach(b => {
        if (o.vertical) b.style.height = pct + '%'; else b.style.width = pct + '%';
        b.setAttribute('aria-valuenow', Math.round(pct));
      });
      if (nav) nav.classList.toggle('on', doc.scrollTop > innerHeight * (o.navAfter || .65));
      par.forEach(p => {
        const r = p.getBoundingClientRect();
        if (r.bottom < 0 || r.top > innerHeight) return;
        const k = (r.top / innerHeight) * (o.parallaxAmt || 60);
        p.style.transform = `translate3d(0,${-k}px,0)`;
      });
    };
    addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(tick); },
      { passive: true });
    addEventListener('resize', tick, { passive: true });
    tick();
    if (o.actSel && o.navLinks) {
      const io = new IntersectionObserver(es => es.forEach(e => {
        if (!e.isIntersecting) return;
        $$(o.navLinks).forEach(a =>
          a.classList.toggle('cur', a.getAttribute('href') === '#' + e.target.id));
      }), { threshold: .35 });
      $$(o.actSel).forEach(s => io.observe(s));
    }
  }

  /* ---------- 署名表 ---------- */
  function credits(sel, wrapTag) {
    const n = $(sel); if (!n) return;
    n.innerHTML = CREDITS.map(i =>
      `<${wrapTag || 'div'}><a href="${esc(i.page)}" target="_blank" rel="noopener"
        >${esc(stripExt(i.title))}</a> — ${esc(i.author || '未署名')} ·
        ${esc(i.license || '见文件页')}</${wrapTag || 'div'}>`).join('');
  }

  function daysOf(actId) { return DAYS.filter(d => d.act === actId); }

  return { $, $$, el, esc, RM, altOf, credit, stripExt, figure, shotFig,
           lightbox, reveal, scroll, credits, daysOf };
})();

/* Lightbox 的样式各版本共用（只有配色跟随该版本的变量） */
(() => {
  const css = `
  .nt-lb{position:fixed;inset:0;z-index:1000;display:none;align-items:center;
    justify-content:center;padding:clamp(14px,4vw,56px);
    background:var(--lb-bg,rgba(0,0,0,.96))}
  .nt-lb.on{display:flex}
  .nt-lb img{max-width:100%;max-height:84vh;object-fit:contain}
  .nt-lb-cap{position:absolute;left:0;right:0;bottom:0;padding:20px clamp(14px,4vw,56px);
    text-align:center;font:400 11px/1.7 var(--lb-mono,ui-monospace,monospace);
    color:var(--lb-dim,#8a8a90)}
  .nt-lb-cap a{color:var(--lb-fg,#e8e8e8)}
  .nt-lb-x{position:absolute;top:clamp(12px,3vw,28px);right:clamp(12px,3vw,28px);
    width:48px;height:48px;display:grid;place-items:center;background:none;cursor:pointer;
    border:1px solid var(--lb-line,#333);border-radius:999px;color:var(--lb-fg,#e8e8e8)}
  .nt-lb-x:hover{background:rgba(255,255,255,.08)}
  [data-zoom]{cursor:zoom-in}
  figure{margin:0;position:relative;overflow:hidden}
  figure img{display:block;width:100%;height:100%;object-fit:cover}`;
  const s = document.createElement('style'); s.textContent = css;
  document.head.appendChild(s);
})();
