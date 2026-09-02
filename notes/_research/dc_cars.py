#!/usr/bin/env python3
"""DiscoverCars live quotes by driving the search form with Playwright.

Usage: python3 dc_cars.py <jobs.json> <out_dir>
job: {"slug","pickup","dropoff"(optional),"pick_date":"2026-09-26","pick_time":"10:00",
      "drop_date":"2026-09-29","drop_time":"20:00"}
"""
import json, re, sys, pathlib
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def pick_suggestion(pg, box_sel, text):
    box = pg.locator(box_sel).first
    box.click()
    box.fill("")
    box.type(text, delay=110)
    pg.wait_for_timeout(2500)
    for sel in ['.autocomplete-item', '[class*="suggest"] li', 'ul[role="listbox"] li',
                '.ui-menu-item', '[class*="dropdown"] [class*="item"]']:
        loc = pg.locator(sel)
        if loc.count():
            try:
                loc.first.click(timeout=3000)
                pg.wait_for_timeout(600)
                return sel
            except Exception:
                pass
    box.press("Enter")
    return None


def scrape(pg, j):
    pg.goto("https://www.discovercars.com/", wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(4000)
    for sel in ['#onetrust-accept-btn-handler', 'button:has-text("Accept")',
                'button:has-text("Agree")', '[aria-label*="close" i]']:
        try:
            pg.locator(sel).first.click(timeout=2000); pg.wait_for_timeout(500)
        except Exception:
            pass

    log = {}
    log["pick_sugg"] = pick_suggestion(pg, '#PickupLocation, input[name="PickupLocation"]', j["pickup"])

    if j.get("dropoff"):
        for sel in ['input[type=checkbox][name*="IsSameLocation" i]',
                    'label:has-text("Return car to a different location")',
                    'input#different-location']:
            try:
                pg.locator(sel).first.click(timeout=2500); pg.wait_for_timeout(1200); break
            except Exception:
                pass
        try:
            log["drop_sugg"] = pick_suggestion(
                pg, '#DropoffLocation, input[name="DropoffLocation"]', j["dropoff"])
        except Exception as e:
            log["drop_err"] = str(e)[:120]

    # date inputs: the unnamed text inputs in the search form
    texts = pg.locator('form input[type="text"]')
    log["n_text_inputs"] = texts.count()
    filled = []
    for i in range(texts.count()):
        el = texts.nth(i)
        try:
            nm = el.get_attribute("name") or el.get_attribute("id") or f"#{i}"
        except Exception:
            continue
        filled.append(nm)
    log["text_inputs"] = filled

    # try calendar-driven date selection
    for label, date in (("pick", j["pick_date"]), ("drop", j["drop_date"])):
        for sel in [f'[data-date="{date}"]', f'td[data-value="{date}"]',
                    f'[aria-label*="{date}"]']:
            try:
                pg.locator(sel).first.click(timeout=2500); pg.wait_for_timeout(700)
                log[f"{label}_date_click"] = sel
                break
            except Exception:
                pass

    for sel in ['button[type=submit]', 'form button:has-text("Search")',
                'input[type=submit]', 'a:has-text("Search")']:
        try:
            pg.locator(sel).first.click(timeout=3000); break
        except Exception:
            pass
    pg.wait_for_timeout(15000)
    for _ in range(4):
        pg.mouse.wheel(0, 3000); pg.wait_for_timeout(1500)

    log["url_after"] = pg.url
    cards = pg.locator('[class*="car-item"], [data-testid*="offer"], .cars-box')
    log["n_cards"] = cards.count()
    rows = []
    for i in range(min(cards.count(), 30)):
        try:
            t = cards.nth(i).inner_text(timeout=4000)
        except Exception:
            continue
        flat = " | ".join(dict.fromkeys(x.strip() for x in t.split("\n") if x.strip()))
        price = re.findall(r"[€$]\s?([\d,]+)", flat)
        rows.append({
            "name": flat.split(" | ")[0][:70],
            "prices": [int(p.replace(",", "")) for p in price][:4],
            "supplier": (re.search(r"(Blue Car|Go Car|Lava|Lotus|Hertz|Avis|Sixt|Europcar|Budget|Enterprise|Green Motion|Thrifty|Alamo|Fireflay|Dollar)", flat) or [None, None])[1],
            "raw": flat[:400],
        })
    return {"log": log, "rows": rows, "body": pg.inner_text("body")[:1500]}


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                             viewport={"width": 1600, "height": 1100})
        for j in jobs:
            pg = ctx.new_page()
            try:
                res = scrape(pg, j)
            except Exception as e:
                res = {"error": f"{type(e).__name__}: {e}"}
            res["job"] = j
            (out / f"{j['slug']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
            print(f"{j['slug']}: {len(res.get('rows',[]))} cards  log={res.get('log',{}).get('url_after','')[:110]}")
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
