#!/usr/bin/env python3
"""Scrape Booking.com property pages for live room availability/prices.

Usage: python3 bk_prop.py <jobs.json> <out_dir>
job: {"slug","hotel":"no/svinoya-rorbuer","checkin","checkout","adults":4,"rooms":1}
"""
import json
import re
import sys
import pathlib

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def url_for(j):
    return (f"https://www.booking.com/hotel/{j['hotel']}.html"
            f"?checkin={j['checkin']}&checkout={j['checkout']}"
            f"&group_adults={j.get('adults', 4)}&group_children=0"
            f"&no_rooms={j.get('rooms', 1)}&selected_currency=EUR&lang=en-us")


def scrape(pg, j):
    pg.goto(url_for(j), wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(7000)
    title = pg.title()
    rows = pg.locator("#hprt-table tbody tr")
    out, cur = [], None
    for i in range(rows.count()):
        try:
            t = rows.nth(i).inner_text(timeout=4000)
        except Exception:
            continue
        flat = " ¶ ".join(x.strip() for x in t.split("\n") if x.strip())
        name = flat.split(" ¶ ")[0]
        beds = len(re.findall(r"Bedroom \d+:", flat))
        baths = re.search(r"(\d+)\s+bathroom", flat, re.I)
        price = re.findall(r"[€$]\s?([\d,]+)", flat)
        cancel = re.search(r"(Free cancellation before [^¶]+|Non-refundable)", flat)
        entry = {
            "row": i,
            "name": name if beds or "Recommended" in flat or "left" in flat else None,
            "bedrooms": beds or None,
            "bathrooms": int(baths.group(1)) if baths else None,
            "prices_seen": [int(p.replace(",", "")) for p in price][:4],
            "cancel": cancel.group(1) if cancel else None,
            "currency": "EUR" if "€" in flat else ("USD" if "$" in flat else None),
            "raw": flat[:520],
        }
        out.append(entry)
    # top-of-page fallback (sold out / no availability messages)
    body = pg.inner_text("body")[:4000]
    soldout = bool(re.search(r"no rooms available|sold out|not available for your dates", body, re.I))
    return {"title": title, "url": url_for(j), "sold_out": soldout, "rows": out}


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                            viewport={"width": 1600, "height": 1100})
        for j in jobs:
            pg = ctx.new_page()
            try:
                res = scrape(pg, j)
            except Exception as e:  # noqa: BLE001
                res = {"error": f"{type(e).__name__}: {e}", "url": url_for(j)}
            res["job"] = j
            (out / f"{j['slug']}.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=1))
            print(f"{j['slug']}: {len(res.get('rows', []))} rows"
                  f"{' SOLD-OUT' if res.get('sold_out') else ''}"
                  f"{' ERR' if res.get('error') else ''}")
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
