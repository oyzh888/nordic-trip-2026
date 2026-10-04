#!/usr/bin/env python3
"""生成 site/senja/data.js —— Senja 一日自驾页的全部数据。

输入（都是 2026-10-04 实测，脚本见同目录）：
  out_senja_route.json   senja_route.py：OSRM 道路网，720 种顺序穷举 + 每段几何
  out_senja_extra.json   senja_extra.py：每站边际绕路 · 渡轮航程（Entur）· 日落 · 错过末班的代价
  out_entur_ferry.json   Entur 官方实时班次（Botnhamn / Brensholmen 两岸）
输出：
  site/senja/data.js     页面用；行驶时间 / 公里全部来自 OSRM table，几何来自 OSRM route

三个「预设线路」：
  A 推荐 5 站   B 加 Husøy 共 6 站（有判断点）   C 赶时间 3 站
缺的几何（如 fjordgard→botnhamn 直达）现场向 OSRM 要，不自己拼。
"""
import json
import pathlib

import requests

from senja_route import ENGINES, KEYS, PTS, table

HERE = pathlib.Path(__file__).parent
SITE = HERE.parent.parent / "site" / "senja" / "data.js"
R = json.load(open(HERE / "out_senja_route.json"))
X = json.load(open(HERE / "out_senja_extra.json"))
E = json.load(open(HERE / "out_entur_ferry.json"))
BASE = ENGINES[0]

dur, dist = table(BASE)
idx = {k: i for i, k in enumerate(KEYS)}
geom = {}
for name in ("best", "image"):
    for leg in R["result"][name]["legs"]:
        geom[f"{leg['from']}>{leg['to']}"] = leg

PRESETS = [
    {"id": "A", "name": "推荐 · 5 站", "order": ["start", "bergsbotn", "tungeneset", "ersfjord", "mefjordvaer", "fjordgard", "botnhamn"],
     "desc": "Bergsbotn → Tungeneset → Ersfjordstranda → Mefjordvær → Fjordgård → 码头。Husøy 不去（它一个站就要多开 24 分钟）。"},
    {"id": "B", "name": "6 站 · 含 Husøy", "order": ["start", "bergsbotn", "tungeneset", "ersfjord", "mefjordvaer", "fjordgard", "husoy", "botnhamn"],
     "desc": "在推荐线路最后多加 Husøy。只有「到 Fjordgård 时还来得及」才走这条 —— 看下表的「最晚离开」。"},
    {"id": "C", "name": "赶时间 · 3 站", "order": ["start", "tungeneset", "ersfjord", "fjordgard", "botnhamn"],
     "desc": "只留最出片的三个：Tungeneset、Ersfjordstranda、Fjordgård(Segla)。省掉 Bergsbotn 和 Mefjordvær。"},
]


def ensure(a, b):
    k = f"{a}>{b}"
    if k not in geom:
        o = PTS[a], PTS[b]
        r = requests.get(f"{BASE}/route/v1/driving/{o[0][2]},{o[0][1]};{o[1][2]},{o[1][1]}",
                         params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=60).json()["routes"][0]
        roads = []
        for s in r["legs"][0]["steps"]:
            nm = (s.get("ref") or s.get("name") or "").strip()
            if nm and (not roads or roads[-1] != nm):
                roads.append(nm)
        geom[k] = {"from": a, "to": b, "coords": r["geometry"]["coordinates"], "roads": roads}
    return geom[k]


legs = {}
for p in PRESETS:
    tot_m = tot_k = 0
    for a, b in zip(p["order"], p["order"][1:]):
        g = ensure(a, b)
        m, k = dur[idx[a]][idx[b]] / 60, dist[idx[a]][idx[b]] / 1000     # 时间 / 公里一律用 table（和穷举同一口径）
        legs[f"{a}>{b}"] = {"min": round(m, 1), "km": round(k, 1), "roads": g["roads"][:6],
                            "coords": [[round(x, 4), round(y, 4)] for x, y in g["coords"]]}
        tot_m += m
        tot_k += k
    p["drive_min"] = round(tot_m)
    p["drive_km"] = round(tot_k, 1)
    print(p["id"], p["name"], "驾驶", p["drive_min"], "分钟", p["drive_km"], "km")

