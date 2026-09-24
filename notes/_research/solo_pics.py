#!/usr/bin/env python3
"""后半段三城：Airbnb 房源 + 直订酒店，一次拿到「实价 + 照片」。

为什么要重写一个而不是复用 bk_prop.py：
上一轮 Nice / Lisbon 的酒店 slug 是猜的，猜错了 Booking 会静默跳回首页（title
变成 "Booking.com Online Hotel Reservations"、rows 为空）。这里先走 Booking 的
autocomplete 拿 dest_id，再用 dest_type=hotel 让它自己跳到正确的酒店页 —— 不猜。

照片用监听网络请求的办法拿（同 bk_img_fix.py）：Booking 的图片 URL 带签名 ?k=，
从 HTML 里抠常常是缩略图；Airbnb 取房源页里 muscache 的 pictures 图。

Usage: python3 solo_pics.py <out.json>
"""
import json
import re
import sys

import requests
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
DATES = {"nice": ("2026-10-06", "2026-10-10"), "lis": ("2026-10-10", "2026-10-14"),
         "lon": ("2026-10-14", "2026-10-18")}

HOTELS = [
    ("nice", "Okko Hotels Nice Centre"),
    ("nice", "Hotel Aston La Scala Nice"),
    ("nice", "Hyatt Regency Nice Palais de la Mediterranee"),
    ("nice", "Hotel Le Negresco Nice"),
    ("lis", "Hotel Mundial Lisboa"),
    ("lis", "Martinhal Lisbon Chiado"),
    ("lis", "Heritage Avenida Liberdade"),
    ("lis", "Memmo Principe Real"),
    ("lon", "Native Hyde Park"),
    ("lon", "Hilton London Paddington"),
    ("lon", "Novotel London Paddington"),
    ("lon", "Inhabit Queen's Gardens"),
]
ABNB = [
    ("nice", "1443297416255023788"), ("nice", "1755951383141506994"),
    ("nice", "48658006"), ("nice", "13017164"),
    ("lis", "13292214"), ("lis", "18047870"), ("lis", "34102943"),
    ("lon", "1281197209882921388"), ("lon", "1620969860892941249"),
    ("lon", "1670183614080025358"),
]


def dest_id(q):
    r = requests.post("https://accommodations.booking.com/autocomplete.json",
                      json={"query": q, "language": "en-us", "size": 5},
                      headers={"User-Agent": UA, "Origin": "https://www.booking.com"}, timeout=20)
    for x in r.json().get("results", []):
        if x.get("dest_type") == "hotel":
            return x["dest_id"], x.get("label")
    return None, None


def dismiss(pg):
    for s in ['#onetrust-accept-btn-handler', 'button[aria-label="Dismiss sign-in info."]',
              'button[aria-label="Close"]', 'button:has-text("Accept")']:
        try:
            pg.locator(s).first.click(timeout=1200)
        except Exception:
            pass


