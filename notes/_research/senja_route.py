#!/usr/bin/env python3
"""Senja 一日自驾：用真实道路网重新排顺序，并和用户手里那张图的顺序对比。

为什么要重做（Steve 2026-10-04）：图上的时间表自相矛盾（Bergsbotn 停到 14:00，Ersfjordstranda 却写 14:23 到，
而图上标的路段是 45 分钟），地址也对不上（Fjordgårdveien 21 查不到）。所以这里不信图，只信道路网：
  1. 坐标：OSM Nominatim 地理编码（9/4 实查），Fjordgård 用村中心
  2. 行驶时间 / 距离：OSRM 的 table（全部两两组合），不是直线
  3. 顺序：起点和终点（渡轮码头）固定，中间 6 个点穷举 720 种排列，取总驾驶时间最短
  4. 「绕路」的量化：把整条路线按 100 m 一个点铺开，数有多少公里和前面已经走过的路重合（= 原路折返）
两个独立的路由引擎（router.project-osrm.org 和 routing.openstreetmap.de）互相核对总时间。

Usage: python3 senja_route.py <out.json>
"""
import itertools
import json
import math
import sys

import requests

PTS = {   # key: (名字, lat, lon)
    "start": ("Lanesbogen（你最后一次的位置）", 69.3426, 17.9373),
    "bergsbotn": ("Bergsbotn 观景台", 69.4231, 17.5038),
    "ersfjord": ("Ersfjordstranda 海滩", 69.4789, 17.3946),
    "tungeneset": ("Tungeneset 恶魔之齿", 69.4870, 17.3330),
    "mefjordvaer": ("Mefjordvær 渔村", 69.5186, 17.4382),
    "fjordgard": ("Fjordgård（Segla 山脚）", 69.5091, 17.6283),
    "husoy": ("Husøy 彩色渔村", 69.5442, 17.6637),
    "botnhamn": ("Botnhamn 渡轮码头", 69.5069, 17.9078),
}
MID = ["bergsbotn", "ersfjord", "tungeneset", "mefjordvaer", "fjordgard", "husoy"]
IMAGE_ORDER = ["start", "bergsbotn", "ersfjord", "tungeneset", "mefjordvaer", "fjordgard", "husoy", "botnhamn"]
ENGINES = ["https://router.project-osrm.org", "https://routing.openstreetmap.de/routed-car"]
KEYS = list(PTS)


def coords(keys):
    return ";".join(f"{PTS[k][2]},{PTS[k][1]}" for k in keys)


def table(base):
    r = requests.get(f"{base}/table/v1/driving/{coords(KEYS)}", params={"annotations": "duration,distance"}, timeout=60).json()
    assert r["code"] == "Ok", r
    return r["durations"], r["distances"]


def route(base, keys, steps=False):
    r = requests.get(f"{base}/route/v1/driving/{coords(keys)}",
                     params={"overview": "full", "geometries": "geojson", "steps": str(steps).lower()}, timeout=60).json()
    assert r["code"] == "Ok", r
    return r["routes"][0]