# Brensholmen → 住处（渡轮之后）的几何，简化即可
home, bren = X["home"], X["brensholmen"]
hr = requests.get(f"{BASE}/route/v1/driving/{bren['lon']},{bren['lat']};{home['lon']},{home['lat']}",
                  params={"overview": "simplified", "geometries": "geojson"}, timeout=60).json()["routes"][0]

NOTE = {   # 每站一句话（道路编号来自 OSRM 的路名；「支线」= 要进去再原路出来）
    "start": "图上你最后一次的位置（12:55）。从这里出发；如果你已经开出一段，把出发时间往前调。",
    "bergsbotn": "44 米长的观景平台，俯瞰 Bergsfjorden 峡湾。主路旁的一个小绕路（约 11 分钟）。",
    "tungeneset": "木栈道通到海边岩石，拍对岸「恶魔之齿」山峰的经典位置。就在主路 Fv862 上。",
    "ersfjord": "白沙滩 + 群山。在 Tungeneset 之后 3 公里，同一条路，顺路。",
    "mefjordvaer": "渔村，码头很上镜。支线 Fv7868：要进去再原路出来，这一站总共多花约 15 分钟。",
    "fjordgard": "Segla 山脚的村子（Segla / Hesten 徒步起点），拍 Segla 的位置。支线 Fv7884，多花约 12 分钟。无人机起飞点按原图。",
    "husoy": "小岛上的彩色渔村，堤坝路连接。支线 Fv7886：这一站要多开约 24 分钟 —— 全线最贵的一站。",
    "botnhamn": "渡轮码头（Torghatten Nord 181 线 → Brensholmen）。今天周日最后一班 18:00。",
}
pts = {}
for k, v in R["points"].items():
    pts[k] = {"name": v["name"], "lat": v["lat"], "lon": v["lon"], "note": NOTE[k],
              "stay": {"bergsbotn": 15, "tungeneset": 20, "ersfjord": 20, "mefjordvaer": 15, "fjordgard": 20, "husoy": 15}.get(k, 0),
              "marginal": X["marginal"].get(k)}

data = {
    "built": "2026-10-04",
    "points": pts, "presets": PRESETS, "legs": legs,
    "ferry": {"departures": [c["dep"] for c in X["ferry"]], "arrivals": [c["arr"] for c in X["ferry"]], "cross_min": X["ferry"][0]["min"],
              "from_bren": [c["aimedDepartureTime"][11:16] for c in E["Brensholmen"]["data"]["stopPlace"]["estimatedCalls"]],
              "bren": bren, "home": home, "after_min": X["after_ferry_to_home"]["min"], "after_km": X["after_ferry_to_home"]["km"],
              "miss_min": X["miss_ferry_drive_around"]["min"], "miss_km": X["miss_ferry_drive_around"]["km"],
              "home_line": [[round(x, 4), round(y, 4)] for x, y in hr["geometry"]["coordinates"]]},
    "sun": X["sun"], "segla": next((s for s in X.get("segla", []) if s["type"] == "peak"), None),
    "direct_min": X["direct_start_botnhamn"]["min"], "direct_km": X["direct_start_botnhamn"]["km"],
    "image": {"min": R["result"]["image"]["minutes"], "km": R["result"]["image"]["km"],
              "best_min": R["result"]["best"]["minutes"], "best_km": R["result"]["best"]["km"]},
    "alts": R["alternatives"][:3],
    "engines": R["engines_check"],
}
SITE.parent.mkdir(parents=True, exist_ok=True)
SITE.write_text("/* 由 notes/_research/senja_build.py 生成，别手改 */\nconst SENJA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
print("wrote", SITE, round(SITE.stat().st_size / 1024), "KB")
