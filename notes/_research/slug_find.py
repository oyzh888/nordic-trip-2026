#!/usr/bin/env python3
"""Find real booking.com property slugs from server-rendered SEO landing pages."""
import re, json, sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

PAGES = [
    ("lofoten", "https://www.booking.com/region/no/lofoten.en-us.html"),
    ("lofoten-apt", "https://www.booking.com/apartments/region/no/lofoten.en-us.html"),
    ("tromso", "https://www.booking.com/city/no/tromso.en-us.html"),
    ("tromso-apt", "https://www.booking.com/apartments/city/no/tromso.en-us.html"),
    ("gardermoen", "https://www.booking.com/city/no/gardermoen.en-us.html"),
    ("hofn", "https://www.booking.com/city/is/hofn.en-us.html"),
    ("vik", "https://www.booking.com/city/is/vik.en-us.html"),
]
WANT = ["svinoy", "sakris", "reinefjord", "enter", "hali", "milk", "park-inn",
        "runway", "vervet", "nusfjord", "katla", "vik-i-", "myrdal", "smart-",
        "clarion", "quality", "scandic", "thon", "radisson"]

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
            out[name] = {"error": str(e)[:120]}; pg.close(); continue
        slugs = sorted(set(re.findall(r"/hotel/(?:no|is)/([a-z0-9\-]+)\.", html)))
        hits = [s for s in slugs if any(w in s for w in WANT)]
        out[name] = {"n_slugs": len(slugs), "hits": hits, "sample": slugs[:25]}
        print(f"{name}: {len(slugs)} slugs; hits={hits}")
        pg.close()
    br.close()
open("slugs.json", "w").write(json.dumps(out, indent=1))
