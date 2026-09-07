/* site/app.js —— 四个页面共用的渲染层
 *
 * 放在一起的理由：导航、甘特图、体检、日卡这几样在多个页面出现，
 * 之前 story/ styles/ viz/ 各写一份，改一次要改三处（README 里记着这个教训）。
 * 这里只暴露几个纯函数，页面自己决定往哪个容器里塞。
 */

/* ---------- 小工具 ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
/* data.js 里的文案有的是 **粗体** 有的已经是 <b> —— 两种都要能显示 */
const md = s => String(s ?? '')
  .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
  .replace(/`(.+?)`/g, '<code class="mono">$1</code>');
const hm = d => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
const md_ = d => `${d.getMonth() + 1}/${d.getDate()}`;

/* ---------- 导航（每页一样，当前页高亮） ---------- */
const PAGES = [
  ['/', '首页'], ['/days/', '逐日'], ['/plan/', '最终方案'], ['/cars/', '四台车'],
];
function nav() {
  const here = location.pathname.replace(/index\.html$/, '') || '/';
  return `<div class="nav"><div class="in">
    <a class="brand" href="/">北欧 2026<em>Nordic</em></a>
    <nav>${PAGES.map(([h, t]) =>
      `<a href="${h}"${h === here ? ' aria-current="page"' : ''}>${t}</a>`).join('')}
      <a href="https://github.com/oyzh888/nordic-trip-2026" target="_blank" rel="noopener">GitHub ↗</a>
    </nav></div></div>`;
}
function foot() {
  return `<footer><div class="wrap">
    <div>北欧 2026 · 4 人 · 9/24 → 10/6 · 13 天<br>
      <span class="s">价格与时刻均为 2026-09-01 → 09-06 用 Playwright 打开真实页面按真实日期抓取，非估算。</span></div>
    <div class="s">风光与车辆照片来自 Wikimedia Commons（CC BY / CC BY-SA），署名见图注<br>
      住宿照片来自 Airbnb / Booking 房源页 · 汇率固定 €1=¥8.0 · $1=¥7.1 · NOK1=¥0.67</div>
  </div></footer>`;
}
function chrome() {
  document.body.insertAdjacentHTML('afterbegin', nav());
  document.body.insertAdjacentHTML('beforeend', foot());
}

/* ---------- 甘特图 ----------
 * 每天一行、行内四条轨（住/车/飞/活动），一个事件按它在这一天里占的
 * 时间比例定位；跨天的事件会在每一天各画一段，两端用 ‹ › 标出还没结束。
 */
function gantt(el) {
  const LANES = ['stay', 'car', 'fly', 'act'];
  const EVS = EV.map(e => ({ ...e, S: new Date(e.s), E: new Date(e.e) }));
  const d0 = new Date(DAY0 + 'T00:00');
  let h = `<div class="gantt"><div class="ruler"><div class="dlab s">日期</div>
    <div class="h">${[0, 3, 6, 9, 12, 15, 18, 21].map(x => `<span>${x}:00</span>`).join('')}</div></div>`;

  for (let i = 0; i < DAYN; i++) {
    const ds = new Date(d0.getTime() + i * 864e5), de = new Date(ds.getTime() + 864e5);
    h += `<div class="drow"><div class="dlab"><b>${md_(ds)}</b>
      <span>${'日一二三四五六'[ds.getDay()]}</span></div><div class="tracks">`;
    for (const ln of LANES) {
      h += `<div class="tk">`;
      for (const e of EVS.filter(x => x.lane === ln && x.E > ds && x.S < de)) {
        const a = Math.max(e.S, ds), b = Math.min(e.E, de);
        const L = (a - ds) / 864e5 * 100, W = Math.max((b - a) / 864e5 * 100, 1.6);
        const cont = (e.S < ds ? '‹ ' : '') + (e.E > de ? ' ›' : '');
        h += `<div class="bar ${ln} ${e.st}" style="left:${L}%;width:${W}%"
                title="${esc(e.t.replace(/<[^>]+>/g, ''))}\n${hm(e.S)} → ${hm(e.E)}">${
          cont ? `<span class="s">${cont.trim()}</span> ` : ''}${e.t.replace(/<[^>]+>/g, '')}</div>`;
      }
      h += `</div>`;
    }
    h += `</div></div>`;
  }
  el.innerHTML = h + `</div><div class="legend">
    <span><i style="background:#8FBF9E"></i>住宿</span><span><i style="background:#E8C77A"></i>租车</span>
    <span><i style="background:#8FB6E8"></i>航班</span><span><i style="background:#3A3630;border:1px solid var(--hair2)"></i>活动</span>
    <span><i style="box-shadow:inset 0 0 0 2px var(--aurora);background:#E8C77A"></i>青色描边 = 已付钱</span>
    <span><i style="background:repeating-linear-gradient(45deg,#232019,#232019 4px,#1C1915 4px,#1C1915 8px)"></i>斜纹 = 还没定</span>
    <span>‹ › = 跨到前/后一天</span></div>`;
}

