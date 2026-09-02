#!/usr/bin/env python3
"""Probe Hurtigruten /en-us/port-to-port booking widget: form fields + XHR endpoints."""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.hurtigruten.com/en-us/port-to-port"
slug = sys.argv[2] if len(sys.argv) > 2 else "hrg-p2p-book"
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1100})
    pg = ctx.new_page()
    xhr = []

    def on_resp(r):
        if r.request.resource_type not in ("xhr", "fetch"):
            return
        item = {"m": r.request.method, "u": r.url[:500], "s": r.status}
        try:
            if "json" in (r.headers.get("content-type") or ""):
                item["body"] = r.text()[:3000]
        except Exception:
            pass
        try:
            if r.request.post_data:
                item["post"] = r.request.post_data[:1500]
        except Exception:
            pass
        xhr.append(item)

    pg.on("response", on_resp)
    rec = {"url": URL}
    try:
        resp = pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        rec["status"] = resp.status if resp else None
        pg.wait_for_timeout(12000)
        rec["title"] = pg.title()
        rec["body"] = pg.inner_text("body")[:8000]
        rec["selects"] = pg.eval_on_selector_all(
            "select", "els => els.map(e => ({name:e.name, id:e.id, "
            "opts: Array.from(e.options).slice(0,80).map(o=>o.value+'|'+o.text)}))")
        rec["inputs"] = pg.eval_on_selector_all(
            "input", "els => els.map(e => ({name:e.name, id:e.id, ph:e.placeholder, "
            "type:e.type, val:e.value}))")
        rec["combos"] = pg.eval_on_selector_all(
            "[role=combobox],[data-testid]", "els => els.map(e => ({tag:e.tagName, "
            "tid:e.getAttribute('data-testid'), role:e.getAttribute('role')})).slice(0,150)")
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["xhr"] = xhr[:120]
    (out / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print(f"status={rec.get('status')} xhr={len(xhr)} err={rec.get('error','')}")
    print((rec.get("body") or "")[:2500])
    for x in xhr:
        print(x["s"], x["m"], x["u"][:200])
    br.close()
