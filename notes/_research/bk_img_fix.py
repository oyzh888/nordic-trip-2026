#!/usr/bin/env python3
"""靠监听网络请求拿 Booking 的真实图片 URL（带签名 ?k=），比抓 HTML 稳。"""
import json,re,pathlib
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JOBS=[("d2-horgsland","https://www.booking.com/hotel/is/horgsland-cottages.html"),
      ("d3-birkifell","https://www.booking.com/hotel/is/guesthouse-birkifell.html"),
      ("alt-arnanes","https://www.booking.com/hotel/is/arnanes-sveitagisting.html")]
SMALL=re.compile(r"/(square\d+|max150|max200|max300|max400|max500)/")
out={}
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    ctx=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1500,"height":1200})
    for slug,url in JOBS:
        hits=[]
        pg=ctx.new_page()
        pg.on("request",lambda r:hits.append(r.url) if "bstatic.com/xdata/images/hotel" in r.url else None)
        try:
            pg.goto(url,wait_until="domcontentloaded",timeout=90000); pg.wait_for_timeout(6000)
            for s in ['#onetrust-accept-btn-handler','button:has-text("Accept")','[aria-label="Dismiss"]']:
                try: pg.locator(s).first.click(timeout=1200)
                except Exception: pass
            for _ in range(8): pg.mouse.wheel(0,2000); pg.wait_for_timeout(950)
            # 试着点开图库，逼它加载大图
            for s in ['[data-testid="gallery-image"]','button:has-text("photos")',
                      'a[href*="#gallery"]','.bh-photo-grid-thumb-more','.bh-photo-grid-item']:
                try: pg.locator(s).first.click(timeout=1500); pg.wait_for_timeout(3200); break
                except Exception: pass
            for _ in range(10):
                try: pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(650)
                except Exception: break
        except Exception as e:
            print(slug,"nav ERR",str(e)[:70])
        seen,urls=set(),[]
        for u in hits:
            if "?k=" not in u or SMALL.search(u): continue
            key=re.search(r"/(\d{6,})\.(?:jpe?g|webp|png)",u)
            key=key.group(1) if key else u
            if key in seen: continue
            seen.add(key); urls.append(u)
        out[slug]={"url":url,"n_req":len(hits),"n":len(urls),"images":urls[:16]}
        print(f"{slug:<14} 请求 {len(hits):>4} 个 → 可用 {len(urls):>3} 张",flush=True)
        pg.close()
    br.close()
pathlib.Path("out_img_bk.json").write_text(json.dumps(out,ensure_ascii=False,indent=1))
