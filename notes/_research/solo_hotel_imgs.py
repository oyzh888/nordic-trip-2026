#!/usr/bin/env python3
"""给订票页每家酒店补 3 张图（城市搜索卡片只给 1 张封面，Hotel Indigo 那张还是灰色占位图）。
和 bk_img_fix.py 同一个办法：监听网络请求拿带签名的 bstatic 大图。
Usage: python3 solo_hotel_imgs.py <out.json> <hotel_url>...
"""
import json, re, sys
from playwright.sync_api import sync_playwright
from solo_pics import UA, dismiss
out = {}
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
    for url in sys.argv[2:]:
        hits = []
        pg = ctx.new_page()
        pg.on("request", lambda r: hits.append(r.url) if "bstatic.com/xdata/images/hotel" in r.url else None)
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(6000)
            dismiss(pg)
            for _ in range(3):
                pg.mouse.wheel(0, 1200); pg.wait_for_timeout(600)
        except Exception as e:
            print("ERR", url, e)
        seen, imgs = set(), []
        for u in hits:
            m = re.search(r"/(\d+)\.jpg", u)
            if not m or m.group(1) in seen:
                continue
            if re.search(r"/(max1024x768|max1280x900|max500|max300)/", u):
                seen.add(m.group(1))
                imgs.append(re.sub(r"/(max500|max300)/", "/max1024x768/", u) if "k=" not in u else u)
        out[url] = imgs[:4]
        print(url.split("/")[-1], len(imgs), flush=True)
        pg.close()
    br.close()
json.dump(out, open(sys.argv[1], "w"), indent=1)
