#!/usr/bin/env python3
"""Open each shortlisted Airbnb listing for OUR real dates and verify it.

The search cards are not trustworthy enough for a hard "must have 2 bathrooms"
requirement, and they never show the cleaning/service fee. This opens the room
page itself, screenshots it, and pulls out the numbers that actually matter.

Usage: python3 abnb_detail.py <jobs.json> <out_dir>
job: {"slug","room","checkin","checkout","adults"?,"note"?}
"""
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def url_for(j):
    return (f"https://www.airbnb.com/rooms/{j['room']}"
            f"?check_in={j['checkin']}&check_out={j['checkout']}"
            f"&adults={j.get('adults', 4)}&guests={j.get('adults', 4)}"
            f"&currency=EUR&locale=en")


def grab(pg, j, out):
    pg.goto(url_for(j), wait_until="domcontentloaded", timeout=120_000)
    pg.wait_for_timeout(11000)
    for sel in ('button[aria-label="Close"]', 'button:has-text("OK")'):
        try:
            pg.locator(sel).first.click(timeout=2500)
            pg.wait_for_timeout(800)
            break
        except Exception:
            pass
    shots = []
    pg.screenshot(path=str(out / f"{j['slug']}-1.png"))
    shots.append(f"{j['slug']}-1.png")
    body = pg.inner_text("body")
    # the price panel and the "what this place offers" block sit further down
    for n, y in enumerate([1100, 1100], start=2):
        pg.mouse.wheel(0, y)
        pg.wait_for_timeout(2500)
        pg.screenshot(path=str(out / f"{j['slug']}-{n}.png"))
        shots.append(f"{j['slug']}-{n}.png")
    body += "\n" + pg.inner_text("body")
    flat = re.sub(r"[ \t]+", " ", body)

    def one(pat, g=1):
        m = re.search(pat, flat, re.I)
        return m.group(g).strip() if m else None

    rec = {
        "slug": j["slug"], "note": j.get("note"), "room": j["room"],
        "dates": f"{j['checkin']}~{j['checkout']}", "url": url_for(j),
        "title": (pg.title() or "")[:120],
        "config": one(r"(\d+\s*bedrooms?\s*[·•]\s*\d+\s*beds?\s*[·•]\s*[\d.]+\s*(?:shared\s*)?bath\w*)"),
        "bedrooms": one(r"(\d+)\s*bedrooms?"),
        "beds": one(r"(\d+)\s*beds?\b"),
        "baths": one(r"([\d.]+)\s*(?:private |shared |half-)?bath"),
        "guests": one(r"(\d+)\s*guests?"),
        "rating": one(r"([\d.]{3,4})\s*(?:out of 5|·\s*\d+ review)"),
        "nightly_line": one(r"(€\s?[\d,]+ x \d+ nights?)"),
        "cleaning_fee": one(r"cleaning fee\s*€\s?([\d,]+)"),
        "service_fee": one(r"service fee\s*€\s?([\d,]+)"),
        "taxes": one(r"taxes\s*€\s?([\d,]+)"),
        "total": one(r"total(?:\s*\(EUR\))?\s*€\s?([\d,]+)"),
        "cancellation": one(r"(Free cancellation (?:before|for) [^\n]{3,60}|"
                            r"non-?refundable[^\n]{0,40})"),
        "min_stay": one(r"(minimum stay[^\n]{0,40}|\d+\s*night minimum)"),
        "unavailable": bool(re.search(r"these dates are not available|"
                                      r"minimum stay.*\d|check the calendar", flat, re.I)),
        "shots": shots,
    }
    rec["all_baths_mentions"] = list(dict.fromkeys(
        re.findall(r"[\w\-.]*\s?bath(?:room)?s?[^\n]{0,30}", flat, re.I)))[:8]
    rec["body"] = flat[:12000]
    return rec


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    summary = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="en-US",
                            viewport={"width": 1500, "height": 1250})
        for j in jobs:
            pg = ctx.new_page()
            try:
                rec = grab(pg, j, out)
            except Exception as e:  # noqa: BLE001
                rec = {"slug": j["slug"], "error": f"{type(e).__name__}: {e}"[:200]}
            (out / f"{j['slug']}.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=1))
            summary.append({k: rec.get(k) for k in
                            ("slug", "note", "config", "bedrooms", "baths", "guests",
                             "nightly_line", "cleaning_fee", "service_fee", "total",
                             "cancellation", "min_stay", "unavailable", "rating", "error")})
            print(f"== {rec.get('slug')} {rec.get('error','')}")
            print(f"   cfg={rec.get('config')} | br={rec.get('bedrooms')} "
                  f"bath={rec.get('baths')} guests={rec.get('guests')}")
            print(f"   {rec.get('nightly_line')} clean={rec.get('cleaning_fee')} "
                  f"svc={rec.get('service_fee')} TOTAL={rec.get('total')}")
            print(f"   cxl={rec.get('cancellation')} min={rec.get('min_stay')} "
                  f"unavail={rec.get('unavailable')}")
            pg.close()
        br.close()
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
