#!/usr/bin/env python3
"""把挑好的图统一解析成 /thumb/ URL。
原因：Commons 在「原图比请求宽度还小」时会把 thumburl 直接给成**原图**路径，
而原图边缘缓存差、体积大，实测会被 upload.wikimedia.org **429 限流**（不是 404）。
所以这一步逐个按 title 重问 iiurlwidth=1400，只接受 /thumb/ 的结果，拿不到就淘汰这个候选。"""
import json, re, time, pathlib, urllib.parse, urllib.request
API="https://commons.wikimedia.org/w/api.php"
UA="nordic-trip-2026/1.0 (personal trip planning; contact zouyang@adobe.com)"
def get(p):
    req=urllib.request.Request(API+"?"+urllib.parse.urlencode(p),headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=45) as r: return json.loads(r.read().decode())

picked=json.load(open("out_wiki_picked.json"))
titles=sorted({it["title"] for v in picked.values() for it in v["items"]})
res={}
for i in range(0,len(titles),20):
    chunk=titles[i:i+20]
    d=get({"action":"query","titles":"|".join("File:"+t for t in chunk),
           "prop":"imageinfo","iiprop":"url|size","iiurlwidth":1400,"format":"json"})
    for p in ((d.get("query") or {}).get("pages") or {}).values():
        ii=(p.get("imageinfo") or [{}])[0]
        t=p.get("title","").replace("File:","")
        tu=ii.get("thumburl")
        if tu and "/thumb/" in tu:
            res[t]={"src":tu,"w":ii.get("thumbwidth"),"h":ii.get("thumbheight")}
    time.sleep(0.4)
    print(f"  已解析 {min(i+20,len(titles))}/{len(titles)}",flush=True)

dropped=[]
for slug,v in picked.items():
    keep=[]
    for it in v["items"]:
        r=res.get(it["title"])
        if not r: dropped.append((slug,it["title"][:48])); continue
        it=dict(it); it.update(r); keep.append(it)
    v["items"]=keep
pathlib.Path("out_wiki_picked.json").write_text(json.dumps(picked,ensure_ascii=False,indent=1))
print(f"\n可用 {sum(len(v['items']) for v in picked.values())} 张；淘汰 {len(dropped)} 张（拿不到 /thumb/）")
for s,t in dropped: print("   ✗",s,t)
print("没图的地点：",[k for k,v in picked.items() if not v['items']] or "无")
