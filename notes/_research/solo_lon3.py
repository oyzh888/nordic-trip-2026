#!/usr/bin/env python3
"""伦敦改 3 晚（10/14→10/17）后重抓 Booking 两种排序，只跑伦敦。"""
import json, sys
from playwright.sync_api import sync_playwright
from solo_bksearch import run
from solo_pics import UA
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
    res = [run(ctx, "lon", "43", "district", "2026-10-14", "2026-10-17", "ht_id%3D204"),
           run(ctx, "lon", "43", "district", "2026-10-14", "2026-10-17", "ht_id%3D204%3Breview_score%3D80&order=price")]
    for r in res: print(r["found"], r["unavail_pct"], len(r["cards"]))
    json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
