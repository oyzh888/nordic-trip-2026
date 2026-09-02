#!/usr/bin/env python3
"""DiscoverCars live quotes via Playwright form driving (react-date-range calendar).

Usage: python3 dc_cars.py <jobs.json> <out_dir>
job: {"slug","pickup","dropoff"?,"pick_date":"2026-09-26","drop_date":"2026-09-29",
      "pick_month_idx":0,"drop_month_idx":0}   # 0 = Sep 2026 pane, 1 = Oct 2026 pane
"""
import json, re, sys, pathlib
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def pick_loc(pg, name, text):
    box = pg.locator(f'input[name="{name}"]').first
    box.click(force=True)
    box.fill("")
    box.type(text, delay=140)
    pg.wait_for_timeout(3500)
    pg.locator('.Autocomplete-AutocompleteItem').first.click(timeout=8000)
    pg.wait_for_timeout(1200)
    return box.input_value()


def click_day(pg, month_idx, day):
    """Click day `day` inside the month pane `month_idx` (0-based) of react-date-range."""
    months = pg.locator('.rdrMonth')
    pane = months.nth(month_idx)
    days = pane.locator('.rdrDay:not(.rdrDayPassive):not(.rdrDayDisabled)')
    for i in range(days.count()):
        d = days.nth(i)
        try:
            if d.locator('.rdrDayNumber span').first.inner_text(timeout=800).strip() == str(day):
                d.click(timeout=4000)
                pg.wait_for_timeout(900)
                return True
        except Exception:
            continue
    return False


def scrape(pg, j):
    log = {}
    pg.goto("https://www.discovercars.com/", wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(5000)

    log["pickup"] = pick_loc(pg, "PickupLocation", j["pickup"])
    if j.get("dropoff"):
        for sel in ['input[type=checkbox][name*="IsSameLocation" i]',
                    'text="Return car in same location"']:
            try:
                pg.locator(sel).first.click(timeout=3000, force=True)
                pg.wait_for_timeout(1500)
                break
            except Exception:
                pass
        try:
            log["dropoff"] = pick_loc(pg, "DropoffLocation", j["dropoff"])
        except Exception as e:
            log["dropoff_err"] = str(e)[:100]

    pg.locator('[class*="datepicker" i]').first.click(timeout=8000)
    pg.wait_for_timeout(2500)
    pd = int(j["pick_date"][-2:]); dd = int(j["drop_date"][-2:])
    log["pick_click"] = click_day(pg, j.get("pick_month_idx", 0), pd)
    log["drop_click"] = click_day(pg, j.get("drop_month_idx", 0), dd)
    body = pg.inner_text("body")
    m = re.search(r"Pick-up date\s*\n(.+?)\n.*?Drop-off date\s*\n(.+?)\n", body, re.S)
    log["dates_shown"] = m.groups() if m else None

    for sel in ['button:has-text("Search")', 'button[type=submit]', 'input[type=submit]']:
        try:
            pg.locator(sel).first.click(timeout=4000)
            break
        except Exception:
            pass
    pg.wait_for_timeout(20000)
    for _ in range(5):
        pg.mouse.wheel(0, 3500); pg.wait_for_timeout(1600)
    log["url_after"] = pg.url

    rows = []
    cards = pg.locator('[class*="car-item"], [class*="CarItem"], [class*="offer" i]')
    log["n_cards"] = cards.count()
    for i in range(min(cards.count(), 40)):
        try:
            t = cards.nth(i).inner_text(timeout=4000)
        except Exception:
            continue
        flat = " | ".join(dict.fromkeys(x.strip() for x in t.split("\n") if x.strip()))
        if len(flat) < 30:
            continue
        price = re.findall(r"[€$£]\s?([\d,]+)", flat)
        rows.append({
            "head": flat.split(" | ")[0][:70],
            "prices": [int(p.replace(",", "")) for p in price][:5],
            "supplier": (re.search(r"(Blue Car|Blue Rental|Go Car|Lava Car|Lotus Car|Hertz|Avis|Sixt|"
                                   r"Europcar|Budget|Enterprise|Green Motion|Thrifty|Alamo|Dollar|"
                                   r"Reykjavik Cars|Geysir|Fara|Autounion|Nordic|Rent a Car)", flat)
                         or [None, None])[1],
            "raw": flat[:420],
        })
    return {"log": log, "rows": rows, "body": pg.inner_text("body")[:1200]}


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                             viewport={"width": 1600, "height": 1200})
        for j in jobs:
            pg = ctx.new_page()
            try:
                res = scrape(pg, j)
            except Exception as e:
                res = {"error": f"{type(e).__name__}: {e}"[:300]}
            res["job"] = j
            (out / f"{j['slug']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
            lg = res.get("log", {})
            print(f"{j['slug']}: {len(res.get('rows',[]))} cards | dates={lg.get('dates_shown')} "
                  f"| {str(lg.get('url_after'))[:110]} {res.get('error','')[:80]}")
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
