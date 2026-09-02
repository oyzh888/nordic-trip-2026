#!/usr/bin/env python3
"""从 Commons 候选里挑图。踩过的三个坑都在这里修掉：
 ① 标题里带 360 / panorama / compressed 的是畸变全景图，当主图很难看 → 降权
 ② thumburl 有时是「原图 + ?utm_*」（原图比请求尺寸还小），那个 URL 加载会失败 → 清掉 query
 ③ 只按标题首字匹配会误命中（narvik → 一艘德国驱逐舰）→ 标题必须命中关键词白名单
"""
import json, re, pathlib, unicodedata

w1 = json.load(open("out_wiki.json"))
w2 = json.load(open("out_wiki2.json"))
merged = {}
for src in (w1, w2):
    for k, v in src.items():
        if not v.get("items"): continue
        merged.setdefault(k, {"query": v.get("query"), "items": []})
        merged[k]["items"] += v["items"]

def norm(s): return unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()

KEY = {
 "oslo":["oslo","fjord"],"hallgrim":["hallgrim"],"rvk":["reykjavik"],
 "sunvoyager":["solfar","sun voyager","voyager","jubilaum"],
 "seljalands":["seljaland"],"skogafoss":["skogafoss","skogar"],"dyrholaey":["dyrholaey"],
 "reynisfjara":["reynis"],"jokulsarlon":["jokulsarlon","jokulsa"],
 "vestrahorn":["stokksnes","vestrahorn"],"svartifoss":["svartifoss"],"fjallsarlon":["fjallsarlon"],
 "gullfoss":["gullfoss"],"geysir":["strokkur","geysir"],
 "thingvellir":["thingvellir","almannagja","pingvellir"],
 "bluelagoon":["lagune","lagoon","blaue"],"gunnuhver":["gunnuhver"],"brimketill":["brimketill"],
 "bridge2cont":["bridge","continent"],"reykjanesviti":["reykjanes","valahnuk"],
 "kirkjufell":["kirkjufell"],"aurora_is":["aurora","northern light"],
 "lofoten":["lofoten","austnesfjord"],"henningsvaer":["henningsvaer"],
 "reine":["reine","sakriso","andoy"],"hamnoy":["hamnoy","eliassen"],
 "reinebringen":["reinebringen"],"sakrisoy":["sakriso"],"haukland":["haukland"],
 "narvik":["ofotfjord","herjangsfjord","narvik"],"tromso":["tromso"],
 "arcticcath":["tromsdalen","ishavskatedralen","arctic cathedral"],
 "fjellheisen":["storsteinen","fjellheisen"],"aurora_no":["aurora"],
 "senja":["senja","mefjord","segla"],"segla":["segla","hesten"],"tungeneset":["tungeneset"],
 "bergsbotn":["bergsbotn","bergsfjord"],"ersfjord":["ersfjord"],"rorbu":["nusfjord","rorbu"],
 "aurora_lof":["aurora"],"e10":["e10","lofast"],"skagsanden":["flakstad","skagsanden"],
}
BAD_TITLE = re.compile(r"(360|panorama|panoram|compressed version|stitch)", re.I)

def clean_src(u):
    # ② 去掉 ?utm_* 之类的追踪参数（带着会 404/失败）
    return re.sub(r"\?(utm_|.*imageinfo).*$", "", u or "")

def score(it):
    w, h = it.get("w") or 0, it.get("h") or 1
    r = w / h if h else 0
    s = 0.0
    if 1.25 <= r <= 2.0: s += 3.0            # 最适合当主图的构图
    elif 1.0 <= r < 1.25 or 2.0 < r <= 2.4: s += 1.5
    elif r < 1.0: s += 0.4                    # 竖图（瀑布可以用）
    else: s -= 0.5                            # 超宽全景
    if BAD_TITLE.search(it.get("title") or ""): s -= 4.0   # ①
    s += min(w, 2000) / 4000
    return -s

def bonus_for(slug, it, keys):
    """标题开头就是地名的，比「某只海豹恰好在冰河湖」更适合当代表图。"""
    t = norm(it.get("title") or "")
    return 1.6 if any(t.startswith(k) for k in keys) else 0.0

picked, rejected = {}, []
for slug, v in merged.items():
    keys = KEY.get(slug, [slug])
    cands = []
    seen = set()
    for it in v["items"]:
        if not any(k in norm(it["title"]) for k in keys):      # ③
            rejected.append((slug, it["title"][:52])); continue
        it = dict(it); it["src"] = clean_src(it["src"])
        if it["src"] in seen: continue
        seen.add(it["src"]); cands.append(it)
    cands.sort(key=lambda it: score(it) - bonus_for(slug, it, keys))
    picked[slug] = {"query": v.get("query"), "items": cands[:3]}

# 跨地点去重：同一张图不要在两个地点重复出现（senja 和 segla 原来就撞了同一张）
used = set()
for slug in list(picked):
    keep = []
    for it in picked[slug]["items"]:
        if it["src"] in used: continue
        used.add(it["src"]); keep.append(it)
    picked[slug]["items"] = keep

pathlib.Path("out_wiki_picked.json").write_text(json.dumps(picked, ensure_ascii=False, indent=1))
print(f"{len(picked)} 个地点 · 共 {sum(len(v['items']) for v in picked.values())} 张 · 因标题不匹配剔除 {len(rejected)} 张")
print("没有可用图的地点：", [k for k,v in picked.items() if not v["items"]] or "无")
for k in sorted(picked):
    it = picked[k]["items"]
    if it: print(f"  {k:<14} {it[0]['w']}x{it[0]['h']}  {it[0]['title'][:60]}")
