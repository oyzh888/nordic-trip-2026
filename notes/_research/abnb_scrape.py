#!/usr/bin/env python3
"""Airbnb search scraper: entire homes with >=2 bedrooms and >=2 bathrooms, live prices.

Usage: python3 abnb_scrape.py <jobs.json> <out_dir>
job: {"slug","place","checkin","checkout","adults":4,"min_bedrooms":2,"min_bathrooms":2}
"""
import json
import re
import sys
import pathlib
from urllib.parse import quote

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def url_for(j):
    place = quote(j["place"].replace(" ", "-").replace(",", "-"), safe="-")
    u = (f"https://www.airbnb.com/s/{place}/homes?checkin={j['checkin']}"
         f"&checkout={j['checkout']}&adults={j.get('adults', 4)}"
         f"&min_bedrooms={j.get('min_bedrooms', 2)}"
         f"&min_bathrooms={j.get('min_bathrooms', 2)}"
         f"&room_types%5B%5D=Entire%20home%2Fapt"
         f"&currency=EUR&locale=en")
    if j.get("bbox"):  # sw_lat, sw_lng, ne_lat, ne_lng -> pin the map, ignore place radius
        s_lat, s_lng, n_lat, n_lng = j["bbox"]
        u += (f"&sw_lat={s_lat}&sw_lng={s_lng}&ne_lat={n_lat}&ne_lng={n_lng}"
              f"&search_by_map=true&zoom={j.get('zoom', 9)}")
    return u


def parse_card(txt):
    # collapse the duplicated a11y text Airbnb emits
    flat = " | ".join(dict.fromkeys(x.strip() for x in txt.split("\n") if x.strip()))
    bed = re.search(r"(\d+)\s+bedroom", flat)
    bath = re.search(r"([\d.]+)\s+bath", flat)
    prices = [int(p.replace(",", "")) for p in re.findall(r"€\s?([\d,]+)", flat)]
    nights = re.search(r"for\s+(\d+)\s+night", flat)
    head = flat.split(" | ")
    kind = next((h for h in head if re.match(r"^(Apartment|Home|Condo|Cabin|Guesthouse|Loft|Townhouse|Villa|Cottage|Place|Rental|Tiny home|Bungalow|Chalet)\b", h)), head[0] if head else "")
    title = next((h for h in head if len(h) > 18 and not h.startswith("€") and "bedroom" not in h and "bath" not in h and h != kind), "")
    loc = kind.split(" in ", 1)[1] if " in " in kind else ""
    return {
        "kind": kind,
        "loc": loc,
        "title": title,
        "bedrooms": int(bed.group(1)) if bed else None,
        "baths": float(bath.group(1)) if bath else None,
        "nights": int(nights.group(1)) if nights else None,
        "total_eur": min(prices) if prices else None,
        "rating": (re.search(r"([\d.]+) out of 5", flat) or [None, None])[1],
        "raw": flat[:400],
    }


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                            viewport={"width": 1600, "height": 1100})
        for j in jobs:
            u = url_for(j)
            pg = ctx.new_page()
            rows = []
            try:
                pg.goto(u, wait_until="domcontentloaded", timeout=90_000)
                pg.wait_for_timeout(9000)
                cards = pg.locator('[data-testid="card-container"]')
                for i in range(cards.count()):
                    try:
                        r = parse_card(cards.nth(i).inner_text(timeout=4000))
                    except Exception:
                        continue
                    try:
                        href = cards.nth(i).locator("a").first.get_attribute("href") or ""
                        r["url"] = "https://www.airbnb.com" + href.split("?")[0]
                    except Exception:
                        r["url"] = ""
                    rows.append(r)
            except Exception as e:  # noqa: BLE001
                rows.append({"error": f"{type(e).__name__}: {e}"})
            (out / f"{j['slug']}.json").write_text(
                json.dumps({"job": j, "url": u, "rows": rows}, ensure_ascii=False, indent=1))
            three = sum(1 for r in rows if (r.get("bedrooms") or 0) >= 3)
            print(f"{j['slug']}: {len(rows)} listings, {three} with 3+ bedrooms")
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