def hotel(ctx, city, q):
    did, label = dest_id(q)
    if not did:
        return {"city": city, "q": q, "err": "autocomplete 没找到酒店"}
    ci, co = DATES[city]
    hits = []
    pg = ctx.new_page()
    pg.on("request", lambda r: hits.append(r.url)
          if "bstatic.com/xdata/images/hotel" in r.url else None)
    url = (f"https://www.booking.com/searchresults.html?dest_id={did}&dest_type=hotel"
           f"&checkin={ci}&checkout={co}&group_adults=1&no_rooms=1&group_children=0"
           f"&selected_currency=EUR&lang=en-us")
    pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(6000)
    dismiss(pg)
    # 有时停在只有一张卡的结果页 → 点进去
    if "/hotel/" not in pg.url:
        try:
            href = pg.locator('a[data-testid="title-link"]').first.get_attribute("href", timeout=5000)
            pg.goto(href, wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(6000)
            dismiss(pg)
        except Exception:
            pass
    final = pg.url
    title = pg.title()
    rows = []
    trs = pg.locator("#hprt-table tbody tr")
    for i in range(min(trs.count(), 30)):
        try:
            t = trs.nth(i).inner_text(timeout=3000)
        except Exception:
            continue
        flat = " ¶ ".join(x.strip() for x in t.split("\n") if x.strip())
        rows.append(flat[:600])
    for _ in range(4):
        pg.mouse.wheel(0, 1600)
        pg.wait_for_timeout(700)
    imgs = []
    for u in hits:
        base = u.split("?")[0]
        if re.search(r"/(max1024x768|max1280x900|1024x768|max500)/", u) and base not in [x.split("?")[0] for x in imgs]:
            imgs.append(u)
    # 大图优先
    imgs.sort(key=lambda u: 0 if "1024" in u or "1280" in u else 1)
    try:
        score = pg.locator('[data-testid="review-score-component"]').first.inner_text(timeout=2000)
    except Exception:
        score = ""
    try:
        addr = pg.locator('[data-testid="PropertyHeaderAddressDesktop-wrapper"], .hp_address_subtitle').first.inner_text(timeout=2000)
    except Exception:
        addr = ""
    pg.close()
    clean = final.split("?")[0]
    return {"city": city, "q": q, "label": label, "dest_id": did, "url": clean,
            "book_url": f"{clean}?checkin={ci}&checkout={co}&group_adults=1&no_rooms=1&selected_currency=EUR",
            "title": title, "score": score, "addr": addr, "rows": rows, "imgs": imgs[:6]}


def airbnb(ctx, city, room):
    ci, co = DATES[city]
    pg = ctx.new_page()
    url = (f"https://www.airbnb.com/rooms/{room}?check_in={ci}&check_out={co}"
           f"&adults=1&currency=EUR&locale=en")
    pg.goto(url, wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(10000)
    dismiss(pg)
    imgs = pg.eval_on_selector_all(
        'img', "els=>els.map(e=>e.currentSrc||e.src).filter(s=>/muscache\\.com\\/im\\/pictures/.test(s))")
    og = pg.eval_on_selector_all('meta[property="og:image"]', "els=>els.map(e=>e.content)")
    seen, out = set(), []
    for u in og + imgs:
        k = u.split("?")[0]
        if k not in seen and "/user/" not in u and "Portrait" not in u:
            seen.add(k)
            out.append(k + "?im_w=1200")
    body = re.sub(r"[ \t]+", " ", pg.inner_text("body"))
    title = pg.title()
    tot = re.search(r"Total(?: before taxes)?\s*\n?\s*€\s?([\d,]+)", body)
    per4 = re.search(r"€\s?([\d,]+)\s*(?:\n\s*)?for 4 nights", body)
    wifi = re.findall(r"(?:Fast wifi[^\n]*|Wifi[^\n]{0,40}Mbps[^\n]*|\bWifi\b)", body)
    desk = bool(re.search(r"Dedicated workspace", body))
    lift = bool(re.search(r"\bElevator\b", body))
    unavailable = bool(re.search(r"Those dates are not available|dates are unavailable", body, re.I))
    pg.close()
    return {"city": city, "room": room, "title": title,
            "total_eur": int((tot or per4).group(1).replace(",", "")) if (tot or per4) else None,
            "wifi": sorted(set(wifi))[:3], "workspace": desk, "elevator": lift,
            "unavailable": unavailable, "imgs": out[:6]}


def main():
    res = {"hotels": [], "airbnb": []}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
        for city, q in HOTELS:
            try:
                r = hotel(ctx, city, q)
            except Exception as e:
                r = {"city": city, "q": q, "err": str(e)[:200]}
            print("H", q, "->", r.get("url"), len(r.get("rows", [])), "rows", len(r.get("imgs", [])), "imgs", flush=True)
            res["hotels"].append(r)
            json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
        for city, room in ABNB:
            try:
                r = airbnb(ctx, city, room)
            except Exception as e:
                r = {"city": city, "room": room, "err": str(e)[:200]}
            print("A", room, r.get("total_eur"), len(r.get("imgs", [])), "imgs", r.get("workspace"), r.get("wifi"), flush=True)
            res["airbnb"].append(r)
            json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
        br.close()


if __name__ == "__main__":
    main()
