#!/usr/bin/env python3
"""Hurtigruten port-to-port: full drive to live availability + cabin prices.

Usage: python3 cruise_book.py <from> <to> <YYYY-MM-DD> <cabins> <adults_per_cabin> <slug>
e.g.   python3 cruise_book.py Svolvær Tromsø 2026-10-02 2 2 hrg-svj-tos-2cab
"""
import datetime as dt
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
URL = "https://www.hurtigruten.com/en-us/port-to-port"
SKIP = ("doubleclick", "google", "clarity", "cookielaw", "salesforce", "onetrust",
        "infinity-tracking", "visualwebsiteoptimizer", "bing", "cdn-cgi", "omappapi",
        "facebook", "stackadapt", "sentry", "hotjar")

FROM = sys.argv[1] if len(sys.argv) > 1 else "Svolvær"
TO = sys.argv[2] if len(sys.argv) > 2 else "Tromsø"
DATE = dt.date.fromisoformat(sys.argv[3] if len(sys.argv) > 3 else "2026-10-02")
CABINS = int(sys.argv[4]) if len(sys.argv) > 4 else 2
ADULTS = int(sys.argv[5]) if len(sys.argv) > 5 else 2
SLUG = sys.argv[6] if len(sys.argv) > 6 else "hrg-book"
out = pathlib.Path("out_cruise")
out.mkdir(parents=True, exist_ok=True)


def pick(pg, dd, text):
    box = pg.locator(f'[data-testid="{dd}"]')
    inp = box.locator("input").first
    inp.click()
    pg.wait_for_timeout(500)
    inp.type(text, delay=100)
    pg.wait_for_timeout(2200)
    box.locator('li, [role="option"]').first.click()
    pg.wait_for_timeout(1500)
    return inp.input_value()


def date_field(pg):
    inps = pg.locator('input[type="text"]')
    for i in range(inps.count()):
        v = inps.nth(i).input_value()
        if v and re.fullmatch(r"\d{2}/\d{2}/\d{4}", v):
            return inps.nth(i), v
    return None, None


def set_date(pg, rec):
    """The Departure field is a masked input; try several encodings until the
    search button stops being disabled. Never trust a single write."""
    fld, initial = date_field(pg)
    rec["date_field_initial"] = initial
    if fld is None:
        rec["date_error"] = "no date field found"
        return False
    cands = [("digits-MDY", DATE.strftime("%m%d%Y")),
             ("digits-DMY", DATE.strftime("%d%m%Y")),
             ("slash-MDY", DATE.strftime("%m/%d/%Y")),
             ("slash-DMY", DATE.strftime("%d/%m/%Y"))]
    tried = []
    for name, val in cands:
        fld.click()
        pg.wait_for_timeout(400)
        for _ in range(12):
            fld.press("Backspace")
        fld.press("Control+a")
        fld.press("Delete")
        pg.wait_for_timeout(300)
        fld.type(val, delay=150)
        pg.wait_for_timeout(2500)
        back = fld.input_value()
        body = pg.inner_text("body")
        bad = bool(re.search(r"Date must be|not a valid", body))
        try:
            disabled = pg.locator('[data-testid="search-button"]').first.is_disabled()
        except Exception:
            disabled = None
        tried.append({"how": name, "typed": val, "readback": back,
                      "validation_error": bad, "search_disabled": disabled})
        if not bad and disabled is False:
            rec["date_attempts"] = tried
            rec["date_accepted"] = tried[-1]
            return True
    rec["date_attempts"] = tried
    rec["date_accepted"] = None
    return False


