#!/usr/bin/env python3
"""找「有意思的房子」：每城在市中心 bbox 里翻 N 页 Airbnb 搜索，拿全候选。

口径变更（Steve 2026-09-24）：**不用担心吵** → 老城（Vieux Nice / Alfama / Bairro Alto）
重新放回来；要的是**有意思 + 各方面平衡**（位置、能工作、评分、价格、房子本身有没有性格）。
所以这一步只负责「拿全」—— 单页只有 18 张卡，翻到第 N 页；筛选和打分在 abnb_rank.py 里做。

Usage: python3 abnb_interest.py <out.json> [pages]
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

from abnb_scrape import UA, parse_card

CITIES = {
    # (checkin, checkout, bbox sw_lat, sw_lng, ne_lat, ne_lng, zoom)
    "nice": ("2026-10-06", "2026-10-10", (43.690, 7.250, 43.708, 7.290), 15),   # 海滨大道 ↔ 老港，含老城
    # 🆕 9/25 方案 C：尼斯 → 伦敦 10/10–10/13 → 里斯本 10/13–10/17（周六里斯本直飞回）
    "lis":  ("2026-10-13", "2026-10-17", (38.704, -9.160, 38.723, -9.122), 15), # Príncipe Real ↔ Graça，含 Alfama
    "lon":  ("2026-10-10", "2026-10-13",   # 方案 C：伦敦挪到前面，正好是周末
             (51.503, -0.215, 51.530, -0.150), 14), # Notting Hill ↔ Marylebone，含 Little Venice
}


def url_for(city):
    ci, co, (a, b, c, d), z = CITIES[city]
    return (f"https://www.airbnb.com/s/homes?checkin={ci}&checkout={co}&adults=1"
            f"&room_types%5B%5D=Entire%20home%2Fapt&currency=EUR&locale=en"
            f"&sw_lat={a}&sw_lng={b}&ne_lat={c}&ne_lng={d}&search_by_map=true&zoom={z}")


def main():
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    res = {}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1600, "height": 1100})
        only = sys.argv[3].split(",") if len(sys.argv) > 3 else list(CITIES)
        for city in only:
            pg = ctx.new_page()
            rows, seen = [], set()
            pg.goto(url_for(city), wait_until="domcontentloaded", timeout=90_000)
            for n in range(pages):
                pg.wait_for_timeout(8000)
                cards = pg.locator('[data-testid="card-container"]')
                for i in range(cards.count()):
                    try:
                        r = parse_card(cards.nth(i).inner_text(timeout=4000))
                        href = cards.nth(i).locator("a").first.get_attribute("href") or ""
                    except Exception:
                        continue
                    m = re.search(r"/rooms/(\d+)", href)
                    if not m or m.group(1) in seen:
                        continue
                    seen.add(m.group(1))
                    rv = re.search(r"out of 5 average rating,\s*([\d,]+) review", r["raw"])
                    r.update(room=m.group(1), page=n, reviews=int(rv.group(1).replace(",", "")) if rv else 0,
                             guest_fav="Guest favorite" in r["raw"])
                    rows.append(r)
                print(city, "page", n, "total", len(rows), flush=True)
                try:
                    pg.locator('a[aria-label="Next"]').first.click(timeout=5000)
                except Exception:
                    break
            res[city] = {"url": url_for(city), "rows": rows}
            json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
