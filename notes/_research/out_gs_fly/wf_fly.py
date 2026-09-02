#!/usr/bin/env python3
"""Try to read live Wideroe fares SVJ->TOS 2026-10-02 for 4 adults."""
import json, pathlib, re
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
out=pathlib.Path("out_wf"); out.mkdir(exist_ok=True)
URLS=[
 ("wf-deep","https://www.wideroe.no/en/booking/select?tripType=OW&origin=SVJ&destination=TOS&departureDate=2026-10-02&adults=4"),
 ("wf-home","https://www.wideroe.no/en"),
 ("wf-timetable","https://www.wideroe.no/en/travel-information/timetable"),
]
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    ctx=br.new_context(user_agent=UA, locale="en-US", viewport={"width":1500,"height":1300})
    for slug,u in URLS:
        pg=ctx.new_page(); rec={"url":u}
        try:
            pg.goto(u, wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(9000)
            for sel in ('button:has-text("Accept")','button:has-text("Godta")','#onetrust-accept-btn-handler'):
                try: pg.locator(sel).first.click(timeout=2500); break
                except Exception: pass
            pg.wait_for_timeout(7000)
            rec["title"]=pg.title(); rec["body"]=pg.inner_text("body")[:9000]
            pg.screenshot(path=str(out/f"{slug}.png"), full_page=True)
        except Exception as e:
            rec["error"]=f"{type(e).__name__}: {e}"[:200]
        (out/f"{slug}.json").write_text(json.dumps(rec,ensure_ascii=False,indent=1))
        print("==",slug,rec.get("title"),rec.get("error",""))
        print((rec.get("body") or "")[:900].replace("\n"," | ")[:900])
        pg.close()
    br.close()
