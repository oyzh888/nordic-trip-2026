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
out = pathlib.Path("out_fly_air")
out.mkdir(parents=True, exist_ok=True)

JOBS = [
    ("A-svj-tos-1002", "SVJ", "TOS", "2026-10-02"),
    ("A-lkn-tos-1002", "LKN", "TOS", "2026-10-02"),
    ("A-eve-tos-1002", "EVE", "TOS", "2026-10-02"),
    ("A-svj-boo-1002", "SVJ", "BOO", "2026-10-02"),
    ("A-lkn-boo-1002", "LKN", "BOO", "2026-10-02"),
    ("A-boo-tos-1002", "BOO", "TOS", "2026-10-02"),
    ("A-svj-tos-0930", "SVJ", "TOS", "2026-09-30"),
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
            pg.screenshot(path=str(out / f"{slug}.png"), full_page=True)
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
