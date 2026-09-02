import re
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    pg=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1600,"height":1100}).new_page()
    pg.goto("https://www.discovercars.com/",wait_until="domcontentloaded",timeout=90000)
    pg.wait_for_timeout(4000)
    for s in ['#onetrust-accept-btn-handler','button:has-text("Accept")']:
        try: pg.locator(s).first.click(timeout=2000)
        except Exception: pass
    box=pg.locator('#PickupLocation')
    box.click(); box.type("Keflavik",delay=140)
    pg.wait_for_timeout(3500)
    # dump every element with visible text containing Keflavik
    els=pg.locator('li, [role="option"], div[class*="item"], div[class*="option"], a[class*="item"]')
    print("candidates:",els.count())
    for i in range(min(els.count(),400)):
        try:
            t=els.nth(i).inner_text(timeout=800).strip()
        except Exception: continue
        if "Keflav" in t and len(t)<120:
            cls=els.nth(i).get_attribute("class") or ""
            tag=els.nth(i).evaluate("e=>e.tagName")
            print(f"  [{i}] {tag}.{cls[:60]} :: {t[:70]!r}")
    # dates
    pg.keyboard.press("Escape")
    for s in ['text=Pick-up date','[class*="pickup-date"]','input#PickupDate']:
        try:
            pg.locator(s).first.click(timeout=2500); pg.wait_for_timeout(2000); print("opened cal via",s); break
        except Exception: pass
    cal=pg.locator('[class*="calendar"] *, [class*="datepicker"] *')
    print("cal nodes:",cal.count())
    html=pg.content()
    for pat in [r'data-date="[^"]{4,12}"', r'aria-label="[^"]*Sep[^"]{0,30}"', r'class="[^"]*day[^"]*"']:
        m=sorted(set(re.findall(pat,html)))[:8]
        print(pat,"->",m)
    br.close()
