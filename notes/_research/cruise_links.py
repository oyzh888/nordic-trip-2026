#!/usr/bin/env python3
"""Harvest port-to-port / booking hrefs from Hurtigruten + Havila."""
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

URLS = [
    ("hrg-home", "https://www.hurtigruten.com/en-us/"),
    ("hrg-nce", "https://www.hurtigruten.com/en-us/norwegian-coastal-express"),
    ("havila-p2p-nb", "https://www.havilavoyages.com/nb/havn-til-havn"),
]
PAT = re.compile(r"port|havn|book|voyage|reis|search|sail", re.I)

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out_cruise")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1100})
    for slug, url in URLS:
        pg = ctx.new_page()
        rec = {"slug": slug, "url": url}
        try:
            resp = pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
            rec["status"] = resp.status if resp else None
            pg.wait_for_timeout(8000)
            links = pg.eval_on_selector_all(
                "a", "els => els.map(e => ({h:e.getAttribute('href')||'', "
                "t:(e.innerText||'').trim().slice(0,60)}))")
            seen, keep = set(), []
            for l in links:
                if not l["h"] or l["h"] in seen:
                    continue
                seen.add(l["h"])
                if PAT.search(l["h"]) or PAT.search(l["t"]):
                    keep.append(l)
            rec["links"] = keep[:120]
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        (out / f"{slug}-links.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        print(f"== {slug} status={rec.get('status')} {rec.get('error','')}")
        for l in rec.get("links", [])[:60]:
            print(f"   {l['h'][:110]}   <- {l['t']}")
        pg.close()
    br.close()