/* ---------- 自动体检 ----------
 * 这四项全部从上面那张图的 ISO 时刻**现算**，不是手写的结论。
 * 改了 data.js 的时间，这里的判断会跟着变 —— 这是它能抓到真问题的原因。
 */
function health(el) {
  const EVS = EV.map(e => ({ ...e, S: new Date(e.s), E: new Date(e.e) }));
  const d0 = new Date(DAY0 + 'T00:00'), out = [];

  /* ① 每一夜在住处待多久（22:00–次日 09:00 这个窗口内被 stay 盖住的时长） */
  {
    const rows = [];
    for (let i = 0; i < DAYN - 1; i++) {
      const ns = new Date(d0.getTime() + i * 864e5 + 22 * 36e5), ne = new Date(d0.getTime() + (i + 1) * 864e5 + 9 * 36e5);
      const hrs = EVS.filter(e => e.lane === 'stay')
        .reduce((s, e) => s + Math.max(0, Math.min(e.E, ne) - Math.max(e.S, ns)), 0) / 36e5;
      if (hrs > 0) rows.push([`${md_(ns)} 夜`, hrs, hrs >= 7]);
    }
    const bad = rows.filter(r => !r[2]);
    out.push({
      cls: bad.length ? 'amb' : 'ok', h: '🏠 每一夜都有地方睡吗',
      sub: '口径：22:00–次日 09:00 窗口内待在住处的时长，不是「睡着」',
      li: rows.map(r => `${r[0]}：${r[2] ? '✅' : '⚠️'} <b>${r[1].toFixed(1)} 小时</b>`),
      tail: bad.length
        ? `<b>${bad.length} 个夜晚短于 7 小时</b>：${bad.map(r => r[0]).join('、')} —— 都是<b>已出票航班</b>造成的（9/24 是 21:30 落地 / 06:15 起飞，9/29 是 00:45 落地 / 早上再飞）。已把这两夜换成<b>连廊直通航站楼的 Radisson</b>，各多睡约 50 分钟并删掉四趟深夜打车，这是航班既定前提下的上限。`
        : '13 夜全部被住宿覆盖 ✅',
    });
  }
  /* ② 落地 → 取车等多久 */
  {
    const rows = EVS.filter(e => e.lane === 'fly').map(f => {
      const p = EVS.find(e => e.lane === 'car' && e.S >= f.E && e.S - f.E < 8 * 36e5);
      if (!p) return null;
      const m = (p.S - f.E) / 6e4;
      return `${md_(f.E)} ${hm(f.E)} 落地 → ${hm(p.S)} 取车：${m <= 45 ? '✅' : '⚠️'} 等 <b>${m} 分钟</b>`;
    }).filter(Boolean);
    out.push({
      cls: 'ok', h: '🚗 落地到取车要等多久', sub: '目标 ~30 分钟，不想在机场干等',
      li: rows,
      tail: '冰岛那台是<b>摆渡车取车</b>（KEF 所有自动挡四驱都不在航站楼内）→ 按落地 +45 分钟算；其余三台都是 <b>In terminal</b>。',
    });
  }
  /* ③ 还车 → 起飞的缓冲。洲际 3h / 欧洲 2h / 国内小机场 50min，三套标准不能混 */
  {
    const rows = EVS.filter(e => e.lane === 'car').map(c => {
      const f = EVS.find(e => e.lane === 'fly' && e.S >= c.E && e.S - c.E < 10 * 36e5);
      if (!f) return null;
      const m = (f.S - c.E) / 6e4, intl = /北京|洲际/.test(f.t), need = intl ? 180 : 50;
      const ok = m >= need;
      return `${md_(c.E)} ${hm(c.E)} 还车 → ${hm(f.S)} 起飞：${ok ? '✅' : '❌'} 缓冲 <b>${m} 分钟</b>${
        ok ? '' : `（${intl ? '洲际至少要留 3 小时' : '太紧'}）`}`;
    }).filter(Boolean);
    out.push({
      cls: 'amb', h: '✈️ 还车到起飞够不够', sub: '洲际 3 小时 / 欧洲 2 小时 / 国内小机场 50 分钟 —— 三套标准分开判',
      li: rows,
      tail: '🔴 <b>10/6 那一条要特别注意</b>：车③ 单子约的是 <b>13:00 还车</b>，而洲际起飞时刻还是占位值。若洲际在上午/中午起飞，<b>必须把还车改早到 09:00</b>（24 小时内同为 1 个计费日，改早不涨价，免费取消到 10/3）。',
    });
  }
  /* ④ 要移动的时候手上有车吗 */
  {
    const moves = EVS.filter(e => e.lane === 'act' && /→|机场|开车|回 OSL/.test(e.t));
    const bad = moves.filter(m => !EVS.some(c => c.lane === 'car' && c.S <= m.S && c.E >= m.E));
    out.push({
      cls: bad.length ? 'amb' : 'ok', h: '🚕 要移动的时候手上有车吗',
      sub: '没车的移动段必须另外安排（打车 / 班车 / 步行）',
      li: bad.length ? bad.map(m => `${md_(m.S)} ${hm(m.S)} <b>${m.t.replace(/<[^>]+>/g, '')}</b>`)
        : ['所有需要开车的段都被某台车盖住 ✅'],
      tail: bad.length
        ? '这些段<b>已经全部解决</b>：两个奥斯陆中转夜改住连廊直通航站楼的酒店后，原来那两段「没车又要打车 20 分钟」直接消失，剩下的是 5 分钟步行。'
        : '两个奥斯陆中转夜改住机场连廊酒店之后，全程再没有「没车又要移动」的段落。',
    });
  }

  el.innerHTML = `<div class="cards">` + out.map(c => `<div class="card ${c.cls}">
    <h3>${c.h}</h3><div class="s" style="margin-bottom:9px">${c.sub}</div>
    <ul>${c.li.map(x => `<li>${x}</li>`).join('')}</ul>
    <div class="s" style="margin-top:11px;color:var(--ink2)">${c.tail}</div></div>`).join('') + `</div>`;
}

