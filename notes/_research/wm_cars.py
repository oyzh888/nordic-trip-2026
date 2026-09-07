#!/usr/bin/env python3
"""从 Wikimedia Commons 找「我们真正订到的那四台车」的照片。

为什么用 Commons 而不是厂家官图：**官图是版权图，这个站是公开的。**
Commons 上的图带明确许可（CC-BY / CC-BY-SA / public domain），只要按要求署名就能用。
所以这个脚本除了拿 URL，还必须拿到 **license + artist**，否则那张图不能用。

用的是 MediaWiki API（不是爬页面）：generator=search 找文件 → prop=imageinfo 取
url / 尺寸 / extmetadata(LicenseShortName, Artist, LicenseUrl)。

Usage: python3 wm_cars.py out_cars_imgs.json
"""
import json, sys, urllib.parse, urllib.request, re, html

API = "https://commons.wikimedia.org/w/api.php"
UA = "nordic-trip-2026/1.0 (personal trip page; contact via github.com/oyzh888)"

# 只收这些许可 —— 其余（尤其 fair use / non-free）一律丢掉
OK_LIC = re.compile(r"^(cc[ -]?by([ -]sa)?([ -][0-9.]+)?|cc0|public domain|pd)", re.I)

QUERIES = {
 "defender":  ["Land Rover Defender 110 2020", "Land Rover Defender L663"],
 "explorer":  ["Ford Explorer EV 2024", "Ford Explorer electric Europe"],
 "eqs":       ["Mercedes-Benz EQS", "Mercedes-Benz EQS 580"],
 "macan":     ["Porsche Macan Electric 2024", "Porsche Macan EV"],
}

def api(**params):
    params.update(format="json", formatversion="2")
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()[:120]

def search(q, n=12):
    d = api(action="query", generator="search", gsrsearch=f"filetype:bitmap {q}",
            gsrnamespace=6, gsrlimit=n, prop="imageinfo",
            iiprop="url|size|extmetadata", iiurlwidth=1600)
    out = []
    for p in (d.get("query", {}).get("pages") or []):
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii: continue
        em = ii.get("extmetadata", {}) or {}
        lic = clean(em.get("LicenseShortName", {}).get("value"))
        if not OK_LIC.match(lic or ""): continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        if w < 900 or w/max(h, 1) < 1.15:        # 要横图、够大（当 hero 用）
            continue
        out.append(dict(title=p["title"], src=ii.get("thumburl") or ii["url"],
                        full=ii["url"], w=w, h=h, lic=lic,
                        author=clean(em.get("Artist", {}).get("value")) or "Unknown",
                        licurl=clean(em.get("LicenseUrl", {}).get("value")),
                        page=f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ','_'))}"))
    return out

res = {}
for key, qs in QUERIES.items():
    hits, seen = [], set()
    for q in qs:
        for h_ in search(q):
            if h_["title"] in seen: continue
            seen.add(h_["title"]); hits.append(h_)
    hits.sort(key=lambda x: -x["w"])
    res[key] = hits[:6]
    print(f"== {key}: {len(hits)} 张可用")
    for h_ in res[key]:
        print(f"   {h_['w']}x{h_['h']:<5} {h_['lic']:<14} {h_['title'][5:70]}")
    sys.stdout.flush()

json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print("\n→", sys.argv[1])
