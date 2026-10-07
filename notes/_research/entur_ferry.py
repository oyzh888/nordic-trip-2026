#!/usr/bin/env python3
"""查某一天 Botnhamn ⇄ Brensholmen 渡轮的官方班次（Entur：挪威国家公共交通数据平台，含实时、含取消）。

为什么单独一个脚本：Senja 那天的整条线路是从「末班船」倒推的，而 Gemini 联网搜索给出的班次是错的
（多出 20:00、21:30 两班不存在的船）。班次必须来自官方数据，并且要能重算 ——
out_entur_ferry.json 就是这个脚本在 2026-10-04 的输出。

Usage: python3 entur_ferry.py [YYYY-MM-DD] [out.json]
       换别的航线：改下面 STOPS（站点 id 用 geocoder 查：
       https://api.entur.io/geocoder/v1/autocomplete?text=<站名>&size=6 ，取 NSR:StopPlace:…）
Entur 要求带 ET-Client-Name 请求头（随便起个名字，别留空）。
"""
import datetime as dt
import json
import sys

import requests

STOPS = {"Botnhamn": "NSR:StopPlace:63913", "Brensholmen": "NSR:StopPlace:63915"}
H = {"ET-Client-Name": "nordic-trip-2026", "Content-Type": "application/json"}
GQL = """query($id:String!,$t:DateTime!){ stopPlace(id:$id){ name
  estimatedCalls(startTime:$t, timeRange:86400, numberOfDepartures:30, includeCancelledTrips:true){
    aimedDepartureTime expectedDepartureTime realtime cancellation
    destinationDisplay{frontText}
    serviceJourney{ line{publicCode name transportMode operator{name}} } } } }"""


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    out = sys.argv[2] if len(sys.argv) > 2 else "out_entur_ferry.json"
    res = {}
    for name, sid in STOPS.items():
        r = requests.post("https://api.entur.io/journey-planner/v3/graphql",
                          json={"query": GQL, "variables": {"id": sid, "t": f"{day}T00:00:00+02:00"}},   # 10 月下旬前挪威是 UTC+2
                          headers=H, timeout=40).json()
        res[name] = r
        calls = ((r.get("data") or {}).get("stopPlace") or {}).get("estimatedCalls") or []
        print(f"== {name} {day}: {len(calls)} 班")
        for c in calls:
            print("  ", c["aimedDepartureTime"][11:16], "→", c["expectedDepartureTime"][11:16],
                  "实时" if c["realtime"] else "    ", "取消" if c["cancellation"] else "", c["destinationDisplay"]["frontText"])
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
