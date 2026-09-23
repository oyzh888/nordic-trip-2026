#!/usr/bin/env python3
"""换平台核「马拉喀什→伦敦」—— Google Flights 连续 5 次给出 7h50（实际应约 3h40），
明显是它自己的解析/数据问题。这里用 Kayak 和 Kiwi 交叉验证时长与价格。"""
import re,sys,json
from playwright.sync_api import sync_playwright
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
out={}
with sync_playwright() as p:
    br=p.chromium.launch(); ctx=br.new_context(user_agent=UA,locale="en-US",viewport={"width":1500,"height":1400})
    for name,url in [
      ("kayak","https://www.kayak.com/flights/RAK-LON/2026-10-14?sort=bestflight_a&fs=stops=0"),
      ("kiwi","https://www.kiwi.com/en/search/results/marrakesh-morocco/london-united-kingdom/2026-10-14")]:
        pg=ctx.new_page()
        try:
            pg.goto(url,wait_until="domcontentloaded",timeout=90000)
            for sel in ('button:has-text("Accept")','button:has-text("Agree")','[aria-label*="close" i]'):
                try: pg.locator(sel).first.click(timeout=3000)
                except Exception: pass
            last,stable,w=-1,0,0
            while w<45 and stable<2:
                pg.wait_for_timeout(3000); w+=3
                n=len(pg.inner_text("body"))
                stable=stable+1 if n==last else 0; last=n
            t=re.sub(r"\s+"," ",pg.inner_text("body"))
            durs=sorted(set(re.findall(r"\b(\d)h\s?(\d{2})m\b",t)))
            prices=sorted(set(int(x.replace(",","")) for x in re.findall(r"\$\s?(\d{2,4})\b",t)))[:8]
            out[name]=dict(durs=[f"{a}h{b}" for a,b in durs][:10], prices=prices, url=url,
                           has_direct=bool(re.search(r"non ?stop|direct",t,re.I)))
            print(f"== {name}: 时长候选 {out[name]['durs']}")
            print(f"   价格候选 {prices} · 提到直飞: {out[name]['has_direct']}")
        except Exception as e:
            print(f"== {name} ❌ {type(e).__name__}: {str(e)[:90]}")
            out[name]=dict(error=str(e)[:200])
        sys.stdout.flush(); pg.close()
    br.close()
json.dump(out,open("out_altplat.json","w"),ensure_ascii=False,indent=1)
print("DONE")
