#!/usr/bin/env python3
"""第三轮（2026-09-20）：法国 + 伦敦，且必须抓到**起降时刻**。

为什么要重抓：
  ① 9/5–9/7 的报价已过两周，而 10/6 只剩 16 天（同一段 LHR→SFO 两天翻过一倍，见上一轮）；
  ② 新增了「工作日 10:00–16:00 PT 要留出来」的约束 —— 这条只能用**时刻**来判，
     而前两轮的解析器只取了价格/时长/转机，**没有时刻**，拿不来用。

时区（10/6–10/24 期间，欧洲夏令时 10/25 才结束）：
  法国 CEST = UTC+2 = PT+9  → 10:00–16:00 PT  =  当地 19:00–01:00
  伦敦 BST  = UTC+1 = PT+8  → 10:00–16:00 PT  =  当地 18:00–24:00
→ 判据：**航班尽量落在当地 08:00–18:00 之间**（不压工作时段）；洲际回程尽量放周末。

Usage: python3 flights_solo3.py out_solo4
"""
import json, pathlib, re, sys, urllib.parse
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

JOBS = [
 # ---- 第一段：10/6（周二）从奥斯陆出发 ----
 ("a-osl-nce-1006", "OSL", "NCE", "2026-10-06", "先法国：奥斯陆→尼斯"),
 ("a-osl-lon-1006", "OSL", "LON", "2026-10-06", "先伦敦：奥斯陆→伦敦"),
 # ---- 中段：南法 → 伦敦 ----
 ("b-mrs-lhr-1015", "MRS", "LHR", "2026-10-15", "马赛→伦敦 周四"),
 ("b-mrs-lon-1017", "MRS", "LON", "2026-10-17", "马赛→伦敦 周六（搬家放周末）"),
 ("b-nce-lon-1017", "NCE", "LON", "2026-10-17", "尼斯→伦敦 周六"),
 # ---- 回程：洲际 ----
 ("c-lhr-sfo-1017", "LHR", "SFO", "2026-10-17", "伦敦→SFO 周六"),
 ("c-lhr-sfo-1018", "LHR", "SFO", "2026-10-18", "伦敦→SFO 周日"),
 ("c-lhr-sfo-1024", "LHR", "SFO", "2026-10-24", "伦敦→SFO 周六（+2 周版）"),
 ("c-lhr-sfo-1016", "LHR", "SFO", "2026-10-16", "伦敦→SFO 周五（对照：会吃掉工作日）"),
 ("c-cdg-sfo-1017", "CDG", "SFO", "2026-10-17", "巴黎→SFO 周六（若最后一站放巴黎）"),
 ("c-nce-sfo-1017", "NCE", "SFO", "2026-10-17", "尼斯→SFO 周六（先伦敦方案的回程）"),
]

PRICE = re.compile(r"\$\s?([\d,]+)")
DUR   = re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?")
STOPS = re.compile(r"(Nonstop|1 stop|2 stops|3 stops)", re.I)
# Google Flights 的行里时刻长这样：「10:35 AM – 1:35 PM」（可能带 +1）
TIMES = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)\s*[–\-—]\s*(\d{1,2}:\d{2}\s*[AP]M)")

def to24(s):
    s = s.replace(" ", " ").strip()
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP])M", s, re.I)
    if not m: return None
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == "P" and h != 12: h += 12
    if ap == "A" and h == 12: h = 0
    return f"{h:02d}:{mi:02d}"

def url_for(fr, to, d):
    q = f"one-way flights from {fr} to {to} on {d} for 1 adult"
    return "https://www.google.com/travel/flights?hl=en&curr=USD&q=" + urllib.parse.quote(q)

def parse(texts):
    out, seen = [], set()
    for t in texts:
        t1 = re.sub(r"\s+", " ", t)
        p, dm, st, tm = PRICE.search(t1), DUR.search(t1), STOPS.search(t1), TIMES.search(t1)
        if not (p and dm and tm): continue
        dep, arr = to24(tm.group(1)), to24(tm.group(2))
        if not (dep and arr): continue
        mins = int(dm.group(1)) * 60 + int(dm.group(2) or 0)
        air = re.search(r"(United|British Airways|Air France|Norwegian|easyJet|Ryanair|KLM|Lufthansa|"
                        r"SAS|TAP|Vueling|Iberia|Swiss|Delta|Virgin Atlantic|Wizz|Transavia|Aer Lingus)", t1)
        k = (p.group(1), dep, arr, mins)
        if k in seen: continue
        seen.add(k)
        out.append(dict(price=int(p.group(1).replace(",", "")), dep=dep, arr=arr, mins=mins,
                        stops=(st.group(1) if st else "?"), air=(air.group(1) if air else "?")))
    return sorted(out, key=lambda x: (x["price"], x["mins"]))

outdir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out_solo4")
outdir.mkdir(parents=True, exist_ok=True)
summary = {}
with sync_playwright() as p:
    br = p.chromium.launch()
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1500, "height": 1500})
    for slug, fr, to, d, label in JOBS:
        pg = ctx.new_page()
        rec = dict(slug=slug, frm=fr, to=to, date=d, label=label, url=url_for(fr, to, d))
        try:
            pg.goto(rec["url"], wait_until="domcontentloaded", timeout=90_000)
            for sel in ('button:has-text("Accept all")', 'button:has-text("Reject all")'):
                try: pg.locator(sel).first.click(timeout=2500); break
                except Exception: pass
            last, stable, waited = -1, 0, 0
            while waited < 40 and stable < 2:
                pg.wait_for_timeout(2500); waited += 2.5
                n = pg.locator("li").filter(has_text=re.compile(r"\$")).count()
                stable = stable + 1 if n == last else 0
                last = n
            rows = pg.locator("li").filter(has_text=re.compile(r"\$"))
            texts = []
            for i in range(min(rows.count(), 30)):
                try: texts.append(rows.nth(i).inner_text(timeout=3000))
                except Exception: pass
            rec["offers"] = parse(texts)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        (outdir / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        offs = rec.get("offers", [])
        summary[slug] = dict(label=label, url=rec["url"], offers=offs[:8])
        print(f"== {slug:18} {label}")
        for o in offs[:5]:
            print(f"   ${o['price']:>5} {o['dep']}→{o['arr']} {o['mins']//60}h{o['mins']%60:02d} "
                  f"{o['stops']:<8} {o['air']}")
        if not offs: print("   ❌", rec.get("error", "没解析到")[:80])
        sys.stdout.flush()
        pg.close()
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    br.close()
print("\n→", outdir / "summary.json")
