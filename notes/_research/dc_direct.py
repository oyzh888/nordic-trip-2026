#!/usr/bin/env python3
"""DiscoverCars live quotes via direct /search/<uuid>?sq=<b64 json> deep link.

The sq payload is unsigned (Hash:"") and the UUID path segment is not validated,
so a random UUID + hand-built payload returns a real live result set.

Usage: python3 dc_direct.py <jobs.json> <out_dir>
job: {"slug","pick_id","drop_id"?,"pick_dt","drop_dt","country"?,"age"?}
Location ids harvested from the form: KEF 1787 | Evenes/EVE 2088 | Svolvaer 2092 | Tromso apt 2195
"""
import base64, json, re, sys, uuid, pathlib
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def url_for(j):
    sq = {"PickupLocationId": j["pick_id"], "DropOffLocationId": j.get("drop_id", j["pick_id"]),
          "PickupDateTime": j["pick_dt"], "DropOffDateTime": j["drop_dt"],
          "ResidenceCountry": j.get("country", "US"), "DriverAge": j.get("age", 35), "Hash": ""}
    b = base64.urlsafe_b64encode(
        json.dumps(sq, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"https://www.discovercars.com/search/{uuid.uuid4()}?sq={b}"


def parse(flat):
    price = [int(p.replace(",", "")) for p in re.findall(r"[€$£]\s?([\d,]+)", flat)]
    total = re.search(r"([\d,]+)\s*(?:total|for \d+ day)", flat, re.I)
    return {
        "car": flat.split(" | ")[0][:60],
        "supplier": (re.search(
            r"(Blue Car Rental|Blue Rental|Go Car Rental|Lava Car|Lotus Car|Hertz|Avis|Sixt|"
            r"Europcar|Budget|Enterprise|Green Motion|Thrifty|Alamo|Dollar|Reykjavik Cars|"
            r"Geysir|Fara|Autounion|Nordic Car|Rent A Car|Right Cars|SADCars|Procar|Keddy|"
            r"Northbound|Blue|Firefly)", flat, re.I) or [None, None])[1],
        "prices": price[:5],
        "total_days": (re.search(r"[Tt]otal for (\d+) day", flat) or [None, None])[1],
        "awd": bool(re.search(r"\b(4x4|AWD|4WD|SUV)\b", flat, re.I)),
        "auto": "Automatic" in flat,
        "free_cancel": "Free cancellation" in flat,
        "score": (re.search(r"\b([\d.]+)\s*/\s*10\b", flat) or [None, None])[1],
        "raw": flat[:400],
    }


def scrape(pg, j):
    url = url_for(j)
    pg.goto(url, wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(22000)
    body0 = pg.inner_text("body")
    seen, rows = set(), []
    for step in range(14):
        items = pg.locator('[data-testid="virtuoso-item-list"] > div')
        for i in range(items.count()):
            try:
                t = items.nth(i).inner_text(timeout=3000)
            except Exception:
                continue
            flat = " | ".join(dict.fromkeys(x.strip() for x in t.split("\n") if x.strip()))
            if len(flat) < 60 or flat[:90] in seen:
                continue
            seen.add(flat[:90])
            rows.append(parse(flat))
        pg.mouse.wheel(0, 2600)
        pg.wait_for_timeout(1700)
    m = re.search(r"Pick-up date \| (.+?) \|.*?Drop-off date \| (.+?) \|",
                  " | ".join(x.strip() for x in body0.split("\n") if x.strip()))
    return {"url": url, "dates_on_page": m.groups() if m else None,
            "n_offers": len(rows), "rows": rows}


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                             viewport={"width": 1600, "height": 1200})
        for j in jobs:
            pg = ctx.new_page()
            try:
                res = scrape(pg, j)
            except Exception as e:
                res = {"error": f"{type(e).__name__}: {e}"[:250]}
            res["job"] = j
            (out / f"{j['slug']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
            print(f"{j['slug']}: {res.get('n_offers', 0)} offers | dates={res.get('dates_on_page')} "
                  f"{res.get('error','')[:70]}")
            pg.close()
        br.close()


if __name__ == "__main__":
    main()
