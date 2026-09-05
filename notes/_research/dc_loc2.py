#!/usr/bin/env python3
"""Harvest DiscoverCars location ids for arbitrary search terms.
Usage: python3 dc_loc2.py <filter-regex> <term> [term...]
（dc_loc.py 把过滤词写死成 Reykjav|Keflav|Iceland 了，这个版本让它当参数传）"""
import re,sys
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
FILT, TERMS = sys.argv[1], sys.argv[2:]
hits=[]
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    pg=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1600,"height":1100}).new_page()
    pg.on("response", lambda r: hits.append(r) if re.search(r"(location|autocomplete|suggest)",r.url,re.I) else None)
    bodies=[]
    def grab(r):
        try:
            if "json" in (r.headers.get("content-type") or ""): bodies.append(r.text()[:120000])
        except Exception: pass
    pg.on("response", grab)
    pg.goto("https://www.discovercars.com/",wait_until="domcontentloaded",timeout=90000)
    pg.wait_for_timeout(4000)
    for s in ['#onetrust-accept-btn-handler','button:has-text("Accept")']:
        try: pg.locator(s).first.click(timeout=2000)
        except Exception: pass
    for term in TERMS:
        box=pg.locator('input[name="PickupLocation"]'); box.click(); box.fill("")
        box.type(term,delay=140); pg.wait_for_timeout(4500)
    br.close()
seen=set()
for b in bodies:
    for m in re.finditer(r'\{[^{}]{0,500}?"[Ii]d"\s*:\s*"?(\d{2,6})"?[^{}]{0,500}?\}',b):
        blob=m.group(0)
        if not re.search(FILT,blob,re.I): continue
        name=re.search(r'"[Nn]ame"\s*:\s*"([^"]{2,90})"',blob)
        if not name: continue
        k=(m.group(1),name.group(1))
        if k in seen: continue
        seen.add(k); print(f"  id={m.group(1):>6}  {name.group(1)}")
print("json responses:",len(bodies))
