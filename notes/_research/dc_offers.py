#!/usr/bin/env python3
"""抓一条 DiscoverCars 链接上的**全部**报价，带车名。

和前面几个脚本的区别（2026-09-06 按 Steve 的意见改的）：
**不再盲等固定秒数，改成轮询条件。** 旧写法 `wait_for_timeout(26000)` 有两个毛病：
① 慢的时候不够、快的时候白等；② 等不够会**静默**拿到部分报价，长得跟「这个市场没货」
一模一样（就是这么一度以为冰岛只有 8 个报价的）。
现在的判据：每 1.5 秒数一次报价条数，**连续 3 次不再增长**就认为加载完，最多等 45 秒。

Usage: python3 dc_offers.py <out.json> <label>=<url> [<label>=<url> ...]
"""
import json, re, sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# 一条报价的文本长这样：
#   Toyota RAV4 | or similar Standard SUV | Automatic | 5 seats | 5 doors | ...
#   ... | In terminal pick-up — Tromso Airport (TOS) | ... | Total for 3 days | $227.45 | Free cancellation
ROW = re.compile(
    r"([A-Z][A-Za-z0-9\.\-/ ]{1,30}?) \| or similar ([A-Za-z\- ]+?) \| (Manual|Automatic) \| "
    r"(\d+) seats \| (\d+) doors(.*?)Total for (\d+) days? \| \$\s?([\d,]+(?:\.\d+)?)", re.S)


def harvest(pg):
    flat = " | ".join(x.strip() for x in pg.inner_text("body").split("\n") if x.strip())
    out = {}
    for m in ROW.finditer(flat):
        car, klass, gear, seats, doors, mid, days, price = m.groups()
        pk = re.search(r"(In terminal|Free shuttle service|Shuttle bus|Meet (?:and|&) greet)", mid)
        out[(car.strip(), klass.strip(), gear, float(price.replace(",", "")))] = dict(
            car=car.strip(), klass=klass.strip(), gear=gear, seats=int(seats), doors=int(doors),
            pickup=pk.group(1) if pk else None, days=int(days),
            price=float(price.replace(",", "")),
            aircon="Air Conditioning" in mid, free_cancel="Free cancellation" in mid,
            unlimited="Unlimited mileage" in mid, deposit_free="No deposit" in mid)
    return out


def scrape(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=120_000)
    seen, flat_last, stable, waited = {}, -1, 0, 0
    while waited < 45 and stable < 3:                 # ← 轮询，不盲等
        pg.wait_for_timeout(1500); waited += 1.5
        seen.update(harvest(pg))
        stable = stable + 1 if len(seen) == flat_last else 0
        flat_last = len(seen)
    for _ in range(12):                               # 虚拟列表：滚出后面的行
        pg.mouse.wheel(0, 2600); pg.wait_for_timeout(900); seen.update(harvest(pg))
    return {"url": url, "n": len(seen), "waited_s": waited,
            "offers": sorted(seen.values(), key=lambda o: (o["klass"], o["price"]))}


res = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(user_agent=UA, viewport={"width": 1440, "height": 1200})
    for arg in sys.argv[2:]:
        label, url = arg.split("=", 1)
        res[label] = scrape(pg, url)
        print(f"== {label}: {res[label]['n']} offers（加载等了 {res[label]['waited_s']:.0f}s）")
        for o in res[label]["offers"]:
            print(f"   ${o['price']:>7.2f} {o['days']}d | {o['klass']:<28} | {o['gear']:<9} | "
                  f"{o['seats']}座{o['doors']}门 | {o['pickup']} | {o['car']}"
                  + ("" if o["free_cancel"] else "  ⚠️不可免费取消"))
        sys.stdout.flush()
    b.close()
json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print("→", sys.argv[1])
