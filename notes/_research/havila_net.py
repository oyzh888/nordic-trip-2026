#!/usr/bin/env python3
"""The Havila engine is a Flutter/CanvasKit app -> zero DOM. Scrape its network
layer instead: log every non-asset request and look for the availability API.
"""
import json
import pathlib
import re
import sys
import urllib.parse

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
MONTH = int(sys.argv[1]) if len(sys.argv) > 1 else 10
YEAR = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
SLUG = sys.argv[3] if len(sys.argv) > 3 else f"hav-net-{YEAR}{MONTH:02d}"
WAIT = int(sys.argv[4]) if len(sys.argv) > 4 else 45
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)

inj = {"caller": "D-FLOW", "adults": 4, "children": 0, "locale": "en",
       "month": MONTH, "year": YEAR, "productTypes": "NORWEGIAN COAST"}
URL = ("https://prod.havilavoyages.com/touchhvl/?inJson="
       + urllib.parse.quote(json.dumps(inj), safe=""))

NOISE = re.compile(r"google|doubleclick|hubspot|clarity|collect\.|gstatic|"
                   r"challenge-platform|cdn-cgi/rum|\.(js|css|png|jpg|svg|woff2?|wasm|ttf)(\?|$)")

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-GB",
                         viewport={"width": 1600, "height": 1400})
    pg = ctx.new_page()
    seen = []

    def on_resp(r):
        if NOISE.search(r.url):
            return
        it = {"m": r.request.method, "u": r.url[:500], "s": r.status,
              "rt": r.request.resource_type}
        try:
            if r.request.post_data:
                it["post"] = r.request.post_data[:4000]
        except Exception:
            pass
        try:
            t = r.text()
            it["len"] = len(t)
            it["body"] = t[:40000]
        except Exception:
            pass
        seen.append(it)

    ctx.on("response", on_resp)
    pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(WAIT * 1000)
    (out / f"{SLUG}.json").write_text(json.dumps(
        {"url": URL, "requests": seen}, ensure_ascii=False, indent=1))
    for s in seen:
        print(s["s"], s["m"], s["rt"], s.get("len", "-"), s["u"][:220])
        if s.get("post"):
            print("     POST:", s["post"][:600])
    br.close()
