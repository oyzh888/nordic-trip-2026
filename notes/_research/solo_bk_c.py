#!/usr/bin/env python3
"""方案 C 的 Booking 行情：伦敦 10/10–10/13、里斯本 10/13–10/17（周六回），
外加里斯本 10/13–10/18（周日回，只做对比）。每组两种排序：默认 + 按价格（评分 8+）。
Usage: python3 solo_bk_c.py <out.json>
"""
import json, sys
from playwright.sync_api import sync_playwright
from solo_bksearch import run
from solo_pics import UA
CHEAP = "ht_id%3D204%3Breview_score%3D80&order=price"
JOBS = [("lon", "43", "district", "2026-10-10", "2026-10-13"),
        ("lis", "-2167973", "city", "2026-10-13", "2026-10-17"),
        ("lis5", "-2167973", "city", "2026-10-13", "2026-10-18")]
res = {}
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
    for key, did, typ, a, b in JOBS:
        res[key] = [run(ctx, key, did, typ, a, b, "ht_id%3D204"), run(ctx, key, did, typ, a, b, CHEAP)]
        print(key, [(r["found"], r["unavail_pct"], len(r["cards"])) for r in res[key]], flush=True)
        json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    br.close()
