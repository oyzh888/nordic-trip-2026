#!/usr/bin/env python3
"""从住宿详情页抓真实照片 CDN 链接（不下载图片，只要 URL —— 页面直接引用 CDN）。

Airbnb  → a0.muscache.com/im/pictures/...
Booking → cf.bstatic.com/xdata/images/hotel/...
Usage: python3 img_scrape.py <jobs.json> <out.json>
job: {"slug","url","name"}
"""
import json, re, sys, pathlib, collections
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

AIRBNB = re.compile(r"https://a0\.muscache\.com/im/pictures/[A-Za-z0-9/_\-\.%]+?\.(?:jpe?g|png|webp)", re.I)
BSTATIC = re.compile(r"https://cf\.bstatic\.com/xdata/images/hotel/[A-Za-z0-9/_\-\.%]+?\.(?:jpe?g|png|webp)", re.I)

def norm_airbnb(u):
    """把缩略图尺寸参数统一提到大图。"""
    u = re.sub(r"\?.*$", "", u)
    return u + "?im_w=1200"

def norm_bstatic(u):
    # .../hotel/max1024x768/xxx.jpg  → 统一到 max1280x900
    return re.sub(r"/xdata/images/hotel/[^/]+/", "/xdata/images/hotel/max1280x900/", u)

def scrape(pg, job):
    pg.goto(job["url"], wait_until="domcontentloaded", timeout=90_000)
    pg.wait_for_timeout(6500)
    for sel in ['button[aria-label="Close"]', '#onetrust-accept-btn-handler',
                'button:has-text("Accept")', '[aria-label="Dismiss"]']:
        try: pg.locator(sel).first.click(timeout=1200)
        except Exception: pass
    # 往下滚，把懒加载的图逼出来
    for _ in range(6):
        pg.mouse.wheel(0, 2200); pg.wait_for_timeout(900)
    html = pg.content()
    og = None
    try:
        og = pg.locator('meta[property="og:image"]').first.get_attribute("content", timeout=2000)
    except Exception: pass
    title = None
    try: title = pg.title()
    except Exception: pass

    if "airbnb" in job["url"]:
        raw = AIRBNB.findall(html)
        # 过滤掉头像/图标类（user、profile、avatar）
        raw = [u for u in raw if not re.search(r"(user|profile|avatar|airbnb-platform-assets)", u, re.I)]
        seen, urls = set(), []
        for u in raw:
            n = norm_airbnb(u)
            key = re.sub(r"\?.*$", "", n)
            if key in seen: continue
            seen.add(key); urls.append(n)
    else:
        raw = BSTATIC.findall(html)
        raw = [u for u in raw if "square" not in u.lower()]
        seen, urls = set(), []
        for u in raw:
            n = norm_bstatic(u)
            if n in seen: continue
            seen.add(n); urls.append(n)
    return {"slug": job["slug"], "name": job.get("name"), "url": job["url"],
            "page_title": (title or "")[:160], "og_image": og,
            "n": len(urls), "images": urls[:40]}

def main():
    jobs = json.load(open(sys.argv[1]))
    out = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                             viewport={"width": 1500, "height": 1200})
        for j in jobs:
            pg = ctx.new_page()
            try:
                r = scrape(pg, j)
            except Exception as e:
                r = {"slug": j["slug"], "url": j["url"], "error": f"{type(e).__name__}: {e}"[:200], "images": []}
            out.append(r)
            print(f"{j['slug']:<14} {r.get('n', 0):>3} imgs  {r.get('error','')[:60]}", flush=True)
            pg.close()
        br.close()
    pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print("total images:", sum(len(r.get("images", [])) for r in out))

if __name__ == "__main__":
    main()
