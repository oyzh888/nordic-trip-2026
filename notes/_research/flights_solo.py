#!/usr/bin/env python3
"""Steve 一个人的分手后段：10/6 从奥斯陆分开 → 法国南部 / 伦敦 → 回湾区。

和 flights_*.py 的区别只有两个，但都要紧：
  1) **1 adult**（其余脚本全写死 4 adults，价格是 4 人总价 —— 直接抄会差 4 倍）
  2) **USD**（他用美国卡买，且要和 SFO/SJC 直接比）

Usage: python3 flights_solo.py [jobs_solo.json] [out_solo]
"""
import json
import pathlib
import re
import sys
import urllib.parse

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

jobs_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "jobs_solo.json")
out = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "out_solo")
out.mkdir(parents=True, exist_ok=True)
JOBS = json.loads(jobs_path.read_text(encoding="utf-8"))


def url_for(fr, to, d):
    q = f"one-way flights from {fr} to {to} on {d} for 1 adult"
    return ("https://www.google.com/travel/flights?hl=en&curr=USD&q="
            + urllib.parse.quote(q))


with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1500, "height": 1600})
    summary = {}
    for j in JOBS:
        slug, fr, to, d = j["slug"], j["from"], j["to"], j["date"]
        pg = ctx.new_page()
        rec = {"slug": slug, "from": fr, "to": to, "date": d, "pax": 1,
               "curr": "USD", "note": j.get("note", ""), "url": url_for(fr, to, d)}
        try:
            pg.goto(rec["url"], wait_until="domcontentloaded", timeout=90_000)
            pg.wait_for_timeout(3000)
            for sel in ('button:has-text("Accept all")',
                        'button:has-text("Reject all")'):
                try:
                    pg.locator(sel).first.click(timeout=3000)
                    break
                except Exception:
                    pass
            pg.wait_for_timeout(14000)
            rec["body"] = pg.inner_text("body")[:20000]
            rows = pg.locator("li").filter(has_text=re.compile(r"\$"))
            offers = []
            for i in range(min(rows.count(), 30)):
                t = re.sub(r"\s+", " ", rows.nth(i).inner_text(timeout=3000)).strip()
                if 30 < len(t) < 500 and re.search(r"\$\d", t):
                    offers.append(t)
            rec["offers"] = offers
            pg.screenshot(path=str(out / f"{slug}.png"), full_page=True)
        except Exception as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        (out / f"{slug}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=1))
        summary[slug] = rec.get("offers", [])[:10]
        print(f"== {slug}  {fr}->{to} {d}  {rec.get('error','')}", flush=True)
        for o in rec.get("offers", [])[:8]:
            print("   ", o[:230], flush=True)
        pg.close()
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1))
    br.close()
print("DONE")
