#!/usr/bin/env python3
"""Screenshot Booking.com property pages (room table) as bookable evidence."""
import json, pathlib, sys
from playwright.sync_api import sync_playwright
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
jobs = json.load(open(sys.argv[1])); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1500, "height": 1250})
    for j in jobs:
        pg = ctx.new_page()
        u = (f"https://www.booking.com/hotel/{j['hotel']}.html?checkin={j['checkin']}"
             f"&checkout={j['checkout']}&group_adults={j.get('adults',4)}&group_children=0"
             f"&no_rooms={j.get('rooms',2)}&selected_currency=EUR&lang=en-us")
        try:
            pg.goto(u, wait_until="domcontentloaded", timeout=120_000); pg.wait_for_timeout(8000)
            for sel in ('button[aria-label="Dismiss sign-in info."]', '#onetrust-accept-btn-handler'):
                try: pg.locator(sel).first.click(timeout=2500); pg.wait_for_timeout(600)
                except Exception: pass
            try:
                pg.locator("#hprt-table").first.scroll_into_view_if_needed(timeout=8000); pg.wait_for_timeout(2500)
            except Exception: pg.mouse.wheel(0, 2600); pg.wait_for_timeout(2000)
            pg.screenshot(path=str(out / f"{j['slug']}.png"))
            print("ok", j['slug'])
        except Exception as e:
            print("ERR", j['slug'], type(e).__name__, str(e)[:80])
        pg.close()
    br.close()
