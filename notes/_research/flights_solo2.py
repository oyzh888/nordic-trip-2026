#!/usr/bin/env python3
"""Steve 一个人的后半段 · 第二轮：把「葡萄牙」这个新变量加进来。

第一轮（notes/SOLO-after-oslo.md，2026-09-05）已经回答了：南法 vs 伦敦怎么选、
伦敦→SFO 的价格断崖在 10/15。这一轮要回答**新的两个问题**：
  ① 先法国还是先英国（顺序）——本质是"哪个城市当回程跳板"，所以要比各出发地飞 SFO 的价
  ② 从哪飞 SFO 最便宜 —— 里斯本有 TAP 直飞，这是第一轮完全没查的一条

口径（和第一轮一致，方便对比）：**1 adult · 单程 · USD**。
⚠️ 与本 repo 其它机票脚本不同 —— 那些都是 `for 4 adults`。

抓法：Google Flights 的结果是异步流入的，所以**轮询到条数不再增长**才读，
不用固定 sleep（固定等待要么不够、要么白等，而且等不够会静默拿到部分结果）。

Usage: python3 flights_solo2.py out_solo3
"""
import json, pathlib, re, sys, urllib.parse
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

JOBS = [
 # ---- 回程：各出发地 → SFO（这一组是核心） ----
 ("ret-lis-1019", "LIS", "SFO", "2026-10-19", "🇵🇹 里斯本 · TAP 有直飞"),
 ("ret-lis-1017", "LIS", "SFO", "2026-10-17", "🇵🇹 里斯本 · 周六"),
 ("ret-lis-1022", "LIS", "SFO", "2026-10-22", "🇵🇹 里斯本 · 再晚 3 天"),
 ("ret-lhr-1019", "LHR", "SFO", "2026-10-19", "🇬🇧 伦敦 · 第一轮查过 $560"),
 ("ret-lhr-1022", "LHR", "SFO", "2026-10-22", "🇬🇧 伦敦 · 同日对照"),
 ("ret-opo-1019", "OPO", "SFO", "2026-10-19", "🇵🇹 波尔图"),
 ("ret-mad-1019", "MAD", "SFO", "2026-10-19", "🇪🇸 马德里（伊比利亚半岛对照）"),
 ("ret-cdg-1019", "CDG", "SFO", "2026-10-19", "🇫🇷 巴黎"),
 ("ret-nce-1019", "NCE", "SFO", "2026-10-19", "🇫🇷 尼斯（第一轮 $1,118，复核）"),
 # ---- 中间段：南法 → 下一站 ----
 ("mid-nce-lis-1012", "NCE", "LIS", "2026-10-12", "尼斯→里斯本"),
 ("mid-nce-lis-1013", "NCE", "LIS", "2026-10-13", "尼斯→里斯本 晚一天"),
 ("mid-mrs-lis-1013", "MRS", "LIS", "2026-10-13", "马赛→里斯本（若最后一站是普罗旺斯）"),
 ("mid-nce-lhr-1012", "NCE", "LHR", "2026-10-12", "尼斯→伦敦"),
 ("mid-lis-lhr-1019", "LIS", "LHR", "2026-10-19", "里斯本→伦敦（两个都去时的接法）"),
 # ---- 「先英国」那个顺序需要的两段 ----
 ("alt-osl-lon-1006", "OSL", "LON", "2026-10-06", "奥斯陆→伦敦（先英国方案）"),
 ("alt-lon-nce-1010", "LON", "NCE", "2026-10-10", "伦敦→尼斯（先英国方案）"),
]

PRICE = re.compile(r"\$\s?([\d,]+)")
DUR   = re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?")
STOPS = re.compile(r"(Nonstop|1 stop|2 stops|3 stops)", re.I)

def url_for(fr, to, d):
    q = f"one-way flights from {fr} to {to} on {d} for 1 adult"
    return "https://www.google.com/travel/flights?hl=en&curr=USD&q=" + urllib.parse.quote(q)

def parse(rows_text):
    out = []
    for t in rows_text:
        p, dm, st = PRICE.search(t), DUR.search(t), STOPS.search(t)
        if not (p and dm):
            continue
        mins = int(dm.group(1)) * 60 + int(dm.group(2) or 0)
        out.append(dict(price=int(p.group(1).replace(",", "")), mins=mins,
                        stops=(st.group(1) if st else "?"),
                        air=re.sub(r"\s+", " ", t)[:150]))
    # 同价同时长的重复行去掉
    seen, uniq = set(), []
    for o in sorted(out, key=lambda x: (x["price"], x["mins"])):
        k = (o["price"], o["mins"], o["stops"])
        if k in seen: continue
        seen.add(k); uniq.append(o)
    return uniq

outdir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out_solo3")
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
            # 轮询：等到"带 $ 的 li"数量连续两次不变（上限 40s）
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
            rec["waited_s"] = waited
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        (outdir / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        offs = rec.get("offers", [])
        summary[slug] = dict(label=label, best=offs[0] if offs else None, n=len(offs), url=rec["url"])
        best = offs[0] if offs else None
        ns = next((o for o in offs if o["stops"].lower() == "nonstop"), None)
        print(f"== {slug:20} {label}")
        if best:
            print(f"   最低 ${best['price']:>5} {best['mins']//60}h{best['mins']%60:02d} {best['stops']}")
            if ns and ns is not best:
                print(f"   最低直飞 ${ns['price']:>5} {ns['mins']//60}h{ns['mins']%60:02d}")
            elif not ns:
                print("   ⚠️ 没有直飞")
        else:
            print("   ❌ 没抓到", rec.get("error", "")[:90])
        sys.stdout.flush()
        pg.close()
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    br.close()
print("\n→", outdir / "summary.json")
