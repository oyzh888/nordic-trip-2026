#!/usr/bin/env python3
"""Senja 补充计算：每个站的「边际绕路」、错过末班渡轮的代价、渡轮航程、日落。
全部来自实测：OSRM（道路）· Entur（渡轮官方数据）· astral（日落）。"""
import datetime as dt, json, sys
import requests
from senja_route import PTS, KEYS, ENGINES, table, route, coords
from astral import LocationInfo
from astral.sun import sun
import zoneinfo

base = ENGINES[0]
dur, dist = table(base)
idx = {k: i for i, k in enumerate(KEYS)}
T = lambda a, b: dur[idx[a]][idx[b]] / 60
D = lambda a, b: dist[idx[a]][idx[b]] / 1000
R = json.load(open("out_senja_route.json"))
best = R["result"]["best"]["order"]
cost = lambda o: sum(T(a, b) for a, b in zip(o, o[1:]))
dcost = lambda o: sum(D(a, b) for a, b in zip(o, o[1:]))
out = {"best_order": best, "total_min": round(cost(best), 1), "total_km": round(dcost(best), 1)}

# 1) 每个停靠点的「边际绕路」= 有它的总驾驶时间 − 把它从顺序里拿掉之后的总时间
marg = {}
for k in best[1:-1]:
    o2 = [x for x in best if x != k]
    marg[k] = {"min": round(cost(best) - cost(o2), 1), "km": round(dcost(best) - dcost(o2), 1)}
out["marginal"] = marg
out["direct_start_botnhamn"] = {"min": round(T("start", "botnhamn"), 1), "km": round(D("start", "botnhamn"), 1)}
print("直接 Lanesbogen→Botnhamn:", out["direct_start_botnhamn"])
for k, v in marg.items():
    print(f"  拿掉 {PTS[k][0]:22} 省 {v['min']:5.1f} 分钟 {v['km']:5.1f} km")

# 2) 渡轮：Entur 实测航程 + 两岸码头 → 住处的陆路时间
H = {"ET-Client-Name": "nordic-trip-2026-steve", "Content-Type": "application/json"}
gql = '''query{ stopPlace(id:"NSR:StopPlace:63913"){ estimatedCalls(startTime:"2026-10-04T00:00:00+02:00",timeRange:86400,numberOfDepartures:10){
  aimedDepartureTime serviceJourney{ estimatedCalls{ quay{name} aimedArrivalTime aimedDepartureTime } } } } }'''
r = requests.post("https://api.entur.io/journey-planner/v3/graphql", json={"query": gql}, headers=H, timeout=40).json()
cross = []
for c in r["data"]["stopPlace"]["estimatedCalls"]:
    calls = c["serviceJourney"]["estimatedCalls"]
    dep = next(x for x in calls if x["quay"]["name"].startswith("Botnhamn"))
    arr = next(x for x in calls if x["quay"]["name"].startswith("Brensholmen"))
    a = dt.datetime.fromisoformat(dep["aimedDepartureTime"]); b = dt.datetime.fromisoformat(arr["aimedArrivalTime"])
    cross.append({"dep": a.strftime("%H:%M"), "arr": b.strftime("%H:%M"), "min": int((b - a).total_seconds() // 60)})
out["ferry"] = cross
print("渡轮:", cross)

HOME = (19.09603, 69.72227)   # Tromsø Airbnb（Tønsvikvegen 444 一带，房源页坐标，有一两百米模糊）
BREN = (18.031359, 69.607837)
BOTN = (PTS["botnhamn"][2], PTS["botnhamn"][1])
def rt(a, b):
    x = requests.get(f"{base}/route/v1/driving/{a[0]},{a[1]};{b[0]},{b[1]}", params={"overview": "false"}, timeout=60).json()["routes"][0]
    return {"min": round(x["duration"] / 60), "km": round(x["distance"] / 1000)}
out["after_ferry_to_home"] = rt(BREN, HOME)
out["miss_ferry_drive_around"] = rt(BOTN, HOME)
print("Brensholmen→住处", out["after_ferry_to_home"], "| 错过末班：Botnhamn→住处 陆路绕行", out["miss_ferry_drive_around"])
out["home"] = {"lat": HOME[1], "lon": HOME[0]}; out["brensholmen"] = {"lat": BREN[1], "lon": BREN[0]}

# 3) 日落 / 天黑
loc = LocationInfo("Senja", "Norway", "Europe/Oslo", 69.5, 17.6)
s = sun(loc.observer, date=dt.date(2026, 10, 4), tzinfo=zoneinfo.ZoneInfo("Europe/Oslo"))
out["sun"] = {k: s[k].strftime("%H:%M") for k in ("sunrise", "sunset", "dusk")}
print("日照:", out["sun"], "(dusk = 民用黄昏结束，之后基本全黑)")

# 4) Segla 山峰
try:
    g = requests.get("https://nominatim.openstreetmap.org/search", params={"q": "Segla Senja", "format": "json", "limit": 3},
                     headers={"User-Agent": "nordic-trip-2026/1.0 (zouyang@adobe.com)"}, timeout=20).json()
    out["segla"] = [{"name": x["display_name"][:70], "lat": float(x["lat"]), "lon": float(x["lon"]), "type": x.get("type")} for x in g]
    print("Segla:", out["segla"])
except Exception as e:
    print("segla ERR", e)
json.dump(out, open("out_senja_extra.json", "w"), ensure_ascii=False, indent=1)
