#!/usr/bin/env python3
"""Harvest DiscoverCars location ids from the autocomplete XHR."""
import json,re,sys
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
TERMS=sys.argv[1:] or ["Reykjavik","Keflavik"]
hits=[]
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    pg=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1600,"height":1100}).new_page()
    def on_resp(r):
        u=r.url
        if not re.search(r"(location|autocomplete|suggest|search)",u,re.I): return
        try:
            if "json" not in (r.headers.get("content-type") or ""): return
            hits.append({"url":u[:140],"body":r.text()[:60000]})
        except Exception: pass
    pg.on("response",on_resp)
    pg.goto("https://www.discovercars.com/",wait_until="domcontentloaded",timeout=90000)
    pg.wait_for_timeout(4000)
    for s in ['#onetrust-accept-btn-handler','button:has-text("Accept")']:
        try: pg.locator(s).first.click(timeout=2000)
        except Exception: pass
    for term in TERMS:
        box=pg.locator('input[name="PickupLocation"]'); box.click(); box.fill("")
        box.type(term,delay=150); pg.wait_for_timeout(4000)
    br.close()
seen=set()
for h in hits:
    for m in re.finditer(r'\{[^{}]{0,400}?"[Ii]d"\s*:\s*(\d{2,6})[^{}]{0,400}?\}',h["body"]):
        blob=m.group(0)
        if not re.search(r"Reykjav|Keflav|Iceland",blob,re.I): continue
        name=re.search(r'"[Nn]ame"\s*:\s*"([^"]{2,80})"',blob)
        if not name: continue
        key=(m.group(1),name.group(1))
        if key in seen: continue
        seen.add(key)
        print(f"  id={m.group(1):>6}  {name.group(1)}   [{blob[:150]}]")
print("xhr responses captured:",len(hits))
for h in hits[:4]: print("  ",h["url"])