def set_adults(pg, target, rec):
    """Every cabin gets `target` adults. Steppers are the innermost divs whose
    text is exactly '<n> Adults'."""
    log = []
    rows = pg.locator('div').filter(has_text=re.compile(r"^\s*\d+\s*\n?\s*Adults\s*$"))
    n = rows.count()
    for i in range(n):
        row = rows.nth(i)
        try:
            for _ in range(6):
                cur = int(re.search(r"(\d+)", row.inner_text(timeout=2000)).group(1))
                if cur >= target:
                    break
                row.locator("button").last.click(timeout=2500)
                pg.wait_for_timeout(700)
            log.append(re.sub(r"\s+", " ", row.inner_text(timeout=2000))[:40])
        except Exception as e:  # noqa: BLE001
            log.append(f"ERR {type(e).__name__}")
    rec["adult_steppers"] = log
    rec["adult_stepper_count"] = n


with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US",
                         viewport={"width": 1600, "height": 1500})
    pg = ctx.new_page()
    api = []

    def on_resp(r):
        if r.request.resource_type not in ("xhr", "fetch") or any(b in r.url for b in SKIP):
            return
        it = {"m": r.request.method, "u": r.url[:700], "s": r.status}
        try:
            it["body"] = r.text()[:20000]
        except Exception:
            pass
        try:
            if r.request.post_data:
                it["post"] = r.request.post_data[:3000]
        except Exception:
            pass
        api.append(it)

    ctx.on("response", on_resp)
    rec = {"from": FROM, "to": TO, "date": DATE.isoformat(),
           "cabins": CABINS, "adults_per_cabin": ADULTS}
    try:
        pg.goto(URL, wait_until="domcontentloaded", timeout=90_000)
        pg.wait_for_timeout(9000)
        try:
            pg.locator("#onetrust-accept-btn-handler").click(timeout=3000)
            pg.wait_for_timeout(1000)
        except Exception:
            pass
        rec["from_val"] = pick(pg, "from-port-dropdown", FROM)
        rec["to_val"] = pick(pg, "to-port-dropdown", TO)
        pg.wait_for_timeout(1500)
        try:
            pg.locator('input[name="is-round-trip"][value="oneWay"]').check(force=True)
            pg.wait_for_timeout(700)
        except Exception:
            pass
        try:
            pg.locator('input[name="is-via-kirkenes"][value="false"]').check(force=True)
            pg.wait_for_timeout(600)
        except Exception:
            pass
        pg.locator('[data-testid="cabin-choice-want-cabin"]').click(timeout=8000)
        pg.wait_for_timeout(4000)
        for _ in range(CABINS - 1):
            try:
                pg.locator('button:has-text("Add more cabins")').first.click(timeout=4000)
                pg.wait_for_timeout(1500)
            except Exception:
                break
        set_adults(pg, ADULTS, rec)
        rec["date_ok"] = set_date(pg, rec)
        # re-read the whole form area before submitting
        rec["form_snapshot"] = re.sub(
            r"\n+", " | ", pg.inner_text("body")[:2500])
        btn = pg.locator('button:has-text("See availability and prices")').first
        btn.click(timeout=8000)
        pg.wait_for_timeout(25000)
        rec["result_url"] = pg.url
        rec["result_body"] = pg.inner_text("body")[:20000]
    except Exception as e:  # noqa: BLE001
        rec["error"] = f"{type(e).__name__}: {e}"
        try:
            rec["result_url"] = pg.url
            rec["result_body"] = pg.inner_text("body")[:20000]
        except Exception:
            pass
    rec["api"] = api[:80]
    (out / f"{SLUG}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    print("from/to:", rec.get("from_val"), "->", rec.get("to_val"))
    print("date_ok:", rec.get("date_ok"), "accepted:", rec.get("date_accepted"))
    for t in rec.get("date_attempts", []):
        print("   attempt", t)
    print("adults:", rec.get("adult_stepper_count"), rec.get("adult_steppers"))
    print("result_url:", rec.get("result_url"), "| err:", rec.get("error", ""))
    for a in api[:40]:
        print(a["s"], a["m"], a["u"][:220])
    print("----- BODY -----")
    print((rec.get("result_body") or "")[:6000])
    br.close()
