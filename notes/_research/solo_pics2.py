#!/usr/bin/env python3
"""solo_pics.py 的第二遍：只补「有页面、没房价」的酒店 + 新增的两家尼斯酒店。

第一遍经 searchresults 跳过去的页面，Lisbon/Nice 大多 0 行房价（伦敦却全有）——
直接用带日期的酒店页再开一次、等更久、滚到 #availability 再读。
Usage: python3 solo_pics2.py <in_out.json>
"""
import json
import re
import sys

from playwright.sync_api import sync_playwright

from solo_pics import UA, DATES, dismiss, hotel

EXTRA = [("nice", "57868", "Hotel Palais de la Mediterranee, in the Unbound Collection by Hyatt"),
         ("nice", None, "Hotel Splendid Nice")]


def rows_on(pg):
    out = []
    trs = pg.locator("#hprt-table tbody tr")
    for i in range(min(trs.count(), 30)):
        try:
            t = trs.nth(i).inner_text(timeout=3000)
        except Exception:
            continue
        out.append(" ¶ ".join(x.strip() for x in t.split("\n") if x.strip())[:600])
    return out


def main():
    path = sys.argv[1]
    res = json.load(open(path))
    res["hotels"] = [h for h in res["hotels"] if h.get("url")]      # 丢掉 Okko / Hyatt 两条空的
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
        for city, did, q in EXTRA:
            try:
                h = hotel(ctx, city, q) if not did else None
            except Exception as e:
                h = {"err": str(e)}
            if did:
                import solo_pics
                orig = solo_pics.dest_id
                solo_pics.dest_id = lambda _q, d=did, l=q: (d, l)
                h = hotel(ctx, city, q)
                solo_pics.dest_id = orig
            print("EXTRA", q, h.get("url"), len(h.get("rows", [])), flush=True)
            if h.get("url"):
                res["hotels"].append(h)
        for h in res["hotels"]:
            if h.get("rows"):
                continue
            pg = ctx.new_page()
            pg.goto(h["book_url"] + "&lang=en-us&group_children=0", wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(9000)
            dismiss(pg)
            try:
                pg.locator("#availability, #hprt-table").first.scroll_into_view_if_needed(timeout=5000)
            except Exception:
                pass
            pg.wait_for_timeout(4000)
            h["rows"] = rows_on(pg)
            if not h["rows"]:
                body = pg.inner_text("body")
                m = re.search(r".{0,200}(no availability|sold out|not available|There are no available)[^\n]{0,200}", body, re.I)
                h["note"] = m.group(0) if m else body[:0]
            print("P2", h["q"], len(h["rows"]), h.get("note", "")[:120], flush=True)
            pg.close()
            json.dump(res, open(path, "w"), ensure_ascii=False, indent=1)
        br.close()
    json.dump(res, open(path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
