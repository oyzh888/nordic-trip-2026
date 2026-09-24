#!/usr/bin/env python3
"""「普通酒店」那一档：Booking 城市搜索按价格从低到高，只要评分 8+ 的酒店。

Steve 问「酒店是不是都比 Airbnb 贵很多？是不是没考虑普通酒店？」——
上一轮 solo_bksearch.py 用的是 Booking 默认排序（Top Picks），前 40 张卡里偏中高档。
这里换成 order=price + review_score≥8，专门看「便宜又不差」的那一截到底多少钱。
Usage: python3 solo_bkcheap.py <out.json>
"""
import json
import sys

from playwright.sync_api import sync_playwright

from solo_bksearch import run
from solo_pics import UA

FLT = "ht_id%3D204%3Breview_score%3D80&order=price"
JOBS = [("nice", "-1454990", "city", "2026-10-06", "2026-10-10", FLT),
        ("lis", "-2167973", "city", "2026-10-10", "2026-10-14", FLT),
        ("lon", "43", "district", "2026-10-14", "2026-10-17", FLT)]
res = []
with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    ctx = br.new_context(user_agent=UA, locale="en-US", viewport={"width": 1440, "height": 1100})
    for j in JOBS:
        r = run(ctx, *j)
        print(j[0], r["found"], len(r["cards"]), flush=True)
        res.append(r)
        json.dump(res, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
    br.close()
