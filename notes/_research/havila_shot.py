import json, pathlib, sys, urllib.parse
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
MONTH=int(sys.argv[1]); YEAR=int(sys.argv[2]); WAIT=int(sys.argv[3])
inj={"caller":"D-FLOW","adults":4,"children":0,"locale":"en","month":MONTH,"year":YEAR,
     "productTypes":"NORWEGIAN COAST"}
URL="https://prod.havilavoyages.com/touchhvl/?inJson="+urllib.parse.quote(json.dumps(inj),safe="")
out=pathlib.Path("out_cruise"); out.mkdir(exist_ok=True)
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    pg=br.new_context(user_agent=UA,locale="en-GB",viewport={"width":1500,"height":1200}).new_page()
    pg.goto(URL,wait_until="load",timeout=120000)
    pg.wait_for_timeout(WAIT*1000)
    pg.screenshot(path=str(out/f"hav-{YEAR}{MONTH:02d}.png"),full_page=False)
    print("html len", len(pg.content()))
    print("flutter glass?", pg.eval_on_selector_all("flutter-view,canvas,flt-glass-pane","e=>e.map(x=>x.tagName)"))
    br.close()
