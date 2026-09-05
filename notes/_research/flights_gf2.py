#!/usr/bin/env python3
"""Live one-way fares off Google Flights (DOM-rendered), as the concrete
fallback to the 10/2 Svolvær->Tromso coastal sailing.

Usage: python3 flights_gf.py
"""
import json
import pathlib
import re
import urllib.parse

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
out = pathlib.Path("out_flights2")
out.mkdir(parents=True, exist_ok=True)

JOBS = [
    # 🆕 2026-09-04：四条「取车时间取决于它」的航段。SAS/Norwegian 在 Google Flights 上有供货
    # （只有 Widerøe 没有 —— 那条已经靠 OTA 解决了：WF816 LKN 15:40→TOS 16:35）
    ("osl-kef-0925", "OSL", "KEF", "2026-09-25"),   # 决定冰岛那台几点提车
    ("kef-osl-0929", "KEF", "OSL", "2026-09-29"),   # 决定冰岛那台几点还车
    ("osl-eve-0930", "OSL", "EVE", "2026-09-30"),   # 核实「10:35 落地」这个假设
    ("tos-osl-1005", "TOS", "OSL", "2026-10-05"),   # 决定奥斯陆那台几点提车
]


def url_for(fr, to, d):
    q = f"one-way flights from {fr} to {to} on {d} for 4 adults"
    return ("https://www.google.com/travel/flights?hl=en&curr=NOK&q="
            + urllib.parse.quote(q))


with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1500, "height": 1400})
    summary = {}
    for slug, fr, to, d in JOBS:
        pg = ctx.new_page()
        rec = {"from": fr, "to": to, "date": d, "url": url_for(fr, to, d)}
        try:
            pg.goto(rec["url"], wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(3000)
            for sel in ('button:has-text("Accept all")', 'button:has-text("Reject all")'):
                try:
                    pg.locator(sel).first.click(timeout=3000)
                    break
                except Exception:
                    pass
            pg.wait_for_timeout(12000)
            body = pg.inner_text("body")
            rec["body"] = body[:16000]
            # each result row is an li under the results list
            rows = pg.locator("li").filter(has_text=re.compile(r"kr|NOK"))
            offers = []
            for i in range(min(rows.count(), 25)):
                t = re.sub(r"\s+", " ", rows.nth(i).inner_text(timeout=3000)).strip()
                if 30 < len(t) < 400 and re.search(r"\d", t):
                    offers.append(t)
            rec["offers"] = offers
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        (out / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        summary[slug] = rec.get("offers", [])[:8]
        print(f"== {slug} {rec.get('error','')}")
        for o in rec.get("offers", [])[:10]:
            print("   ", o[:220])
        pg.close()
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    br.close()
