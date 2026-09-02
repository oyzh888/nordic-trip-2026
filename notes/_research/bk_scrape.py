#!/usr/bin/env python3
"""Scrape Booking.com search results for entire homes/apartments with bedroom+bathroom counts.

Usage: python3 bk_scrape.py <jobs.json> <out_dir>
jobs.json: [{"slug":"tromso","ss":"Tromso, Norway","checkin":"2026-10-03","checkout":"2026-10-06"}, ...]
"""
import json
import re
import sys
import pathlib
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def build_url(job):
    q = {
        "ss": job["ss"],
        "checkin": job["checkin"],
        "checkout": job["checkout"],
        "group_adults": job.get("adults", 4),
        "group_children": 0,
        "no_rooms": 1,
        "selected_currency": "EUR",
        "lang": "en-us",
        "order": job.get("order", "price"),
    }
    url = "https://www.booking.com/searchresults.html?" + urlencode(q)
    if job.get("nflt"):
        url += "&nflt=" + job["nflt"]
    return url


def scrape(page, job):
    url = build_url(job)
    page.goto(url, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(6000)
    # dismiss cookie / signin popups
    for sel in ['button[aria-label*="Dismiss"]', '#onetrust-accept-btn-handler',
                'button:has-text("Accept")']:
        try:
            page.locator(sel).first.click(timeout=2500)
            page.wait_for_timeout(800)
        except Exception:
            pass
    # scroll to load more cards
    for _ in range(job.get("scrolls", 6)):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(1200)
        try:
            page.locator('button:has-text("Load more results")').first.click(timeout=2000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

    cards = page.locator('[data-testid="property-card"]')
    n = cards.count()
    rows = []
    for i in range(n):
        c = cards.nth(i)
        try:
            txt = c.inner_text(timeout=4000)
        except Exception:
            continue
        name = txt.split("\n")[0].strip()
        try:
            link = c.locator('a[data-testid="title-link"]').first.get_attribute("href") or ""
        except Exception:
            link = ""
        beds = re.search(r"(\d+)\s+bedroom", txt, re.I)
        baths = re.search(r"(\d+)\s+bathroom", txt, re.I)
        price = re.findall(r"€\s?([\d,]+)", txt)
        rows.append({
            "name": name,
            "bedrooms": int(beds.group(1)) if beds else None,
            "bathrooms": int(baths.group(1)) if baths else None,
            "price_eur_total": min(int(p.replace(",", "")) for p in price) if price else None,
            "score": (re.search(r"Scored\s+([\d.]+)", txt) or [None, None])[1],
            "url": link.split("?")[0],
            "raw": " | ".join(l for l in txt.split("\n") if l.strip())[:600],
        })
    return url, rows


def main():
    jobs = json.load(open(sys.argv[1]))
    out = pathlib.Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, viewport={"width": 1600, "height": 1000},
                             locale="en-US")
        for job in jobs:
            page = ctx.new_page()
            try:
                url, rows = scrape(page, job)
            except Exception as e:  # noqa: BLE001
                url, rows = build_url(job), [{"error": f"{type(e).__name__}: {e}"}]
            (out / f"{job['slug']}.json").write_text(
                json.dumps({"job": job, "url": url, "rows": rows}, ensure_ascii=False, indent=1))
            ok = [r for r in rows if r.get("bathrooms")]
            print(f"{job['slug']}: {len(rows)} cards, {len(ok)} with bathroom info")
            page.close()
        br.close()


if __name__ == "__main__":
    main()
