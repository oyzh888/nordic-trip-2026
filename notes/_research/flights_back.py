#!/usr/bin/env python3
"""回程 10/18 伦敦 → 湾区：有没有比 Virgin $1,166 更便宜的？

口径（Steve 2026-09-24 问「两周翻倍是啥意思，有没有更便宜的」）：
  · 伦敦所有机场（LON = LHR/LGW/STN/LTN/LCY）→ SFO / SJC / OAK 三个湾区机场
  · 直飞 + 转机都要（转机只要 10/18 当天落地就行）
  · 顺手抓 Google 的价格判断（"Prices are currently high/typical/low" + 常见区间），
    回答「现在是不是贵的时候」
  · 10/17、10/19 只做对照（行程约束是周日 10/18 落地），不当选项
Usage: python3 flights_back.py <out.json>
"""
import json
import re
import sys
import urllib.parse

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JOBS_DEFAULT = [("lon-sfo-1018", "LON", "SFO", "2026-10-18"), ("lon-sjc-1018", "LON", "SJC", "2026-10-18"),
        ("lon-oak-1018", "LON", "OAK", "2026-10-18"), ("lhr-sfo-1018", "LHR", "SFO", "2026-10-18"),
        ("lon-sfo-1017", "LON", "SFO", "2026-10-17"), ("lon-sfo-1019", "LON", "SFO", "2026-10-19")]
PRICE = re.compile(r"\$\s?([\d,]+)")
DUR = re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?")
STOPS = re.compile(r"(Nonstop|1 stop|2 stops)", re.I)
TIMES = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)\s*[–\-—]\s*(\d{1,2}:\d{2}\s*[AP]M)(\+\d)?")
AIR = re.compile(r"(Virgin Atlantic|British Airways|United|American|Delta|Aer Lingus|Icelandair|"
                 r"Lufthansa|KLM|Air France|Alaska|JetBlue|Norse Atlantic|Condor|Iberia|SWISS|"
                 r"Air Canada|WestJet|TAP Air Portugal|Turkish|Finnair|SAS|Air India|Level)")
VIA = re.compile(r"\b(LHR|LGW|STN|LTN|LCY)[–-](?:([A-Z]{3})[–-])?(SFO|SJC|OAK)\b")
LAYOVER = re.compile(r"(\d+ hr(?: \d+ min)?) ([A-Z]{3})\b")


def to24(s):
    m = re.match(r"(\d{1,2}):(\d{2})\s*([AP])M", s.replace(" ", " ").strip(), re.I)
    h, mi, ap = int(m.group(1)), int(m.group(2)), m.group(3).upper()
    if ap == "P" and h != 12:
        h += 12
    if ap == "A" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}"


def main():
    res = {}
    JOBS = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else JOBS_DEFAULT
    with sync_playwright() as p:
        br = p.chromium.launch()
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1500, "height": 1600})
        for slug, fr, to, d in JOBS:
            pg = ctx.new_page()
            offs = []
            url = "https://www.google.com/travel/flights?hl=en&curr=USD&q=" + urllib.parse.quote(
                f"one-way flights from {fr} to {to} on {d} for 1 adult")
            insight = None
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=90000)
                for sel in ('button:has-text("Accept all")', 'button:has-text("Reject all")'):
                    try:
                        pg.locator(sel).first.click(timeout=2500)
                        break
                    except Exception:
                        pass
                # 等结果数稳定，不用固定 sleep
                last, stable, w = -1, 0, 0
                while w < 45 and stable < 2:
                    pg.wait_for_timeout(2500)
                    w += 2.5
                    n = pg.locator("li").filter(has_text=re.compile(r"\$")).count()
                    stable = stable + 1 if n == last else 0
                    last = n
                # 展开「View more flights」拿全
                try:
                    pg.locator('button:has-text("more flights")').first.click(timeout=3000)
                    pg.wait_for_timeout(4000)
                except Exception:
                    pass
                body = pg.inner_text("body")
                m = re.search(r"Prices are currently (\w+)[^\n]*", body)
                m2 = re.search(r"usually cost between \$[\d,]+\s*(?:[–-]|and)\s*\$[\d,]+", body)
                insight = {"level": m.group(1) if m else None, "range": m2.group(0) if m2 else None}
                rows = pg.locator("li").filter(has_text=re.compile(r"\$"))
                seen = set()
                for i in range(min(rows.count(), 60)):
                    try:
                        t = re.sub(r"\s+", " ", rows.nth(i).inner_text(timeout=3000))
                    except Exception:
                        continue
                    pr, dm, st, tm = PRICE.search(t), DUR.search(t), STOPS.search(t), TIMES.search(t)
                    if not (pr and dm and tm):
                        continue
                    mins = int(dm.group(1)) * 60 + int(dm.group(2) or 0)
                    k = (pr.group(1), tm.group(1), mins)
                    if k in seen:
                        continue
                    seen.add(k)
                    v = VIA.search(t)
                    lay = LAYOVER.findall(t)
                    offs.append(dict(price=int(pr.group(1).replace(",", "")), dep=to24(tm.group(1)),
                                     arr=to24(tm.group(2)), plus=tm.group(3) or "", mins=mins,
                                     stops=st.group(1) if st else "?",
                                     air=", ".join(dict.fromkeys(AIR.findall(t))) or "?",
                                     route=v.group(0) if v else None,
                                     layover=lay[0] if lay else None, raw=t[:260]))
            except Exception as e:
                print(slug, "ERR", type(e).__name__, e)
            offs.sort(key=lambda x: (x["price"], x["mins"]))
            res[slug] = dict(url=url, insight=insight, offers=offs)
            print(f"== {slug} {len(offs)} offers · {insight}", flush=True)
            for o in offs[:8]:
                print(f"   ${o['price']:>5} {o['dep']}->{o['arr']}{o['plus']} {o['mins']//60}h{o['mins']%60:02d} "
                      f"{o['stops']:<8} {o['air'][:30]:<30} {o['route']} {o['layover']}", flush=True)
            pg.close()
            json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
        br.close()


if __name__ == "__main__":
    main()
