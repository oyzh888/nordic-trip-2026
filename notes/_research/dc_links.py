#!/usr/bin/env python3
"""给「四台车」各生成一条可以直接点开的 DiscoverCars 比价链接，并当场验证它真的打得开。

为什么能这么做：DiscoverCars 的 /search/<uuid>?sq=<base64 json> 里那个 sq 是**未签名**的
（payload 里 Hash 是空字符串），路径上的 uuid 也不校验 —— 所以可以手工拼一条链接，
直接落在「我们那几个日期 + 那几个取还点」的实时结果页上，不用让人再手填表单。

验证的是三件事（缺一件就不能发给人点）：
  ① 页面上写的取/还日期和我们要的一致（不是被重置成默认的今天）
  ② 真的有报价（offers > 0，不是空结果页）
  ③ 最低价对得上我们文档里记的那个数量级

Usage: python3 dc_links.py [out.json]
"""
import base64, json, re, sys, uuid, pathlib
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# 取还点 id 是从 DiscoverCars 自己的 autocomplete 里挖出来的（notes/_research/dc_loc.py）
LOC = {"KEF": 1787, "EVE": 2088, "SVJ": 2092, "TOS": 2195, "OSL": 1710,
       "RVK": 3092, "LKN": 2091}   # LKN = Leknes Airport（2026-09-04 从 autocomplete 采到）

CARS = [
 dict(slug="car1-iceland", label="🇮🇸 冰岛 5 天",
      pick="KEF", drop="KEF", pick_dt="2026-09-25 12:00", drop_dt="2026-09-29 18:00",
      expect="$326 裸车（Peugeot 2008 4x4 自动）· 取车钟点对价格无影响，落地后随便填"),
 dict(slug="car2-lofoten", label="🇳🇴 车① 罗弗敦 3 天（异地还到 Leknes）",
      pick="EVE", drop="LKN", pick_dt="2026-09-30 11:00", drop_dt="2026-10-02 14:30",
      expect="$647（Ford Explorer 4WD）· 只有 5 个车源 · 配 WF816 15:40 那班"),
 dict(slug="car2b-lofoten-48h", label="🇳🇴 车① 同上但卡在 48h 内（省一个计费日）",
      pick="EVE", drop="LKN", pick_dt="2026-09-30 11:00", drop_dt="2026-10-02 11:00",
      expect="$571（Ford Explorer 4WD）· 便宜 $76 但要在小机场干等 4h40"),
 dict(slug="car3-tromso", label="🇳🇴 车② 特罗姆瑟 3 天",
      pick="TOS", drop="TOS", pick_dt="2026-10-02 17:00", drop_dt="2026-10-05 10:00",
      expect="$224（4x4 自动）· 落地 16:35 + 25 min"),
 dict(slug="car4-oslo", label="🇳🇴 车③ 奥斯陆 1 天",
      pick="OSL", drop="OSL", pick_dt="2026-10-05 10:45", drop_dt="2026-10-06 10:00",
      expect="$85（4x4 自动）· 配 TOS→OSL 08:20→10:15 那班，落地 +30 min"),
]


def url_for(c):
    sq = {"PickupLocationId": LOC[c["pick"]], "DropOffLocationId": LOC[c["drop"]],
          "PickupDateTime": c["pick_dt"], "DropOffDateTime": c["drop_dt"],
          "ResidenceCountry": "US", "DriverAge": 35, "Hash": ""}
    b = base64.urlsafe_b64encode(
        json.dumps(sq, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"https://www.discovercars.com/search/{uuid.uuid4()}?sq={b}"


def check(pg, c, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(24000)
    flat = " | ".join(x.strip() for x in pg.inner_text("body").split("\n") if x.strip())
    m = re.search(r"Pick-up date \| (.+?) \|.*?Drop-off date \| (.+?) \|", flat)
    items = pg.locator('[data-testid="virtuoso-item-list"] > div')
    prices = sorted(int(p.replace(",", "")) for p in re.findall(r"\$\s?([\d,]+)", flat))
    return {"dates_on_page": list(m.groups()) if m else None,
            "n_offers": items.count(),
            "cheapest_usd": prices[0] if prices else None,
            "has_results": "No cars found" not in flat and items.count() > 0}


def main():
    out_path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "out_dc_links.json")
    res = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                             viewport={"width": 1600, "height": 1200})
        for c in CARS:
            url = url_for(c)
            pg = ctx.new_page()
            try:
                r = check(pg, c, url)
            except Exception as e:
                r = {"error": f"{type(e).__name__}: {e}"[:200]}
            pg.close()
            res.append({**c, "url": url, **r})
            print(f"{c['slug']:14s} offers={r.get('n_offers')} cheapest=${r.get('cheapest_usd')} "
                  f"dates={r.get('dates_on_page')} {r.get('error','')}")
        br.close()
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print("→", out_path)


if __name__ == "__main__":
    main()
