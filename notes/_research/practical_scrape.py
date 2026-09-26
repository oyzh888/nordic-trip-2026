#!/usr/bin/env python3
"""实用页的「在哪 / 几点能进」：已订住宿的地址、坐标、入住/退房时间。

来源：
  Booking 房源页 —— 页头的完整地址 + a[data-atlas-latlng] 精确坐标 + 「House rules」里的 check-in/out
  Airbnb 房源页 —— 只有**街区级**位置（精确门牌号只在订单 / App 里，下单后才给）+ 模糊坐标 +
                  「House rules」里的入住/退房时间
所以页面上 Airbnb 那几处一律写「精确地址看订单」，不许把模糊坐标当门牌号用。

Usage: python3 practical_scrape.py <out.json>
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

BOOKING = {
    "radisson-osl": "https://www.booking.com/hotel/no/radisson-blu-airport-oslo.html?checkin=2026-09-29&checkout=2026-09-30&group_adults=2&lang=en-us",
    "horgsland": "https://www.booking.com/hotel/is/horgsland-cottages.html?checkin=2026-09-26&checkout=2026-09-27&group_adults=4&lang=en-us",
    "birkifell": "https://www.booking.com/hotel/is/guesthouse-birkifell.html?checkin=2026-09-27&checkout=2026-09-28&group_adults=4&lang=en-us",
}
AIRBNB = {
    "rvk": "1729852848905770040", "njardvik": "1139944377459145061", "lyngvaer": "1303545546783105490",
    "tromso": "825162133059470411", "konglehytta": "648419631702172808",
}


def dismiss(pg):
    for s in ('#onetrust-accept-btn-handler', 'button[aria-label="Dismiss sign-in info."]',
              'button[aria-label="Close"]', 'button:has-text("OK")'):
        try:
            pg.locator(s).first.click(timeout=1200)
        except Exception:
            pass


def booking(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(7000)
    dismiss(pg)
    addr = ""
    for sel in ('[data-testid="PropertyHeaderAddressDesktop-wrapper"]', '.hp_address_subtitle',
                '[data-node_tt_id="location_score_tooltip"]'):
        try:
            addr = pg.locator(sel).first.inner_text(timeout=2500).strip()
            if addr:
                break
        except Exception:
            pass
    ll = None
    try:
        v = pg.locator("[data-atlas-latlng]").first.get_attribute("data-atlas-latlng", timeout=3000)
        ll = [float(x) for x in v.split(",")]
    except Exception:
        m = re.search(r'"latitude"\s*:\s*"?(-?\d+\.\d+)"?\s*,\s*"longitude"\s*:\s*"?(-?\d+\.\d+)', pg.content())
        if m:
            ll = [float(m.group(1)), float(m.group(2))]
    for _ in range(8):
        pg.mouse.wheel(0, 1600)
        pg.wait_for_timeout(500)
    body = re.sub(r"[ \t]+", " ", pg.inner_text("body"))
    ci = re.search(r"Check-in\s*\n+\s*((?:From|Available)[^\n]{0,60}|\d{1,2}:\d{2}[^\n]{0,40})", body)
    co = re.search(r"Check-out\s*\n+\s*((?:Until|From|Available)[^\n]{0,60}|\d{1,2}:\d{2}[^\n]{0,40})", body)
    return {"addr": re.sub(r"\s+", " ", addr).split(" – ")[0].split("Excellent location")[0].strip(),
            "ll": ll, "checkin": ci.group(1).strip() if ci else None,
            "checkout": co.group(1).strip() if co else None, "title": pg.title().split(" (")[0]}


def airbnb(pg, room):
    pg.goto(f"https://www.airbnb.com/rooms/{room}?locale=en&currency=EUR", wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(9000)
    dismiss(pg)
    for _ in range(10):
        pg.mouse.wheel(0, 1500)
        pg.wait_for_timeout(600)
    html = pg.content()
    body = re.sub(r"[ \t]+", " ", pg.inner_text("body"))
    lat = re.search(r'"lat(?:itude)?":\s*(-?\d+\.\d+)', html)
    lng = re.search(r'"(?:lng|longitude)":\s*(-?\d+\.\d+)', html)
    where = re.search(r"Where you['’]ll be\s*\n+\s*([^\n]{3,80})", body)
    ci = re.search(r"(Check-in (?:after|:|from)[^\n]{0,40}|Check-in: [^\n]{0,40}|Self check-in[^\n]{0,60})", body)
    co = re.search(r"(Checkout before[^\n]{0,20}|Check-out before[^\n]{0,20})", body)
    selfci = re.search(r"(Self check-in[^\n]{0,80}|Check yourself in with the [^\n]{0,40})", body)
    return {"where": where.group(1).strip() if where else None,
            "ll": [float(lat.group(1)), float(lng.group(1))] if lat and lng else None,
            "checkin": ci.group(1).strip() if ci else None, "checkout": co.group(1).strip() if co else None,
            "selfcheckin": selfci.group(1).strip() if selfci else None, "title": pg.title().split(" - ")[0]}


def main():
    res = {}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
        for k, u in BOOKING.items():
            pg = ctx.new_page()
            try:
                res[k] = {"src": "booking", "url": u.split("?")[0], **booking(pg, u)}
            except Exception as e:
                res[k] = {"err": str(e)[:200]}
            print(k, json.dumps(res[k], ensure_ascii=False)[:300], flush=True)
            pg.close()
        for k, r in AIRBNB.items():
            pg = ctx.new_page()
            try:
                res[k] = {"src": "airbnb", "url": f"https://www.airbnb.com/rooms/{r}", **airbnb(pg, r)}
            except Exception as e:
                res[k] = {"err": str(e)[:200]}
            print(k, json.dumps(res[k], ensure_ascii=False)[:300], flush=True)
            pg.close()
        br.close()
    json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
