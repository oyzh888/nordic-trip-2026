#!/usr/bin/env python3
"""第二轮：给四台车找**好看**的 CC 授权照片。

第一轮的问题（Steve 指出的）：
  ① 特罗姆瑟那台是 **EQS SUV（X296）**，我却按轿车 V297 挑了图 —— 车都挑错了；
  ② 有几张不好看：车展室内摊位、局部特写、背景杂乱的路边照。

「好看」没法完全自动判定，所以这一轮的分工是：脚本负责**筛出合法且构图可能好**的候选
（自由许可 · 横图 · 够大 · 标题不像室内车展/内饰/局部），然后我把候选拼成一张联系表
（contact sheet）用眼睛挑。评分只是排序，不是结论。

Usage: python3 wm_cars2.py out_cars2.json
"""
import json, re, sys, urllib.parse, urllib.request, html

API = "https://commons.wikimedia.org/w/api.php"
UA = "nordic-trip-2026/1.0 (personal trip page; github.com/oyzh888)"
OK_LIC = re.compile(r"^(cc[ -]?by([ -]sa)?([ -][0-9.]+)?|cc0|public domain|pd)", re.I)
# 这些词基本等于「不好看」：室内车展摊位、内饰、局部、仪表台、后备箱、充电口特写
UGLY = re.compile(r"interior|dashboard|cockpit|seat|wheel\b|badge|logo|detail|engine|trunk|boot|"
                  r"charging.?port|rear light|headlight|IAA|Salon|Motor.?Show|Auto.?Show|"
                  r"Messe|stand|indoor|museum", re.I)
# 这些词通常意味着「在外面、有环境、构图完整」
PRETTY = re.compile(r"front|three.?quarter|3.?4|side|profile|road|street|nature|mountain|snow|"
                    r"landscape|outdoor|parked|driving", re.I)

QUERIES = {
 "defender": ["Land Rover Defender L663", "Land Rover Defender 110"],
 "explorer": ["Ford Explorer EV", "Ford Explorer electric"],
 # ← Steve 给的准确型号：**EQS SUV（X296）**，不是轿车 V297。第一轮我挑错了车。
 "eqs":      ["Mercedes-Benz EQS SUV", "Mercedes-Benz X296"],
 "macan":    ["Porsche Macan Electric", "Porsche Macan 2024"],
}

_last = [0.0]
def api(**p):
    """节流 + 429 退避 —— Commons API 会限流，第一版没管这个，跑到第二台车就 429 挂了。"""
    import time
    p.update(format="json", formatversion="2")
    url = API + "?" + urllib.parse.urlencode(p)
    for attempt in range(5):
        gap = 1.3 - (time.time() - _last[0])
        if gap > 0: time.sleep(gap)
        _last[0] = time.time()
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(r, timeout=30) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4: raise
            wait = 3 * (attempt + 1)
            print(f"   (429，等 {wait}s 重试)", flush=True); time.sleep(wait)

def clean(s): return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()[:110]

def search(q, n=14):
    d = api(action="query", generator="search", gsrsearch=f"filetype:bitmap {q}", gsrnamespace=6,
            gsrlimit=n, prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=1600)
    out = []
    for p in (d.get("query", {}).get("pages") or []):
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii: continue
        em = ii.get("extmetadata", {}) or {}
        lic = clean(em.get("LicenseShortName", {}).get("value"))
        if not OK_LIC.match(lic or ""): continue
        w, h = ii.get("width", 0), ii.get("height", 0)
        ar = w / max(h, 1)
        if w < 1400 or ar < 1.3: continue            # 要够大的横图，当大图用
        t = p["title"][5:]
        score = (2 if PRETTY.search(t) else 0) - (3 if UGLY.search(t) else 0) + min(w / 4000, 2) \
                + (1 if 1.45 <= ar <= 1.85 else 0)  # 接近 3:2 / 16:9 的最好排
        out.append(dict(title=t, src=ii.get("thumburl") or ii["url"], full=ii["url"], w=w, h=h,
                        ar=round(ar, 2), lic=lic, score=round(score, 2),
                        author=clean(em.get("Artist", {}).get("value")) or "Unknown",
                        page=f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ','_'))}"))
    return out

res = {}
for k, qs in QUERIES.items():
    seen, hits = set(), []
    for q in qs:
        for h_ in search(q):
            if h_["title"] in seen: continue
            seen.add(h_["title"]); hits.append(h_)
    hits.sort(key=lambda x: -x["score"])
    res[k] = hits[:8]
    print(f"== {k}: 候选 {len(hits)} → 取前 {len(res[k])}")
    for i, h_ in enumerate(res[k]):
        print(f"   [{i}] {h_['score']:>5} {h_['w']}x{h_['h']} ar{h_['ar']} {h_['lic']:<13} {h_['title'][:66]}")
    sys.stdout.flush()
json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
print("\n→", sys.argv[1])
