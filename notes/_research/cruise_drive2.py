#!/usr/bin/env python3
"""Stage 2: after picking ports, dump the expanded form's structure (testids/buttons/inputs)."""
import json
import pathlib

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
URL = "https://www.hurtigruten.com/en-us/port-to-port"
out = pathlib.Path("out_cruise")


def pick(pg, dd, text):
    box = pg.locator(f'[data-testid="{dd}"]')
    inp = box.locator("input").first
    inp.click()
    pg.wait_for_timeout(500)
    inp.type(text, delay=100)
    pg.wait_for_timeout(2200)
    box.locator('li, [role="option"]').first.click()
    pg.wait_for_timeout(1500)


with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1400})
    pg = ctx.new_page()
    rec = {}
    pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(9000)
    try:
        pg.locator("#onetrust-accept-btn-handler").click(timeout=3000)
        pg.wait_for_timeout(1000)
    except Exception:
        pass
    pick(pg, "from-port-dropdown", "Svolvær")
    pick(pg, "to-port-dropdown", "Tromsø")
    pg.wait_for_timeout(2500)
    rec["testids"] = pg.eval_on_selector_all(
        "[data-testid]", "els => Array.from(new Set(els.map(e=>e.getAttribute('data-testid'))))")
    rec["buttons"] = pg.eval_on_selector_all(
        "button, [role=button]", "els => els.map(e=>({t:(e.innerText||'').trim().slice(0,50), "
        "tid:e.getAttribute('data-testid'), cls:(e.className||'').slice(0,80)}))")
    rec["inputs"] = pg.eval_on_selector_all(
        "input", "els => els.map(e=>({ph:e.placeholder, type:e.type, val:e.value, "
        "tid:e.getAttribute('data-testid'), name:e.name}))")
    rec["labels"] = pg.eval_on_selector_all(
        "label", "els => els.map(e=>(e.innerText||'').trim().slice(0,60)).filter(Boolean)")
    (out / "hrg-form2.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print("TESTIDS:", json.dumps(rec["testids"], ensure_ascii=False))
    print("BUTTONS:", json.dumps([b for b in rec["buttons"] if b["t"] or b["tid"]],
                                 ensure_ascii=False)[:3000])
    print("INPUTS:", json.dumps(rec["inputs"], ensure_ascii=False)[:2000])
    print("LABELS:", json.dumps(rec["labels"], ensure_ascii=False)[:1200])
    br.close()
