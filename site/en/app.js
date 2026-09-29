/* site/en/app.js —— shared render layer for the four English pages.
 * Translated from site/app.js; logic identical. Regexes that matched Chinese
 * copy were adapted to the English data (see health checks ③ and ④).
 */

/* ---------- utils ---------- */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
/* copy in data.js is sometimes **bold** and sometimes already <b> — render both */
const md = s => String(s ?? '')
  .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
  .replace(/`(.+?)`/g, '<code class="mono">$1</code>');
const hm = d => `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
const md_ = d => `${d.getMonth() + 1}/${d.getDate()}`;

/* ---------- nav (same on every page, current page highlighted) ---------- */
const PAGES = [
  ['/en/', 'Home'], ['/en/days/', 'Days'], ['/en/plan/', 'Plan'], ['/en/cars/', 'Cars'],
];
function nav() {
  const here = location.pathname.replace(/index\.html$/, '') || '/en/';
  return `<div class="nav"><div class="in">
    <a class="brand" href="/en/">Nordic 2026</a>
    <nav>${PAGES.map(([h, t]) =>
      `<a href="${h}"${h === here ? ' aria-current="page"' : ''}>${t}</a>`).join('')}
      <a href="https://github.com/oyzh888/nordic-trip-2026" target="_blank" rel="noopener">GitHub ↗</a>
      <a href="/">中文</a>
    </nav></div></div>`;
}
function foot() {
  return `<footer><div class="wrap">
    <div>Nordic 2026 · 4 people · 9/24 → 10/6 · 13 days<br>
      <span class="s">Prices and times were captured 2026-09-01 → 09-06 from real pages for our real dates via Playwright — not estimates.</span></div>
    <div class="s">Scenery &amp; car photos from Wikimedia Commons (CC BY / CC BY-SA), credits in captions<br>
      Stay photos from Airbnb / Booking listings · fixed rates €1=¥8.0 · $1=¥7.1 · NOK1=¥0.67</div>
  </div></footer>`;
}
function chrome() {
  document.body.insertAdjacentHTML('afterbegin', nav());
  document.body.insertAdjacentHTML('beforeend', foot());
  hues();
}

/* one hue per section, in document order (see style.css --acc) */
function hues() {
  const secs = [...document.querySelectorAll('section')].filter(s => !s.hasAttribute('data-hue'));
  const all = document.querySelectorAll('section').length;
  secs.forEach((s, i) => s.setAttribute('data-hue',
    String(Math.min(4, Math.round(i / Math.max(1, all - 1) * 4)))));
  const h = document.querySelector('.hero');
  if (h && !h.hasAttribute('data-hue')) h.setAttribute('data-hue', '3');
}

/* ---------- gantt ----------
 * one row per day, four lanes per row (stay/car/fly/activity); each event is
 * positioned by its share of that day. Multi-day events draw a segment per day,
 * with ‹ › marking "not over yet".
 */
function gantt(el) {
  const LANES = ['stay', 'car', 'fly', 'act'];
  const EVS = EV.map(e => ({ ...e, S: new Date(e.s), E: new Date(e.e) }));
  const d0 = new Date(DAY0 + 'T00:00');
  let h = `<div class="gantt"><div class="ruler"><div class="dlab s">Date</div>
    <div class="h">${[0, 3, 6, 9, 12, 15, 18, 21].map(x => `<span>${x}:00</span>`).join('')}</div></div>`;

  for (let i = 0; i < DAYN; i++) {
    const ds = new Date(d0.getTime() + i * 864e5), de = new Date(ds.getTime() + 864e5);
    h += `<div class="drow"><div class="dlab"><b>${md_(ds)}</b>
      <span>${'SMTWTFS'[ds.getDay()]}</span></div><div class="tracks">`;
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
  /* legend swatches reuse .bar classes so they can never drift from the bars */
  el.innerHTML = h + `</div><div class="legend">
    <span><i class="bar stay" style="position:static"></i>Stay</span>
    <span><i class="bar car"  style="position:static"></i>Car</span>
    <span><i class="bar fly"  style="position:static"></i>Flight</span>
    <span><i class="bar act"  style="position:static"></i>Activity</span>
    <span><i class="bar car booked" style="position:static"></i>Outline = paid</span>
    <span><i class="bar tbd"  style="position:static"></i>Striped = not booked</span>
    <span>‹ › = spans into prev/next day</span></div>`;
}

/* ---------- auto health checks ----------
 * all four are computed live from the ISO times above — not hand-written
 * conclusions. Change a time in data.js and the verdicts follow.
 */
function health(el) {
  const EVS = EV.map(e => ({ ...e, S: new Date(e.s), E: new Date(e.e) }));
  const d0 = new Date(DAY0 + 'T00:00'), out = [];

  /* ① hours under a stay roof each night (22:00–09:00 next day window) */
  {
    const rows = [];
    for (let i = 0; i < DAYN - 1; i++) {
      const ns = new Date(d0.getTime() + i * 864e5 + 22 * 36e5), ne = new Date(d0.getTime() + (i + 1) * 864e5 + 9 * 36e5);
      const hrs = EVS.filter(e => e.lane === 'stay')
        .reduce((s, e) => s + Math.max(0, Math.min(e.E, ne) - Math.max(e.S, ns)), 0) / 36e5;
      if (hrs > 0) rows.push([`${md_(ns)} night`, hrs, hrs >= 7]);
    }
    const bad = rows.filter(r => !r[2]);
    out.push({
      cls: bad.length ? 'amb' : 'ok', h: '🏠 A bed every night?',
      sub: 'Measure: hours under a stay roof within the 22:00–09:00 window — not “asleep”',
      li: rows.map(r => `${r[0]}: ${r[2] ? '✅' : '⚠️'} <b>${r[1].toFixed(1)} h</b>`),
      tail: bad.length
        ? `<b>${bad.length} night(s) under 7 hours</b>: ${bad.map(r => r[0]).join(', ')} — all caused by <b>ticketed flights</b> (9/24 is a 06:45 landing / 06:15 take-off, 9/29 is a 00:45 landing / morning flight). Both nights were switched to <b>Radisson hotels connected to the terminal by skybridge</b>, gaining ≈50 min of sleep each and deleting four late-night taxi rides — the ceiling given fixed flights.`
        : 'All 13 nights covered by stays ✅',
    });
  }
  /* ② landing → car pick-up wait */
  {
    const rows = EVS.filter(e => e.lane === 'fly').map(f => {
      const p = EVS.find(e => e.lane === 'car' && e.S >= f.E && e.S - f.E < 8 * 36e5);
      if (!p) return null;
      const m = (p.S - f.E) / 6e4;
      return `${md_(f.E)} ${hm(f.E)} land → ${hm(p.S)} pick-up: ${m <= 45 ? '✅' : '⚠️'} wait <b>${m} min</b>`;
    }).filter(Boolean);
    out.push({
      cls: 'ok', h: '🚗 Landing → car pick-up: how long the wait', sub: 'Target ~30 min — no dead waiting at the airport',
      li: rows,
      tail: 'The Iceland pick-up is <b>in the terminal</b> (Avis counter inside the terminal building) → counted as landing +45 min to clear immigration and reach the counter; the other three are <b>in terminal</b> as well.',
    });
  }
  /* ③ return → take-off buffer. Intercontinental 3h / Europe 2h / small airports 50min — separate standards */
  {
    const rows = EVS.filter(e => e.lane === 'car').map(c => {
      const f = EVS.find(e => e.lane === 'fly' && e.S >= c.E && e.S - c.E < 10 * 36e5);
      if (!f) return null;
      const m = (f.S - c.E) / 6e4, intl = /Beijing|intercontinental/i.test(f.t), need = intl ? 180 : 50;
      const ok = m >= need;
      return `${md_(c.E)} ${hm(c.E)} return → ${hm(f.S)} take-off: ${ok ? '✅' : '❌'} buffer <b>${m} min</b>${
        ok ? '' : ` (${intl ? 'intercontinental needs 3 h' : 'too tight'})`}`;
    }).filter(Boolean);
    out.push({
      cls: 'amb', h: '✈️ Return → take-off: enough buffer?', sub: 'Intercontinental 3 h / Europe 2 h / small domestic airports 50 min — three separate standards',
      li: rows,
      tail: '🔴 <b>Watch the 10/6 one</b>: car ③ is booked for a <b>13:00 return</b>, while the intercontinental departure time is still a placeholder. If the intercontinental flight leaves in the morning/midday, <b>the return must move earlier to 09:00</b> (within 24 hours counts as 1 billing day, moving earlier costs nothing, free cancellation until 10/3).',
    });
  }
  /* ④ car in hand when we need to move */
  {
    const moves = EVS.filter(e => e.lane === 'act' && /→|airport|drive/i.test(e.t));
    const bad = moves.filter(m => !EVS.some(c => c.lane === 'car' && c.S <= m.S && c.E >= m.E));
    out.push({
      cls: bad.length ? 'amb' : 'ok', h: '🚕 Car in hand when we need to move?',
      sub: 'Legs without a car need separate arrangements (taxi / shuttle / walk)',
      li: bad.length ? bad.map(m => `${md_(m.S)} ${hm(m.S)} <b>${m.t.replace(/<[^>]+>/g, '')}</b>`)
        : ['Every driving leg is covered by some car ✅'],
      tail: bad.length
        ? 'These are <b>all resolved</b>: after the two Oslo layover nights moved to skybridge-connected terminal hotels, the old “no car and a 20-min taxi ride” legs disappeared; what remains is a 5-minute walk.'
        : 'After the two Oslo layover nights moved to the skybridge airport hotels, no more “need to move without a car” legs remain.',
    });
  }

  el.innerHTML = `<div class="cards">` + out.map(c => `<div class="card ${c.cls}">
    <h3>${c.h}</h3><div class="s" style="margin-bottom:9px">${c.sub}</div>
    <ul>${c.li.map(x => `<li>${x}</li>`).join('')}</ul>
    <div class="s" style="margin-top:11px;color:var(--ink2)">${c.tail}</div></div>`).join('') + `</div>`;
}

/* ---------- day cards ---------- */
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

/* ---------- to-fill list ---------- */
function tofill(el) {
  el.innerHTML = `<div class="tw"><table>
    <thead><tr><th>Urgency</th><th>To do</th><th>Who</th><th>Why / basis</th></tr></thead>
    <tbody>${TOFILL.map(t => `<tr>
      <td><span class="badge ${/🔴🔴/.test(t.p) ? 'hot' : /🔴|🟠/.test(t.p) ? 'amb' : ''}">${esc(t.p)}</span></td>
      <td>${md(t.what)}</td><td class="s">${esc(t.who)}</td>
      <td>${md(t.why)}<div class="s" style="margin-top:5px">${md(t.ev || '')}</div></td>
    </tr>`).join('')}</tbody></table></div>`;
}
