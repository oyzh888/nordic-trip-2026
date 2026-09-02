import json, pathlib, urllib.parse, re
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
inj={"caller":"D-FLOW","adults":4,"children":0,"locale":"en","month":10,"year":2026,
     "productTypes":"NORWEGIAN COAST"}
URL="https://prod.havilavoyages.com/touchhvl/?inJson="+urllib.parse.quote(json.dumps(inj),safe="")
with sync_playwright() as p:
    br=p.chromium.launch(headless=True)
    pg=br.new_context(user_agent=UA,locale="en-GB",viewport={"width":1500,"height":1200}).new_page()
    reqs=[]
    pg.on("response", lambda r: reqs.append((r.status, r.request.resource_type, r.url[:180])))
    errs=[]
    pg.on("console", lambda m: errs.append(m.type+": "+m.text[:300]))
    pg.on("pageerror", lambda e: errs.append("pageerror: "+str(e)[:400]))
    pg.goto(URL,wait_until="load",timeout=120000)
    pg.wait_for_timeout(40000)
    html=pg.content()
    pathlib.Path("out_cruise/hav-doc.html").write_text(html)
    print("--- scripts in doc ---")
    for m in re.findall(r'<script[^>]*src="([^"]+)"', html): print("  ", m)
    print("base:", re.findall(r'<base[^>]*>', html))
    print("--- all responses ---")
    for s,rt,u in reqs: print(s, rt, u)
    print("--- console ---")
    for e in errs[:40]: print(" ", e)
    br.close()
