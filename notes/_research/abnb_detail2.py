#!/usr/bin/env python3
"""Airbnb 房源页逐个打开：照片 + 能不能工作 + 位置坐标 + 房东自己的描述。

为什么要坐标：Steve 问「它们的特点是什么 —— 是靠近好玩的地方，还是住宿环境好」。
「靠近」必须是个数，不能是房东写的 "5 min to everything"。拿到 lat/lng 后，
abnb_rank.py 会算到这座城里每个锚点（逐日表里那几个）的步行距离。
Airbnb 页面上的坐标是**模糊过的**（几十到一两百米的随机偏移），所以距离按「约」报。

Usage: python3 abnb_detail2.py <in_interest.json> <out.json> <city> [min_rating]
三个城市分三个进程并行跑（各自一个浏览器），互不干扰。
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

from abnb_scrape import UA
from abnb_interest import CITIES


def price(raw):
    head = raw.split("Show price breakdown")[0]
    p = [int(x.replace(",", "")) for x in re.findall(r"€([\d,]+)", head)]
    return p[-1] if p else None


def grab(ctx, city, room):
    ci, co = CITIES[city][0], CITIES[city][1]
    pg = ctx.new_page()
    pg.goto(f"https://www.airbnb.com/rooms/{room}?check_in={ci}&check_out={co}&adults=1&currency=EUR&locale=en",
            wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(9000)
    for sel in ('button[aria-label="Close"]', 'button:has-text("OK")'):
        try:
            pg.locator(sel).first.click(timeout=1500)
        except Exception:
            pass
    html = pg.content()
    body = re.sub(r"[ \t]+", " ", pg.inner_text("body"))
    imgs = pg.eval_on_selector_all(
        "img", "els=>els.map(e=>e.currentSrc||e.src).filter(s=>/muscache\\.com\\/im\\/pictures/.test(s))")
    seen, photos = set(), []
    for u in imgs:
        k = u.split("?")[0]
        if k not in seen and "platform-assets" not in u and "/user/" not in u:
            seen.add(k)
            photos.append(k + "?im_w=960")
    lat = re.search(r'"lat(?:itude)?":\s*(-?\d+\.\d+)', html)
    lng = re.search(r'"(?:lng|longitude)":\s*(-?\d+\.\d+)', html)
    # 描述：「About this space」那块；拿不到就用页面前段
    desc = ""
    m = re.search(r"About this (?:space|place)\s*\n(.{0,1200})", body, re.S)
    if m:
        desc = m.group(1)
    else:
        try:
            desc = pg.locator('[data-section-id="DESCRIPTION_DEFAULT"]').first.inner_text(timeout=2000)[:1200]
        except Exception:
            pass
    revs = re.search(r"([\d,]+) reviews", body)
    floor = re.search(r"(\d+)(?:st|nd|rd|th) floor", body, re.I)
    out = {
        "city": city, "room": room, "title": pg.title().split(" - ")[0],
        "lat": float(lat.group(1)) if lat else None, "lng": float(lng.group(1)) if lng else None,
        "reviews": int(revs.group(1).replace(",", "")) if revs else None,
        "workspace": "Dedicated workspace" in body,
        "wifi_mbps": (re.search(r"(\d+) Mbps", body) or [None, None])[1],
        "elevator": bool(re.search(r"\bElevator\b", body)),
        "ac": bool(re.search(r"Air conditioning|Central air", body)),
        "washer": bool(re.search(r"\bWasher\b", body)),
        "kitchen": bool(re.search(r"\bKitchen\b", body)),
        "view": re.findall(r"(Sea view|Ocean view|City skyline view|River view|Garden view|Park view|Harbor view|Mountain view|Courtyard view)", body)[:3],
        "floor": floor.group(0) if floor else None,
        "stairs_note": bool(re.search(r"no elevator|without (?:an )?elevator|stairs only|walk-up", body, re.I)),
        "superhost": "Superhost" in body,
        "desc": re.sub(r"\s+", " ", desc)[:1000],
        "photos": photos[:6],
        "unavailable": bool(re.search(r"Those dates are not available", body)),
    }
    pg.close()
    return out


def main():
    src, dst, city = sys.argv[1], sys.argv[2], sys.argv[3]
    minr = float(sys.argv[4]) if len(sys.argv) > 4 else 4.8
    rows = json.load(open(src))[city]["rows"]
    cand = []
    for r in rows:
        r["total_eur"] = price(r["raw"])
        try:
            ok = float(r["rating"]) >= minr
        except (TypeError, ValueError):
            ok = False
        if ok and r["total_eur"]:
            cand.append(r)
    res = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
        for r in cand:
            try:
                d = grab(ctx, city, r["room"])
            except Exception as e:
                d = {"city": city, "room": r["room"], "err": str(e)[:160]}
            d.update(search_title=r["title"], total_eur=r["total_eur"], rating=r["rating"], guest_fav=r["guest_fav"])
            res.append(d)
            print(city, r["room"], d.get("lat"), d.get("reviews"), d.get("wifi_mbps"), d.get("workspace"), len(d.get("photos", [])), flush=True)
            json.dump(res, open(dst, "w"), ensure_ascii=False, indent=1)
        br.close()


if __name__ == "__main__":
    main()