/* ---------- 逐日卡 ---------- */
function days(el, limit) {
  const D = limit ? DAYS.slice(0, limit) : DAYS;
  el.innerHTML = D.map(d => {
    const im = (d.imgs || [])[0];
    return `<div class="day">
      <div class="ph">${im ? `<img src="${im.src}" alt="${esc(d.t)}" loading="lazy">` : ''}</div>
      <div class="tx">
        <div class="no">DAY ${d.n} · ${d.date} ${d.wd}</div>
        <h3>${esc(d.t)}</h3><div class="en">${esc(d.en || '')}</div>
        <p>${md(d.body || '')}</p>
        <div class="kv">
          ${d.drive ? `<span class="badge">🚗 ${esc(d.drive)}</span>` : ''}
          ${d.stayname ? `<span class="badge ok">🛏 ${esc(d.stayname)}</span>` : ''}
        </div>
      </div></div>`;
  }).join('');
}

/* ---------- 待办 ---------- */
function tofill(el) {
  el.innerHTML = `<div class="tw"><table>
    <thead><tr><th>急不急</th><th>要做什么</th><th>谁</th><th>为什么 / 依据</th></tr></thead>
    <tbody>${TOFILL.map(t => `<tr>
      <td><span class="badge ${/🔴🔴/.test(t.p) ? 'hot' : /🔴|🟠/.test(t.p) ? 'amb' : ''}">${esc(t.p)}</span></td>
      <td>${md(t.what)}</td><td class="s">${esc(t.who)}</td>
      <td>${md(t.why)}<div class="s" style="margin-top:5px">${md(t.ev || '')}</div></td>
    </tr>`).join('')}</tbody></table></div>`;
}
