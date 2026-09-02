#!/usr/bin/env python3
"""Hurtigruten port-to-port availability, straight off the JSON API.

Found by driving the form once: POST /nellie-coastal-v2/api/availability with a
plain JSON body. No signature, no quote id needed for the search step.

Usage: python3 hrg_api.py
"""
import json
import pathlib

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
API = "https://www.hurtigruten.com/nellie-coastal-v2/api/availability"
WARM = "https://www.hurtigruten.com/en-us/port-to-port"
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)

CAB = {"adults": 2, "children": 0, "infants": 0, "companions": 0, "students": 0,
       "seniors": 0, "militaryServicePersons": 0, "wheelchairs": 0, "pets": 0}


def body(from_port, to_port, d_from, d_to, cabins=2, deck=None):
    b = {"searchInterval": "day", "locale": "en-us", "automaticPromotionCode": None,
         "promotionCode": None, "fromDate": d_from, "toDate": d_to,
         "isReturnTrip": False, "isViaKirkenes": False,
         "fromPort": from_port, "toPort": to_port,
         "deckspaces": deck,
         "cabins": None if deck else [dict(CAB) for _ in range(cabins)],
         "vehicles": {"cars": 0, "motorcycles": 0}, "requestType": "voyage"}
    return b


JOBS = [
    # (slug, from, to, week-from ISO Z, week-to ISO Z, cabins, deckspaces)
    ("svj-tos-w0928", "SVJ", "TOS", "2026-09-27T22:00:00.000Z", "2026-10-03T22:00:00.000Z", 2, None),
    ("svj-tos-w1005", "SVJ", "TOS", "2026-10-04T22:00:00.000Z", "2026-10-10T22:00:00.000Z", 2, None),
    ("svj-tos-deck-w0928", "SVJ", "TOS", "2026-09-27T22:00:00.000Z", "2026-10-03T22:00:00.000Z",
     0, {"adults": 4, "children": 0, "infants": 0, "companions": 0, "students": 0,
         "seniors": 0, "militaryServicePersons": 0, "wheelchairs": 0, "pets": 0}),
    ("svj-tos-1cab4ad", "SVJ", "TOS", "2026-09-27T22:00:00.000Z", "2026-10-03T22:00:00.000Z", 1, None),
    # fallback: leave from Stamsund / Bodo? and the day-before option
    ("svj-tos-w0921", "SVJ", "TOS", "2026-09-20T22:00:00.000Z", "2026-09-26T22:00:00.000Z", 2, None),
]

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US")
    pg = ctx.new_page()
    pg.goto(WARM, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(6000)
    summary = []
    for slug, fr, to, d1, d2, ncab, deck in JOBS:
        b = body(fr, to, d1, d2, ncab, deck)
        if ncab == 1:
            b["cabins"] = [dict(CAB, adults=4)]
        r = pg.request.post(API, data=json.dumps(b),
                            headers={"content-type": "application/json",
                                     "accept": "application/json"})
        try:
            js = r.json()
        except Exception:
            js = {"_raw": r.text()[:2000]}
        (out / f"api-{slug}.json").write_text(
            json.dumps({"request": b, "status": r.status, "response": js},
                       ensure_ascii=False, indent=1))
        print(f"== {slug} status={r.status}")
        if isinstance(js, list):
            for v in js:
                cats = ", ".join(
                    f"{c['cabinCategory']}=${c['price']}"
                    for c in v.get("categoryPrices", []) if c.get("isAvailable"))
                print(f"   {v.get('departureDateTime')} {v.get('shipName')} "
                      f"from ${v.get('price')} {v.get('currency')} | {cats or 'NONE AVAILABLE'}")
                summary.append({"slug": slug, "dep": v.get("departureDateTime"),
                                "ship": v.get("shipName"), "from": v.get("price"),
                                "cats": cats})
        else:
            print("   ", json.dumps(js, ensure_ascii=False)[:600])
    (out / "api-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    br.close()
