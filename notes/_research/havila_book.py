#!/usr/bin/env python3
"""Click Havila's 'Bestill havn-til-havn' and see where the booking engine lives."""
import json
import pathlib
import re

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
URL = "https://www.havilavoyages.com/nb/havn-til-havn"
out = pathlib.Path("out_cruise")
SKIP = ("hubapi", "hubspot", "clarity", "cookieinformation", "stackadapt",
        "google-analytics", "sentry", "puzzel", "hscollectedforms", "cdn-cgi")

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="nb-NO",
                         viewport={"width": 1600, "height": 1300})
    pg = ctx.new_page()
    api = []

    def on_resp(r):
        if r.request.resource_type not in ("xhr", "fetch") or any(b in r.url for b in SKIP):
            return
        it = {"m": r.request.method, "u": r.url[:600], "s": r.status}
        try:
            it["body"] = r.text()[:12000]
        except Exception:
            pass
        try:
            if r.request.post_data:
                it["post"] = r.request.post_data[:2000]
        except Exception:
            pass
        api.append(it)

    ctx.on("response", on_resp)
    rec = {}
    try:
        pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        pg.wait_for_timeout(8000)
        for sel in ('button:has-text("OK")', 'button:has-text("Godta")'):
            try:
                pg.locator(sel).first.click(timeout=2500)
                pg.wait_for_timeout(1200)
                break
            except Exception:
                pass
        pages_before = len(ctx.pages)
        pg.locator('button:has-text("Bestill havn-til-havn"), '
                   'a:has-text("Bestill havn-til-havn")').first.click(timeout=8000)
        pg.wait_for_timeout(15000)
        tgt = ctx.pages[-1] if len(ctx.pages) > pages_before else pg
        rec["url"] = tgt.url
        rec["title"] = tgt.title()
        rec["body"] = tgt.inner_text("body")[:8000]
        rec["inputs"] = tgt.eval_on_selector_all(
            "input", "els=>els.map(e=>({ph:e.placeholder,type:e.type,val:e.value,"
            "name:e.name,id:e.id}))")
        rec["selects"] = tgt.eval_on_selector_all(
            "select", "els=>els.map(e=>({name:e.name,id:e.id,"
            "opts:Array.from(e.options).slice(0,80).map(o=>o.value+'|'+o.text)}))")
        rec["testids"] = tgt.eval_on_selector_all(
            "[data-testid]", "els=>Array.from(new Set(els.map(e=>e.getAttribute('data-testid'))))")
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        try:
            rec["url"] = pg.url
            rec["body"] = pg.inner_text("body")[:8000]
        except Exception:
            pass
    rec["api"] = api[:60]
    (out / "hav-book.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print("url:", rec.get("url"), "| err:", rec.get("error", ""))
    print("testids:", json.dumps(rec.get("testids", []), ensure_ascii=False)[:1200])
    print("selects:", json.dumps(rec.get("selects", []), ensure_ascii=False)[:2000])
    print("inputs:", json.dumps(rec.get("inputs", []), ensure_ascii=False)[:1500])
    for a in api:
        print(a["s"], a["m"], a["u"][:200])
    print("--- BODY ---")
    print((rec.get("body") or "")[:4000])
    br.close()
