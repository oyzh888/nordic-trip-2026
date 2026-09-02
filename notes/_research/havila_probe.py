#!/usr/bin/env python3
"""Find Havila's port-to-port booking engine (their /en/booking is CF-403 from here)."""
import json
import pathlib
import re

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("hav-nb-p2p", "https://www.havilavoyages.com/nb/havn-til-havn"),
    ("hav-nb-rute", "https://www.havilavoyages.com/nb/ruteplan"),
    ("hav-en-home", "https://www.havilavoyages.com/en"),
]

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="nb-NO",
                         viewport={"width": 1600, "height": 1200})
    for slug, url in PAGES:
        pg = ctx.new_page()
        rec = {"url": url}
        api = []
        pg.on("response", lambda r: api.append(
            {"m": r.request.method, "u": r.url[:400], "s": r.status})
            if r.request.resource_type in ("xhr", "fetch") else None)
        try:
            resp = pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
            rec["status"] = resp.status if resp else None
            pg.wait_for_timeout(9000)
            rec["all_links"] = sorted(set(
                l for l in pg.eval_on_selector_all(
                    "a", "els=>els.map(e=>e.getAttribute('href')||'')") if l))[:400]
            rec["booking_links"] = [l for l in rec["all_links"]
                                    if re.search(r"bestill|book|søk|sok|reserv", l, re.I)]
            rec["buttons"] = pg.eval_on_selector_all(
                "button,[role=button]",
                "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,80)")
            rec["testids"] = pg.eval_on_selector_all(
                "[data-testid],[data-cy],[id]",
                "els=>Array.from(new Set(els.map(e=>e.getAttribute('data-testid')||"
                "e.getAttribute('data-cy')||e.id))).filter(Boolean).slice(0,120)")
            rec["body"] = pg.inner_text("body")[:4000]
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        rec["api"] = api[:60]
        (out / f"{slug}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        print(f"== {slug} status={rec.get('status')} {rec.get('error','')}")
        print("  booking_links:", rec.get("booking_links"))
        print("  buttons:", (rec.get("buttons") or [])[:20])
        print("  api hosts:", sorted({re.sub(r'^https?://([^/]+).*', r'\1', a['u'])
                                      for a in api})[:20])
        pg.close()
    br.close()
