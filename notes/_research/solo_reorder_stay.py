#!/usr/bin/env python3
"""「换顺序」方案（尼斯 → 伦敦 10/10–10/13 → 里斯本 10/13–10/17）的住宿行情快查。

只为回答一个问题：住的日期挪了以后，伦敦（变成周末）和里斯本（变成周二到周六）的房
会不会明显更贵 / 更满。每城 Airbnb 翻 2 页 + Booking 酒店一次（拿「已无房 %」和价）。
Usage: python3 solo_reorder_stay.py <out.json>
"""
import json, re, sys
from playwright.sync_api import sync_playwright
import abnb_interest as AI
from abnb_scrape import UA, parse_card
from abnb_detail2 import price
from solo_bksearch import run

AI.CITIES["lon"] = ("2026-10-10", "2026-10-13", AI.CITIES["lon"][2], AI.CITIES["lon"][3])
AI.CITIES["lis"] = ("2026-10-13", "2026-10-17", AI.CITIES["lis"][2], AI.CITIES["lis"][3])
res = {}
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1600, "height": 1100})
    for city in ("lon", "lis"):
        pg = ctx.new_page(); rows = []
        pg.goto(AI.url_for(city), wait_until="domcontentloaded", timeout=90_000)
        for n in range(2):
            pg.wait_for_timeout(8000)
            cards = pg.locator('[data-testid="card-container"]')
            for i in range(cards.count()):
                try:
                    r = parse_card(cards.nth(i).inner_text(timeout=4000))
                except Exception:
                    continue
                r["total_eur"] = price(r["raw"]); rows.append(r)
            try:
                pg.locator('a[aria-label="Next"]').first.click(timeout=5000)
            except Exception:
                break
        pg.close()
        res[city] = {"airbnb": rows}
    ci = {"lon": ("43", "district", "2026-10-10", "2026-10-13"), "lis": ("-2167973", "city", "2026-10-13", "2026-10-17")}
    for city, (did, typ, a, b) in ci.items():
        r = run(ctx, city, did, typ, a, b, "ht_id%3D204%3Breview_score%3D80&order=price")
        res[city]["booking"] = r
        print(city, "airbnb", len(res[city]["airbnb"]), "booking found", r["found"], "unavail", r["unavail_pct"], flush=True)
    br.close()
json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
