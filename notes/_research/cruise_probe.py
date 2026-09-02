#!/usr/bin/env python3
"""Probe Hurtigruten / Havila port-to-port booking pages: dump structure + XHRs."""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

URLS = [
    ("hrg-p2p", "https://www.hurtigruten.com/en-us/norwegian-coastal-express/port-to-port"),
    ("hrg-uk-p2p", "https://www.hurtigruten.co.uk/port-to-port/"),
    ("havila-p2p", "https://www.havilavoyages.com/en/port-to-port"),
    ("havila-book", "https://www.havilavoyages.com/en/booking"),
]

out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out_cruise")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1100})
    for slug, url in URLS:
        pg = ctx.new_page()
        xhr = []
        pg.on("request", lambda r: xhr.append({"m": r.method, "u": r.url[:400],
                                               "t": r.resource_type})
              if r.resource_type in ("xhr", "fetch") else None)
        rec = {"slug": slug, "url": url}
        try:
            resp = pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
            rec["status"] = resp.status if resp else None
            rec["final_url"] = pg.url
            pg.wait_for_timeout(9000)
            rec["title"] = pg.title()
            rec["body"] = pg.inner_text("body")[:6000]
            rec["selects"] = pg.eval_on_selector_all(
                "select", "els => els.map(e => ({name:e.name, id:e.id, "
                "opts: Array.from(e.options).slice(0,60).map(o=>o.value+'|'+o.text)}))")
            rec["inputs"] = pg.eval_on_selector_all(
                "input", "els => els.map(e => ({name:e.name, id:e.id, ph:e.placeholder, "
                "type:e.type}))")
            rec["buttons"] = pg.eval_on_selector_all(
                "button", "els => els.map(e => (e.innerText||'').trim()).filter(Boolean).slice(0,60)")
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        rec["xhr"] = xhr[:80]
        (out / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        print(f"{slug}: status={rec.get('status')} xhr={len(xhr)} err={rec.get('error','')}")
        pg.close()
    br.close()
