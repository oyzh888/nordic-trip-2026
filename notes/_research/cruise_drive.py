#!/usr/bin/env python3
"""Drive Hurtigruten port-to-port: pick Svolvaer -> Tromso, capture result URL + API calls."""
import json
import pathlib

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
URL = "https://www.hurtigruten.com/en-us/port-to-port"
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)

INTERESTING = ("availab", "sail", "voyage", "search", "price", "cabin", "port", "quote",
               "booking", "graphql", "api")


def pick(pg, dd_testid, text, log):
    box = pg.locator(f'[data-testid="{dd_testid}"]')
    inp = box.locator("input").first
    inp.click()
    pg.wait_for_timeout(600)
    inp.fill("")
    inp.type(text, delay=110)
    pg.wait_for_timeout(2200)
    opts = box.locator('li, [role="option"], [data-testid*="option"]')
    n = opts.count()
    labels = []
    for i in range(min(n, 20)):
        try:
            labels.append(opts.nth(i).inner_text(timeout=800).strip())
        except Exception:
            labels.append("")
    log.append({"dd": dd_testid, "typed": text, "options": labels})
    for i, lab in enumerate(labels):
        if text.split("æ")[0].lower()[:4] in lab.lower():
            opts.nth(i).click()
            pg.wait_for_timeout(1500)
            return lab
    if n:
        opts.first.click()
        pg.wait_for_timeout(1500)
        return labels[0]
    return None


with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1200})
    pg = ctx.new_page()
    api = []

    def on_resp(r):
        if r.request.resource_type not in ("xhr", "fetch"):
            return
        u = r.url
        if not any(k in u.lower() for k in INTERESTING):
            return
        if any(bad in u for bad in ("doubleclick", "google", "clarity", "cookielaw",
                                    "salesforce", "infinity-tracking", "onetrust",
                                    "visualwebsiteoptimizer", "bing", "cdn-cgi")):
            return
        item = {"m": r.request.method, "u": u[:600], "s": r.status}
        try:
            item["body"] = r.text()[:6000]
        except Exception:
            pass
        try:
            if r.request.post_data:
                item["post"] = r.request.post_data[:2000]
        except Exception:
            pass
        api.append(item)

    pg.on("response", on_resp)
    rec = {}
    log = []
    try:
        pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        pg.wait_for_timeout(9000)
        # dismiss cookie banner if present
        for sel in ('#onetrust-accept-btn-handler', 'button:has-text("Accept")'):
            try:
                pg.locator(sel).first.click(timeout=2500)
                pg.wait_for_timeout(1200)
                break
            except Exception:
                pass
        rec["from_picked"] = pick(pg, "from-port-dropdown", "Svolvær", log)
        rec["to_picked"] = pick(pg, "to-port-dropdown", "Tromsø", log)
        pg.wait_for_timeout(2500)
        rec["url_after_pick"] = pg.url
        # try a submit/search button
        for sel in ('button:has-text("Search")', 'button:has-text("Find")',
                    'button:has-text("Show")', '[data-testid*="search"] button',
                    'button[type="submit"]'):
            try:
                pg.locator(sel).first.click(timeout=3000)
                rec["clicked"] = sel
                pg.wait_for_timeout(9000)
                break
            except Exception:
                continue
        rec["final_url"] = pg.url
        rec["body"] = pg.inner_text("body")[:9000]
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
    rec["dropdown_log"] = log
    rec["api"] = api[:60]
    (out / "hrg-drive.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print("from:", rec.get("from_picked"), "| to:", rec.get("to_picked"))
    print("clicked:", rec.get("clicked"), "| final:", rec.get("final_url"))
    print("err:", rec.get("error", ""))
    for l in log:
        print("DD", l["dd"], l["typed"], "->", l["options"][:8])
    for a in api:
        print(a["s"], a["m"], a["u"][:220])
    print("----- BODY -----")
    print((rec.get("body") or "")[:3000])
    br.close()
