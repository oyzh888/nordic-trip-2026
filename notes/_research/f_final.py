#!/usr/bin/env python3
"""最终核价：三条线的**每一段**都要有今天的实价，一段不漏。
包括 Steve 指出我漏掉的 OSL 出发段，以及他问的 SJC。"""
import json,re,sys,urllib.parse
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JOBS=[
 # A 线：尼斯 → 里斯本 → 伦敦 → SFO
 ("A1-osl-nce","OSL","NCE","2026-10-06"),
 ("A2-nce-lis","NCE","LIS","2026-10-09"),
 ("A3-lis-lon","LIS","LON","2026-10-12"),
 ("A4-lhr-sfo","LHR","SFO","2026-10-15"),
 # B 线：伦敦 → 尼斯 → 里斯本 → SFO
 ("B1-osl-lon","OSL","LON","2026-10-06"),
 ("B2-lon-nce","LON","NCE","2026-10-09"),
 ("B3-nce-lis","NCE","LIS","2026-10-12"),
 ("B4-lis-sfo","LIS","SFO","2026-10-15"),
 # C 线：尼斯 → 马拉喀什 → 伦敦 → SFO
 ("C2-nce-rak","NCE","RAK","2026-10-10"),
 ("C3-rak-lgw","RAK","LGW","2026-10-13"),
 ("C4-lhr-sfo","LHR","SFO","2026-10-16"),
 # Steve 问的 SJC
 ("X-lhr-sjc","LHR","SJC","2026-10-15"),
 ("X-lis-sjc","LIS","SJC","2026-10-15"),
]
PRICE=re.compile(r"\$\s?([\d,]+)");DUR=re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?")
STOPS=re.compile(r"(Nonstop|1 stop|2 stops|3 stops)",re.I)
TIMES=re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)\s*[–\-—]\s*(\d{1,2}:\d{2}\s*[AP]M)")
def to24(s):
    m=re.match(r"(\d{1,2}):(\d{2})\s*([AP])M",s.replace(" "," ").strip(),re.I)
    if not m: return None
    h,mi,ap=int(m.group(1)),int(m.group(2)),m.group(3).upper()
    if ap=="P" and h!=12: h+=12
    if ap=="A" and h==12: h=0
    return f"{h:02d}:{mi:02d}"
res={}
with sync_playwright() as p:
    br=p.chromium.launch();ctx=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1500,"height":1600})
    for slug,fr,to,d in JOBS:
        pg=ctx.new_page(); offs=[]
        url="https://www.google.com/travel/flights?hl=en&curr=USD&q="+urllib.parse.quote(f"one-way flights from {fr} to {to} on {d} for 1 adult")
        try:
            pg.goto(url,wait_until="domcontentloaded",timeout=90000)
            for sel in ('button:has-text("Accept all")','button:has-text("Reject all")'):
                try: pg.locator(sel).first.click(timeout=2500);break
                except Exception: pass
            last,stable,w=-1,0,0
            while w<45 and stable<2:
                pg.wait_for_timeout(2500);w+=2.5
                n=pg.locator("li").filter(has_text=re.compile(r"\$")).count()
                stable=stable+1 if n==last else 0;last=n
            rows=pg.locator("li").filter(has_text=re.compile(r"\$"));seen=set()
            for i in range(min(rows.count(),35)):
                try: t=re.sub(r"\s+"," ",rows.nth(i).inner_text(timeout=3000))
                except Exception: continue
                pr,dm,st,tm=PRICE.search(t),DUR.search(t),STOPS.search(t),TIMES.search(t)
                if not(pr and dm and tm): continue
                dep,arr=to24(tm.group(1)),to24(tm.group(2))
                if not(dep and arr): continue
                mins=int(dm.group(1))*60+int(dm.group(2) or 0)
                air=re.search(r"(British Airways|Air France|easyJet|Ryanair|KLM|Lufthansa|Transavia|Royal Air Maroc|TAP|United|Virgin Atlantic|Norwegian|SAS|Vueling|Iberia|Swiss|Aer Lingus|Wizz|Volotea|Delta|Air Canada|Finnair)",t)
                k=(pr.group(1),dep,arr,mins)
                if k in seen: continue
                seen.add(k)
                offs.append(dict(price=int(pr.group(1).replace(",","")),dep=dep,arr=arr,mins=mins,
                                 stops=st.group(1) if st else "?",air=air.group(1) if air else "?"))
        except Exception as e: print(f"{slug} ERR {type(e).__name__}")
        offs.sort(key=lambda x:(x["price"],x["mins"]))
        res[slug]=dict(frm=fr,to=to,date=d,url=url,offers=offs[:15])
        ns=[o for o in offs if o["stops"].lower()=="nonstop"]
        print(f"== {slug} {fr}→{to} {d}  共 {len(offs)} 条")
        for o in (ns[:3] if ns else offs[:3]):
            print(f"   ${o['price']:>5} {o['dep']}→{o['arr']} {o['mins']//60}h{o['mins']%60:02d} {o['stops']:<9}{o['air']}")
        if offs and not ns: print("   ⚠️ 无直飞")
        if not offs: print("   ❌ 没抓到")
        sys.stdout.flush(); pg.close()
    json.dump(res,open("out_final.json","w"),ensure_ascii=False,indent=1);br.close()
print("DONE")
