#!/usr/bin/env python3
"""Stage 3: Svolvaer -> Tromso, one-way, 10/02/2026, choose cabin -> follow to booking engine.

Usage: python3 cruise_go.py <date MM/DD/YYYY> <cabin|deck> <slug>
"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
URL = "https://www.hurtigruten.com/en-us/port-to-port"
DATE = sys.argv[1] if len(sys.argv) > 1 else "10/02/2026"
MODE = sys.argv[2] if len(sys.argv) > 2 else "cabin"
SLUG = sys.argv[3] if len(sys.argv) > 3 else f"hrg-{MODE}"
out = pathlib.Path("out_cruise")
SKIP = ("doubleclick", "google", "clarity", "cookielaw", "salesforce", "onetrust",
        "infinity-tracking", "visualwebsiteoptimizer", "bing", "cdn-cgi", "omappapi",
        "facebook", "stackadapt", "sentry")


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
    api = []

    def on_resp(r):
        if r.request.resource_type not in ("xhr", "fetch"):
            return
        if any(b in r.url for b in SKIP):
            return
        it = {"m": r.request.method, "u": r.url[:600], "s": r.status}
        try:
            it["body"] = r.text()[:8000]
        except Exception:
            pass
        try:
            if r.request.post_data:
                it["post"] = r.request.post_data[:2000]
        except Exception:
            pass
        api.append(it)

    ctx.on("response", on_resp)
    rec = {"date_requested": DATE, "mode": MODE}
    try:
        pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        pg.wait_for_timeout(9000)
        try:
            pg.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            pg.wait_for_timeout(1000)
        except Exception:
            pass
        pick(pg, "from-port-dropdown", "Svolvær")
        pick(pg, "to-port-dropdown", "Tromsø")
        pg.wait_for_timeout(2000)
        # one-way
        try:
            pg.locator('input[name="is-round-trip"][value="oneWay"]').check(force=True)
            pg.wait_for_timeout(800)
        except Exception:
            pass
        # date field: the only text input whose value looks like a date
        dfield = pg.locator('input[type="text"]').filter(has_not_text="").nth(0)
        target = None
        inps = pg.locator('input[type="text"]')
        for i in range(inps.count()):
            v = inps.nth(i).input_value()
            if v and "/" in v and len(v) == 10:
                target = inps.nth(i)
                break
        if target is not None:
            target.click()
            pg.wait_for_timeout(600)
            target.fill("")
            target.type(DATE, delay=140)
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(2500)
            rec["date_on_page"] = target.input_value()
        else:
            rec["date_on_page"] = None
        # via Kirkenes = No
        try:
            pg.locator('input[name="is-via-kirkenes"][value="false"]').check(force=True)
            pg.wait_for_timeout(600)
        except Exception:
            pass
        tid = ("cabin-choice-want-cabin" if MODE == "cabin"
               else "cabin-choice-want-deckspace")
        with ctx.expect_page(timeout=15000) as newpg_info:
            pg.locator(f'[data-testid="{tid}"]').click(timeout=8000)
        try:
            pg2 = newpg_info.value
        except Exception:
            pg2 = pg
        pg2.wait_for_timeout(20000)
        rec["result_url"] = pg2.url
        rec["result_title"] = pg2.title()
        rec["result_body"] = pg2.inner_text("body")[:12000]
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        try:
            rec["result_url"] = pg.url
            rec["result_body"] = pg.inner_text("body")[:12000]
        except Exception:
            pass
    rec["api"] = api[:80]
    (out / f"{SLUG}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print("date_on_page:", rec.get("date_on_page"), "| err:", rec.get("error", ""))
    print("result_url:", rec.get("result_url"))
    for a in api[:40]:
        print(a["s"], a["m"], a["u"][:200])
    print("----- BODY -----")
    print((rec.get("result_body") or "")[:5000])
    br.close()
