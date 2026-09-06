#!/usr/bin/env python3
"""车顶箱/车顶架：这条路到底能不能走 —— 三个问题，用实测回答。

Q1 冰岛那几个日期，DiscoverCars 上**最大**能租到什么车？（如果只有 Compact SUV，
   那 4 人 4 箱就真的需要车顶箱，而不是"升级车型"就能解决）
Q2 结账流程里到底有没有 "Roof box / Roof rack" 这个可加项？多少钱？
Q3 挪威那两台（EVE 大 SUV / TOS 3 天）是不是同样的问题？

输出 out_roofbox.json —— 每个报价的 车型/车类/挡位/座位/门数/取车方式/价格，
外加点进第一个 deal 后页面上出现的所有 extras 文本。
"""
import json, re, sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

LINKS = {
 "iceland": "https://www.discovercars.com/search/d9de6241-92c4-4473-b06f-7b8f96d58312?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoxNzg3LCJEcm9wT2ZmTG9jYXRpb25JZCI6MTc4NywiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTA5LTI1IDA4OjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0wOS0yOSAxODowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ",
 "tromso":  "https://www.discovercars.com/search/47f360c8-4902-4dbc-8ab8-808d632580e9?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoyMTk1LCJEcm9wT2ZmTG9jYXRpb25JZCI6MjE5NSwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTEwLTAyIDE3OjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wNSAwOTo0NSIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ",
}

CLASSES = ("Mini","Economy","Compact","Intermediate","Standard","Full-size","Fullsize",
           "Premium","Luxury","SUV","Estate","Van","Minivan","Pickup","Wagon","MPV","7 seat")

def parse(flat):
    """把一屏 offers 的纯文本切成一条一条。DiscoverCars 每条以 '| Manual |' 或 '| Automatic |' 为轴。"""
    out = []
    for seg in re.split(r"(?=\b(?:or similar)\b)", flat):
        if "Total for" not in seg: continue
        m = re.search(r"or similar ([A-Za-z\- 0-9]+?) \| (Manual|Automatic) \| (\d+) seats \| (\d+) doors", seg)
        pm = re.search(r"(In terminal|Free shuttle service|Shuttle bus|Meet (?:and|&) greet)", seg)
        pr = re.findall(r"\$\s?([\d,]+(?:\.\d+)?)", seg)
        nm = re.search(r"([A-Z][A-Za-z0-9\.\- ]+?) \| or similar", seg)
        bags = re.search(r"(\d+) (?:large |small )?bags?", seg)
        if not m: continue
        out.append(dict(car=(nm.group(1).strip() if nm else None), klass=m.group(1).strip(),
                        gear=m.group(2), seats=int(m.group(3)), doors=int(m.group(4)),
                        pickup=(pm.group(1) if pm else None),
                        price=min(float(p.replace(",","")) for p in pr) if pr else None,
                        bags=bags.group(0) if bags else None))
    return out

res = {}
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(user_agent=UA, viewport={"width":1440,"height":1200})
    for key, url in LINKS.items():
        pg.goto(url, wait_until="domcontentloaded", timeout=120_000)
        pg.wait_for_timeout(26000)
        # 往下滚，virtuoso 是虚拟列表，不滚就只有前几条
        seen = {}
        for _ in range(14):
            for o in parse(" | ".join(x.strip() for x in pg.inner_text("body").split("\n") if x.strip())):
                seen[(o["car"], o["klass"], o["gear"], o["price"])] = o
            pg.mouse.wheel(0, 2600); pg.wait_for_timeout(1400)
        res[key] = {"url": url, "n": len(seen), "offers": list(seen.values())}
        print(f"{key}: {len(seen)} offers")
        for o in sorted(seen.values(), key=lambda x: (x['klass'], x['price'] or 0)):
            print("   ", o)
        sys.stdout.flush()

    # extras：点进冰岛那台 Peugeot 2008（自动 + SUV）看结账页有什么可加项
    pg.goto(LINKS["iceland"], wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(26000)
    extras_txt = None
    try:
        # 找到第一个 Automatic + SUV 的 View deal
        cards = pg.locator('[data-testid="virtuoso-item-list"] > div')
        for i in range(min(cards.count(), 25)):
            t = cards.nth(i).inner_text(timeout=3000)
            if "Automatic" in t and "SUV" in t:
                with pg.context.expect_page() as np:
                    cards.nth(i).get_by_text(re.compile("View deal", re.I)).first.click()
                p2 = np.value
                p2.wait_for_timeout(22000)
                extras_txt = p2.inner_text("body")
                break
    except Exception as e:
        extras_txt = f"__ERR__ {e}"
    res["extras_raw"] = (extras_txt or "")[:20000]
    if extras_txt and not extras_txt.startswith("__ERR__"):
        hits = [l for l in extras_txt.split("\n")
                if re.search(r"roof|rack|box|carrier|luggage|extra|add-?on|equipment|seat|wifi|gps|driver", l, re.I)]
        res["extras_hits"] = hits[:120]
        print("\n=== EXTRAS HITS ===")
        for h in hits[:120]: print("  ", h.strip()[:150])
    else:
        print("\nEXTRAS FAILED:", str(extras_txt)[:300])
    b.close()

json.dump(res, open("out_roofbox.json","w"), ensure_ascii=False, indent=1)
print("\n→ out_roofbox.json")
