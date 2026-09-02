#!/usr/bin/env python3
"""Drive the Wideroe booking widget: SVJ->TOS 2026-10-02, 4 pax."""
import json, pathlib
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
out=pathlib.Path("out_wf"); out.mkdir(exist_ok=True)
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    ctx=br.new_context(user_agent=UA, locale="en-US", viewport={"width":1500,"height":1400})
    pg=ctx.new_page(); log=[]
    def snap(n):
        pg.screenshot(path=str(out/f"form-{n}.png"), full_page=True); log.append(n)
    pg.goto("https://www.wideroe.no/en/travel-information/timetable",
            wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(8000)
    for sel in ('#onetrust-accept-btn-handler','button:has-text("Accept")'):
        try: pg.locator(sel).first.click(timeout=3000); break
        except Exception: pass
    pg.wait_for_timeout(2500); snap("0")
    try: pg.get_by_text("One way", exact=True).first.click(timeout=5000)
    except Exception as e: log.append(f"oneway:{e}"[:80])
    pg.wait_for_timeout(1200)
    def fill(label, code, name):
        for sel in [f'input[placeholder*="{label}"]', f'[aria-label*="{label}"]',
                    f'input[id*="{label.split()[-1].lower()}"]']:
            try:
                el=pg.locator(sel).first; el.click(timeout=4000); el.fill(code, timeout=4000)
                pg.wait_for_timeout(2500)
                pg.get_by_text(name, exact=False).first.click(timeout=4000); return True
            except Exception: continue
        return False
    log.append(f"from={fill('Fly from','SVJ','Svolvær')}")
    pg.wait_for_timeout(1500)
    log.append(f"to={fill('Fly to','TOS','Tromsø')}")
    pg.wait_for_timeout(1500); snap("1")
    body=pg.inner_text("body")[:6000]
    (out/"form.json").write_text(json.dumps({"log":log,"body":body},ensure_ascii=False,indent=1))
    print(log); print(body[:1200].replace("\n"," | "))
    br.close()
