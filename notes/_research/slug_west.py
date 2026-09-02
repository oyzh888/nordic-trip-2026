#!/usr/bin/env python3
"""Find booking.com slugs for west-Iceland (Snaefellsnes springboard) towns.

Why: the Borgarnes idea was killed on Airbnb grounds only (all 8 listings had
min-stay >= 2). Hotels there were never checked, even though the same
"Iceland countryside won't take 1 night -> use a hotel + 2 rooms" fallback is
exactly what 9/26 Hvolsvollur and 9/27 Hofn already do.

Usage: python3 slug_west.py   -> writes slugs_west.json
"""
import re, json
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

PAGES = [
    ("borgarnes",   "https://www.booking.com/city/is/borgarnes.en-us.html"),
    ("akranes",     "https://www.booking.com/city/is/akranes.en-us.html"),
    ("west-region", "https://www.booking.com/region/is/west-iceland.en-us.html"),
    ("stykkish",    "https://www.booking.com/city/is/stykkisholmur.en-us.html"),
    ("olafsvik",    "https://www.booking.com/city/is/olafsvik.en-us.html"),
]

out = {}
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1100})
    for name, url in PAGES:
        pg = ctx.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(4000)
            for _ in range(6):
                pg.mouse.wheel(0, 4000); pg.wait_for_timeout(900)
            html = pg.content()
        except Exception as e:
            out[name] = {"error": str(e)[:160]}; pg.close(); continue
        slugs = sorted(set(re.findall(r"/hotel/is/([a-z0-9\-]+)\.", html)))
        out[name] = {"n_slugs": len(slugs), "slugs": slugs}
        print(f"{name}: {len(slugs)} slugs -> {slugs[:30]}", flush=True)
        pg.close()
    br.close()
open("slugs_west.json", "w").write(json.dumps(out, indent=1))
print("wrote slugs_west.json")
