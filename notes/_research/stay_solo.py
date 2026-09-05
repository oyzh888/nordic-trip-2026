#!/usr/bin/env python3
"""Steve 单人段住宿实价：Booking 搜索结果的「每晚均价」。

和 bk_scrape.py 的区别：1 adult（那个默认 4）+ 不要求卫浴数 + 直接读卡片文本，
不依赖 [data-testid=property-card]（2026-09-05 实测该 selector 在这几个查询上返回 0）。

Usage: python3 stay_solo.py jobs_solostay.json out_solostay
"""
import json, pathlib, re, sys
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JOBS = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1500, "height": 1800})
    for j in JOBS:
        q = {"ss": j["ss"], "checkin": j["checkin"], "checkout": j["checkout"],
             "group_adults": 1, "group_children": 0, "no_rooms": 1,
             "selected_currency": "EUR", "lang": "en-us", "order": "price"}
        url = "https://www.booking.com/searchresults.html?" + urlencode(q)
        pg = ctx.new_page(); rec = {"slug": j["slug"], "url": url, "job": j}
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(6000)
            for sel in ('#onetrust-accept-btn-handler',
                        'button[aria-label*="Dismiss"]', 'button:has-text("Accept")'):
                try: pg.locator(sel).first.click(timeout=2500); pg.wait_for_timeout(600)
                except Exception: pass
            for _ in range(4):
                pg.mouse.wheel(0, 4000); pg.wait_for_timeout(1200)
            cards = pg.locator('div[data-testid="property-card"], div[role="listitem"]')
            rows = []
            for i in range(min(cards.count(), 25)):
                t = re.sub(r"\s+", " ", cards.nth(i).inner_text(timeout=3000)).strip()
                if "€" in t and 40 < len(t) < 900:
                    rows.append(t)
            rec["n_cards"] = cards.count(); rec["rows"] = rows
            pg.screenshot(path=str(out / f"{j['slug']}.png"), full_page=False)
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        (out / f"{j['slug']}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        print(f"== {j['slug']} cards={rec.get('n_cards')} rows={len(rec.get('rows',[]))} {rec.get('error','')}", flush=True)
        for r in rec.get("rows", [])[:6]: print("   ", r[:220], flush=True)
        pg.close()
    br.close()
print("DONE")
