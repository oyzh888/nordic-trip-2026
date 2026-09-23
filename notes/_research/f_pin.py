#!/usr/bin/env python3
"""把两个还没确认的时刻钉死：
  ① 9/24 北京首都 T2 → 奥斯陆（携程截图写 9h25 直飞，但落地钟点被裁掉）
  ② 9/30 奥斯陆 → 埃沃内斯 EVE（截图只露出「前往 埃沃内斯」）
思路：这两段都是**公开时刻表**。如果航线上「9h25 直飞」只有一班，落地钟点就被唯一确定。"""
import json,re,sys,urllib.parse
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JOBS=[("PIN-pek-osl","PEK","OSL","2026-09-24"),
      ("PIN-osl-eve","OSL","EVE","2026-09-30")]
PRICE=re.compile(r"\$\s?([\d,]+)");DUR=re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?")
STOPS=re.compile(r"(Nonstop|1 stop|2 stops|3 stops)",re.I)
TIMES=re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)\s*[–\-—]\s*(\d{1,2}:\d{2}\s*[AP]M)")
def to24(s):
    m=re.match(r"(\d{1,2}):(\d{2})\s*([AP])M",s.replace(" "," ").strip(),re.I)
    if not m: return None
    h,mi,ap=int(m.group(1)),int(m.group(2)),m.group(3).upper()
    if ap=="P" and h!=12: h+=12
    if ap=="A" and h==12: h=0
    return f"{h:02d}:{mi:02d}"
res={}
with sync_playwright() as p:
    br=p.chromium.launch();ctx=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1500,"height":1700})
    for slug,fr,to,d in JOBS:
        pg=ctx.new_page();offs=[]
        url="https://www.google.com/travel/flights?hl=en&curr=USD&q="+urllib.parse.quote(f"one-way flights from {fr} to {to} on {d}")
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
            for i in range(min(rows.count(),40)):
                try: t=re.sub(r"\s+"," ",rows.nth(i).inner_text(timeout=3000))
                except Exception: continue
                dm,st,tm=DUR.search(t),STOPS.search(t),TIMES.search(t)
                if not(dm and tm): continue
                dep,arr=to24(tm.group(1)),to24(tm.group(2))
                if not(dep and arr): continue
                pr=PRICE.search(t)
                mins=int(dm.group(1))*60+int(dm.group(2) or 0)
                air=re.search(r"(Air China|China Eastern|China Southern|Hainan|Finnair|SAS|Scandinavian|KLM|Lufthansa|Air France|Turkish|Aeroflot|Norwegian|Wideroe|Widerøe|British Airways|Swiss|Qatar|Emirates|Etihad|Cathay|Juneyao)",t)
                nxt = "+1" if re.search(r"\+\s?1",t) else ""
                k=(dep,arr,mins)
                if k in seen: continue
                seen.add(k)
                offs.append(dict(dep=dep,arr=arr,nxt=nxt,mins=mins,stops=st.group(1) if st else "?",
                                 air=air.group(1) if air else "?",
                                 price=int(pr.group(1).replace(",","")) if pr else None))
        except Exception as e: print(f"{slug} ERR {type(e).__name__}")
        res[slug]=dict(frm=fr,to=to,date=d,url=url,offers=offs)
        ns=[o for o in offs if o["stops"].lower()=="nonstop"]
        print(f"\n===== {fr} → {to} · {d} · 共 {len(offs)} 条，其中直飞 {len(ns)} 条")
        for o in sorted(ns,key=lambda x:x["dep"]):
            h,m=o['mins']//60,o['mins']%60
            print(f"   {o['dep']} → {o['arr']}{o['nxt']}  {h}h{m:02d}  {o['air']:<16}"
                  + (f"${o['price']}" if o['price'] else ""))
        if not ns:
            print("   ⚠️ 没有直飞；最短的几条：")
            for o in sorted(offs,key=lambda x:x["mins"])[:4]:
                print(f"   {o['dep']}→{o['arr']}{o['nxt']} {o['mins']//60}h{o['mins']%60:02d} {o['stops']} {o['air']}")
        sys.stdout.flush();pg.close()
    json.dump(res,open("out_pin.json","w"),ensure_ascii=False,indent=1);br.close()
print("\nDONE")
