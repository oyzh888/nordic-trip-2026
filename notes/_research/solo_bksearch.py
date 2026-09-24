#!/usr/bin/env python3
"""Booking 城市搜索页：给定日期，按「评分高 + 位置好」列出**真有房**的酒店（价 + 图 + 分）。

为什么需要：solo_pics2.py 实测 Lisbon 四家点名的酒店（Mundial / Martinhal / Heritage /
Memmo）和 Nice 的 Aston / Hyatt 在我们的日期**全都没房** —— 点名选酒店这条路走不通，
要从「那几天还有什么」反过来挑。
搜索页 9/5 用 requests 抓是 HTTP 202（反爬），这里用真浏览器开。

Usage: python3 solo_bksearch.py <out.json>
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

from solo_pics import UA, dismiss

# dest_id 来自 autocomplete：district 比 city 更能把位置钉住
JOBS = [
    # ht_id 204 = 酒店，201 = 公寓（Booking 上的整套公寓，含公寓式酒店）
    ("nice", "-1454990", "city", "2026-10-06", "2026-10-10", "ht_id%3D204"),
    ("lis", "-2167973", "city", "2026-10-10", "2026-10-14", "ht_id%3D204"),
    ("lon", "43", "district", "2026-10-14", "2026-10-17", "ht_id%3D204"),   # 43 = Paddington,
]


def run(ctx, city, did, typ, ci, co, flt):
    pg = ctx.new_page()
    url = (f"https://www.booking.com/searchresults.html?dest_id={did}&dest_type={typ}"
           f"&checkin={ci}&checkout={co}&group_adults=1&no_rooms=1&group_children=0"
           f"&selected_currency=EUR&lang=en-us&nflt={flt}")
    pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(8000)
    dismiss(pg)
    for _ in range(3):                       # 一页 15 张，点「Load more」再要两页
        for _ in range(8):
            pg.mouse.wheel(0, 1800)
            pg.wait_for_timeout(700)
        try:
            pg.locator('button:has-text("Load more results")').first.click(timeout=3000)
            pg.wait_for_timeout(3500)
        except Exception:
            pass
    cards = pg.locator('[data-testid="property-card"]')
    out = []
    for i in range(min(cards.count(), 40)):
        c = cards.nth(i)
        try:
            t = c.inner_text(timeout=3000)
            name = c.locator('[data-testid="title"]').first.inner_text(timeout=2000)
            href = c.locator('a[data-testid="title-link"]').first.get_attribute("href", timeout=2000)
            img = c.locator('img').first.get_attribute("src", timeout=2000)
        except Exception:
            continue
        flat = " ¶ ".join(x.strip() for x in t.split("\n") if x.strip())
        m = re.search(r"Price €\s?([\d,]+)", flat)
        prices = [int(m.group(1).replace(",", ""))] if m else []
        score = re.search(r"Scored (\d+(?:\.\d+)?)", flat) or re.search(r"\b(\d\.\d|10)\b ¶ (?:Wonderful|Superb|Excellent|Very Good|Exceptional|Fabulous|Good)", flat)
        dist = re.search(r"([\d.]+ (?:km|m|miles|feet)) from (?:center|downtown)", flat)
        out.append({"name": name, "url": href.split("?")[0] if href else None,
                    "price_4n": prices[-1] if prices else None, "score": score.group(1) if score else None,
                    "dist": dist.group(1) if dist else None,
                    "img": re.sub(r"/square\d+/|/max\d+/", "/max1024x768/", img or ""), "raw": flat[:500]})
    body = pg.inner_text("body")
    n = re.search(r"([\d,]+) properties found", body)
    un = re.search(r"(\d+)% of places to stay are unavailable", body)
    pg.close()
    return {"city": city, "url": url, "found": n.group(1) if n else None, "unavail_pct": un.group(1) if un else None, "cards": out}


def main():
    res = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
        for j in JOBS:
            r = run(ctx, *j)
            print(j[0], r["found"], len(r["cards"]), flush=True)
            res.append(r)
            json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
        br.close()


if __name__ == "__main__":
    main()
