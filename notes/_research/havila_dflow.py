#!/usr/bin/env python3
"""Havila's real booking engine: prod.havilavoyages.com/touchhvl/?inJson=<json>

Found by clicking 'Bestill havn-til-havn' — it opens a D-FLOW engine on a
different host. The wrapper page is Cloudflare-blocked from this pod, so go
straight at the engine.

Usage: python3 havila_dflow.py <month> <year> <slug>
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
SLUG = sys.argv[3] if len(sys.argv) > 3 else f"hav-dflow-{YEAR}{MONTH:02d}"
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)

inj = {"caller": "D-FLOW", "adults": 4, "children": 0, "locale": "en",
       "month": MONTH, "year": YEAR, "productTypes": "NORWEGIAN COAST"}
URL = ("https://prod.havilavoyages.com/touchhvl/?inJson="
       + urllib.parse.quote(json.dumps(inj), safe=""))

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-GB",
                         viewport={"width": 1600, "height": 1400})
    pg = ctx.new_page()
    api = []

    def on_resp(r):
        if r.request.resource_type not in ("xhr", "fetch"):
            return
        if re.search(r"google|doubleclick|hubspot|clarity|collect\.", r.url):
            return
        it = {"m": r.request.method, "u": r.url[:500], "s": r.status}
        try:
            it["body"] = r.text()[:30000]
        except Exception:
            pass
        try:
            if r.request.post_data:
                it["post"] = r.request.post_data[:3000]
        except Exception:
            pass
        api.append(it)

    ctx.on("response", on_resp)
    rec = {"url": URL, "inJson": inj}
    try:
        resp = pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        rec["status"] = resp.status if resp else None
        pg.wait_for_timeout(15000)
        rec["final_url"] = pg.url
        rec["title"] = pg.title()
        rec["body"] = pg.inner_text("body")[:20000]
        rec["selects"] = pg.eval_on_selector_all(
            "select", "els=>els.map(e=>({name:e.name,id:e.id,"
            "opts:Array.from(e.options).slice(0,120).map(o=>o.value+'|'+o.text)}))")
        rec["inputs"] = pg.eval_on_selector_all(
            "input", "els=>els.map(e=>({ph:e.placeholder,type:e.type,val:e.value,name:e.name,id:e.id}))")
        rec["buttons"] = pg.eval_on_selector_all(
            "button,[role=button],a.btn",
            "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,100)")
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        try:
            rec["body"] = pg.inner_text("body")[:8000]
        except Exception:
            pass
    rec["api"] = api[:80]
    (out / f"{SLUG}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print("status:", rec.get("status"), "| err:", rec.get("error", ""))
    print("final_url:", rec.get("final_url"))
    print("selects:", json.dumps(rec.get("selects", []), ensure_ascii=False)[:3000])
    print("inputs:", json.dumps(rec.get("inputs", []), ensure_ascii=False)[:1500])
    print("buttons:", json.dumps(rec.get("buttons", []), ensure_ascii=False)[:1200])
    for a in api[:40]:
        print(a["s"], a["m"], a["u"][:200])
    print("----- BODY -----")
    print((rec.get("body") or "")[:6000])
    br.close()