def hav(a, b):
    R = 6371000
    p = math.pi / 180
    dl, dn = (b[1] - a[1]) * p, (b[0] - a[0]) * p
    h = math.sin(dn / 2) ** 2 + math.cos(a[1] * p) * math.cos(b[1] * p) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def densify(line, step=100):
    out = [line[0]]
    for a, b in zip(line, line[1:]):
        d = hav(a, b)
        n = max(1, int(d // step))
        for i in range(1, n + 1):
            out.append([a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n])
    return out


def overlap_km(legs, tol=45):
    """整条路线里，有多少公里是和「之前已经走过」的路重合的（原路折返 / 走回头路）。"""
    seen, grid, back, total = [], {}, 0.0, 0.0
    cell = 0.0006   # ≈ 65 m 纬度；经度在 69.5° 下约 23 m 每 0.001° 不到 → 查邻居 3×3 够用

    def key(p):
        return (int(p[1] / cell), int(p[0] / (cell * 2.2)))
    for li, leg in enumerate(legs):
        pts = densify(leg)
        for pi, p in enumerate(pts):
            # 本段开头 300 m 不算（刚从上一个停靠点出来，和上一段的结尾天然贴着）
            near = False
            if li > 0 and pi > 3:
                kx, ky = key(p)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for (q, lj) in grid.get((kx + dx, ky + dy), []):
                            if lj < li and hav(p, q) < tol:
                                near = True
            if pi:
                seg = hav(pts[pi - 1], p)
                total += seg
                back += seg if near else 0
        for p in pts:
            grid.setdefault(key(p), []).append((p, li))
    return back / 1000, total / 1000


def main():
    out = {"points": {k: {"name": v[0], "lat": v[1], "lon": v[2]} for k, v in PTS.items()}, "engines": {}}
    tabs = {}
    for base in ENGINES:
        try:
            tabs[base] = table(base)
        except Exception as e:
            print("ENGINE FAIL", base, e)
    base0 = ENGINES[0]
    dur, dist = tabs[base0]
    idx = {k: i for i, k in enumerate(KEYS)}

    def cost(order, M):
        return sum(M[idx[a]][idx[b]] for a, b in zip(order, order[1:]))

    # 穷举
    allp = []
    for perm in itertools.permutations(MID):
        order = ["start", *perm, "botnhamn"]
        allp.append((cost(order, dur), cost(order, dist) / 1000, order))
    allp.sort()
    best = allp[0]
    img = next(x for x in allp if x[2] == IMAGE_ORDER)
    print(f"穷举 {len(allp)} 种顺序")
    print("最短 ", round(best[0] / 60), "分钟", round(best[1]), "km", best[2])
    print("原图 ", round(img[0] / 60), "分钟", round(img[1]), "km", img[2])
    for c, d, o in allp[:5]:
        print("   top", round(c / 60), "min", round(d), "km", "→".join(o[1:-1]))
    # 两个引擎互相核对
    for base, (du, di) in tabs.items():
        print(f"  {base[8:30]:22} 最优顺序总时间 {round(cost(best[2], du) / 60)} 分钟 / 原图顺序 {round(cost(IMAGE_ORDER, du) / 60)} 分钟")

    def leg_table(order):
        rows = []
        for a, b in zip(order, order[1:]):
            rows.append({"from": a, "to": b, "min": round(dur[idx[a]][idx[b]] / 60, 1), "km": round(dist[idx[a]][idx[b]] / 1000, 1)})
        return rows

    res = {}
    for name, order in (("best", best[2]), ("image", IMAGE_ORDER)):
        legs, geoms = [], []
        for a, b in zip(order, order[1:]):
            rt = route(base0, [a, b], steps=True)
            legs.append(rt["geometry"]["coordinates"])
            names = []
            for s in rt["legs"][0]["steps"]:
                nm = (s.get("ref") or s.get("name") or "").strip()
                if nm and (not names or names[-1] != nm):
                    names.append(nm)
            geoms.append({"from": a, "to": b, "coords": [[round(x, 5), round(y, 5)] for x, y in rt["geometry"]["coordinates"]],
                          "roads": names, "min": round(rt["duration"] / 60, 1), "km": round(rt["distance"] / 1000, 1)})
        back, tot = overlap_km(legs)
        res[name] = {"order": order, "legs": geoms, "minutes": round(sum(g["min"] for g in geoms)),
                     "km": round(sum(g["km"] for g in geoms), 1), "backtrack_km": round(back, 1), "path_km": round(tot, 1)}
        print(f"[{name}] 驾驶 {res[name]['minutes']} 分钟 · {res[name]['km']} km · 其中走回头路 {res[name]['backtrack_km']} km")
        for g in geoms:
            print(f"     {g['from']:11}→{g['to']:11} {g['min']:5.1f} 分 {g['km']:5.1f} km  {' > '.join(g['roads'][:5])}")
    out["result"] = res
    out["alternatives"] = [{"min": round(c / 60), "km": round(d), "order": o[1:-1]} for c, d, o in allp[:6]]
    out["engines_check"] = {b[8:40]: {"best_min": round(cost(best[2], du) / 60), "image_min": round(cost(IMAGE_ORDER, du) / 60)}
                            for b, (du, di) in tabs.items()}
    json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
