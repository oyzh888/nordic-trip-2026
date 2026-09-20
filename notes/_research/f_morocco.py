#!/usr/bin/env python3
"""第六轮：加进摩洛哥 + 时间放开（可请假、不卡周末）。

新约束（Steve 2026-09-20 晚）：
  · 可以多 hop，甚至去摩洛哥
  · **航班尽量白天**（上午起飞、15:00 前落地最好）
  · 🔴 硬要求：**10:30–11:30 ET 必须有网** = 法国当地 16:30–17:30 / 伦敦·摩洛哥当地 15:30–16:30
    （摩洛哥全年 UTC+1，与伦敦同时区；10 月欧洲仍夏令时）
  · 20:00–01:00 当地「基本没事」→ 留给工作
  · 总差异 $2,000 以内都可以 → 价格基本不是判据了
判据因此变成：**落地时刻 ≤ 15:00 当地**（保住那一小时有网）+ 段数尽量少。
"""
import json, re, sys, urllib.parse
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
JOBS=[
 ("m-nce-rak-1010","NCE","RAK","2026-10-10","尼斯→马拉喀什"),
 ("m-mrs-rak-1010","MRS","RAK","2026-10-10","马赛→马拉喀什（南法西段出发）"),
 ("m-rak-lon-1014","RAK","LON","2026-10-14","马拉喀什→伦敦"),
 ("m-rak-lgw-1015","RAK","LGW","2026-10-15","马拉喀什→伦敦 Gatwick 晚一天"),
 ("m-lhr-sfo-1019","LHR","SFO","2026-10-19","伦敦→SFO 周一"),
 ("m-lhr-sfo-1020","LHR","SFO","2026-10-20","伦敦→SFO 周二"),
 ("m-lhr-sfo-1021","LHR","SFO","2026-10-21","伦敦→SFO 周三"),
]
PRICE=re.compile(r"\$\s?([\d,]+)"); DUR=re.compile(r"(\d+)\s*hr(?:\s*(\d+)\s*min)?")
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
    br=p.chromium.launch(); ctx=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1500,"height":1500})
    for slug,fr,to,d,lab in JOBS:
        pg=ctx.new_page()
        url=("https://www.google.com/travel/flights?hl=en&curr=USD&q="
             +urllib.parse.quote(f"one-way flights from {fr} to {to} on {d} for 1 adult"))
        offs=[]
        try:
            pg.goto(url,wait_until="domcontentloaded",timeout=90000)
            for sel in ('button:has-text("Accept all")','button:has-text("Reject all")'):
                try: pg.locator(sel).first.click(timeout=2500); break
                except Exception: pass
            last,stable,w=-1,0,0
            while w<40 and stable<2:
                pg.wait_for_timeout(2500); w+=2.5
                n=pg.locator("li").filter(has_text=re.compile(r"\$")).count()
                stable=stable+1 if n==last else 0; last=n
            rows=pg.locator("li").filter(has_text=re.compile(r"\$")); seen=set()
            for i in range(min(rows.count(),30)):
                try: t=re.sub(r"\s+"," ",rows.nth(i).inner_text(timeout=3000))
                except Exception: continue
                pr,dm,st,tm=PRICE.search(t),DUR.search(t),STOPS.search(t),TIMES.search(t)
                if not(pr and dm and tm): continue
                dep,arr=to24(tm.group(1)),to24(tm.group(2))
                if not(dep and arr): continue
                mins=int(dm.group(1))*60+int(dm.group(2) or 0)
                air=re.search(r"(United|British Airways|Air France|Norwegian|easyJet|Ryanair|KLM|Lufthansa|"
                              r"SAS|Virgin Atlantic|Aer Lingus|Vueling|Iberia|Swiss|Delta|Transavia|"
                              r"Royal Air Maroc|Air Arabia|TAP|Wizz|ITA)",t)
                k=(pr.group(1),dep,arr,mins)
                if k in seen: continue
                seen.add(k)
                offs.append(dict(price=int(pr.group(1).replace(",","")),dep=dep,arr=arr,mins=mins,
                                 stops=st.group(1) if st else "?",air=air.group(1) if air else "?"))
        except Exception as e:
            print(slug,"ERR",type(e).__name__)
        offs.sort(key=lambda x:(x["price"],x["mins"]))
        res[slug]=dict(label=lab,url=url,offers=offs[:14])
        ns=[o for o in offs if o["stops"].lower()=="nonstop"]
        print(f"== {slug:16} {lab}")
        for o in (ns[:4] if ns else offs[:3]):
            ok='✅' if o['arr']<='15:00' and o['arr']>='07:00' else '⚠️'
            print(f"   ${o['price']:>5} {o['dep']}→{o['arr']} {o['mins']//60}h{o['mins']%60:02d} "
                  f"{o['stops']:<9}{o['air']:<18}{ok}")
        if not ns: print("   ⚠️ 无直飞")
        sys.stdout.flush(); pg.close()
    json.dump(res,open("out_morocco.json","w"),ensure_ascii=False,indent=1); br.close()
print("DONE")
