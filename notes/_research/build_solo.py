#!/usr/bin/env python3
"""生成 site/solo/stays.js —— 订票页的住宿卡片（价 + 图 + 链接 + 「它的特点是什么」）。

🆕 2026-09-24 第三版（方案 B：伦敦 3 晚；Steve：「不用担心吵，找有意思的房子，平衡各方面；
   它们的特点是什么 —— 靠近好玩的地方还是住宿环境好？」）

每城 5 套 Airbnb + 4 家酒店，每一张卡都带一个「它好在哪」的标签：
  ⚖️ 平衡最好   四项平均分最高（位置 / 舒适 / 特色 / 性价比，见 abnb_rank.py）
  📍 离好玩的最近 到这城核心点的平均步行分钟最少
  🛋 住得最舒服  页面写了的设施最全（书桌 / 网速 / 空调 / 电梯 / 洗衣机）
  🏛 房子最有特色 老建筑 / 景观 / 设计（Claude 读描述打的分）
  💰 性价比      评分 4.85+、评论 20+ 里最便宜的
Airbnb 部分是**规则挑出来的**（改规则就改这里），酒店是手挑的四档（普通 / 位置 / 舒适或特色 / 奢华），
价格和图片一律来自实抓文件：
  out_abnb_rank_<city>.json      abnb_detail2.py → abnb_rank.py
  out_solo_bkcheap.json / out_solo_bksearch.json / out_bk_lon3.json   Booking 城市搜索（有房的）
  out_solo_hotel_imgs*.json      酒店页照片
  out_native_3n.json             Native Hyde Park 3 晚房价

Usage: python3 build_solo.py
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
SITE = HERE.parent.parent / "site" / "solo" / "stays.js"
EUR_USD = 1.13
DATES = {"nice": ("2026-10-06", "2026-10-10"), "lis": ("2026-10-10", "2026-10-14"),
         "lon": ("2026-10-14", "2026-10-17")}
NIGHTS = {"nice": 4, "lis": 4, "lon": 3}

himg = {}
for f in ("out_solo_hotel_imgs.json", "out_solo_hotel_imgs2.json"):
    p = HERE / f
    if p.exists():
        himg.update(json.load(open(p)))
pool = {"nice": [], "lis": [], "lon": []}
for f in ("out_solo_bkcheap.json", "out_solo_bksearch.json"):
    for r in json.load(open(HERE / f)):
        if r["city"] in ("nice", "lis"):
            pool[r["city"]] += r["cards"]
for r in json.load(open(HERE / "out_bk_lon3.json")):          # 伦敦只用 3 晚的价
    pool["lon"] += r["cards"]
unavail = {r["city"]: r["unavail_pct"] for r in json.load(open(HERE / "out_solo_bksearch.json"))}
unavail["lon"] = json.load(open(HERE / "out_bk_lon3.json"))[0]["unavail_pct"]


# ---------------- Airbnb：按规则挑 ----------------
def pick_airbnb(city):
    rows = json.load(open(HERE / f"out_abnb_rank_{city}.json"))
    # 硬伤：共用浴室 / 沙发床 / 地下室 / ≤20㎡（一晚要在里面坐 6 小时） —— 不许当「平衡最好」或「最舒服」（伦敦第一版就是这么挑出一个共用浴室的开间）
    for r in rows:
        txt = (r.get("con", "") + " " + r.get("desc", "")).lower()
        small = [float(x) for x in re.findall(r"(\d{2}(?:\.\d)?)\s*(?:m2|m²|sqm|平米|㎡)", txt)]
        r["flag"] = bool(re.search(r"共用|shared bath|沙发床|sofa bed|地下|basement|lower ground", txt)) or any(x <= 20 for x in small)
    med = sorted(r["total_eur"] for r in rows)[len(rows) // 2]
    cap = 1.6 * med                          # 任何一类都不挑超过中位价 1.6 倍的（「平衡」不是「最贵的那套」）
    good = [r for r in rows if float(r["rating"]) >= 4.8 and r["total_eur"] <= cap]
    clean = [r for r in good if not r["flag"]]
    solid = [r for r in clean if float(r["rating"]) >= 4.85 and (r.get("reviews") or 0) >= 20]
    rules = [
        ("⚖️ 平衡最好", sorted(clean, key=lambda r: -r["balanced"])),
        ("📍 离好玩的最近", sorted(clean, key=lambda r: (r["walk_mean"], -r["balanced"]))),
        ("🛋 住得最舒服", sorted(clean, key=lambda r: (-r["comfort"], -(r.get("reviews") or 0)))),
        ("🏛 房子最有特色", sorted(clean, key=lambda r: (-r["character"], -r["balanced"]))),
        ("💰 性价比", sorted(solid, key=lambda r: r["total_eur"])),
    ]
    out, used = [], set()
    for tag, lst in rules:
        r = next((x for x in lst if x["room"] not in used), None)
        if not r:
            continue
        used.add(r["room"])
        ci, co = DATES[city]
        walk = " · ".join(f"{k} {v} 分" for k, v in sorted(r["walk"].items(), key=lambda kv: kv[1])[:3])
        tags = [f"✅ {a}" for a in r["amen"]] or ["⚠️ 页面没写书桌/网速"]
        if not r.get("wifi_mbps"):
            tags.append("⚠️ 没写网速")
        out.append({
            "kind": "Airbnb", "pick": tag, "eur": r["total_eur"], "score": f"★{r['rating']}"
            + (f"（{r['reviews']} 条评论）" if r.get("reviews") else ""),
            "name": r["title"] if len(r["title"]) > 14 else r["search_title"], "note": f"<b>{r['hook']}</b>", "con": r["con"], "walk": f"🚶 步行：{walk}",
            "tags": tags, "imgs": r["photos"][:3], "lat": r["lat"], "lng": r["lng"],
            "url": f"https://www.airbnb.com/rooms/{r['room']}?check_in={ci}&check_out={co}&adults=1",
        })
    return out


# ---------------- 酒店：手挑四档 ----------------
def bk(city, prefix, pick, note, con="", vat=False, eur=None, url=None, tags=(), imgs=None):
    c = next(x for x in pool[city] if x["name"].startswith(prefix) and x["url"] and (eur or x["price_4n"]))
    u = url or c["url"]
    ci, co = DATES[city]
    more = himg.get(u) or []
    if "indigo-london" in u:        # 它酒店页的第一张图是一块灰色（9/24 实看）
        more = more[1:]
    loc = re.search(r"Location (\d\.\d)", c["raw"])
    return {"kind": "酒店", "pick": pick, "eur": eur or c["price_4n"],
            "score": f"{c['score']}/10" + (f" · 位置 {loc.group(1)}" if loc else ""),
            "name": c["name"].split(",")[0], "note": note, "con": con, "vat": vat, "tags": list(tags),
            "imgs": imgs or more[:3] or [c["img"]],
            "url": f"{u}?checkin={ci}&checkout={co}&group_adults=1&no_rooms=1&selected_currency=EUR"}


nat = json.load(open(HERE / "out_native_3n.json"))

HOTELS = {
    "nice": [
        bk("nice", "Hotel de Berne", "💰 普通酒店 · 最省心", "8.2 分，<b>Nice-Ville 火车站旁</b>（去 Villefranche 的车就从这走），到海边约 1.3 公里",
           tags=["✅ 免费取消"]),
        bk("nice", "Villa Saint Hubert", "🏛 有特色 · 安静", "<b>9.4 分</b> —— 这几天尼斯<b>还有房</b>的酒店里评分最高的，而且最便宜之一",
           con="离海 1.9 公里，去海边要坐车", tags=["✅ 免费取消"]),
        bk("nice", "Hotel Nap", "📍 离好玩的最近", "位置 9.7，<b>Masséna 广场旁</b>，海和老城都在 5 分钟内", con="这个价是单人间，房间小"),
        bk("nice", "Maison Albar", "🌟 奢华 · 彻底躺平", "五星，<b>正对海滩</b>，Junior Suite 有独立起居区，能好好工作"),
    ],
    "lis": [
        bk("lis", "Limehome Lisbon Calçada", "💰 普通 · 公寓式", "整套开间（有小厨房），自助入住，8.2 分",
           con="离 Baixa 约 1.5 公里，靠 Santa Apolónia 车站"),
        bk("lis", "Albergaria Senhora do Monte", "🏛 有特色 · 城市最美观景台旁", "Graça 区，<b>就在 Senhora do Monte 观景台边上</b>，看全城落日；28 路电车门口过",
           con="在山顶，回住处要上坡（有电车）", tags=["✅ 免费取消"]),
        bk("lis", "Hotel Metropole", "📍 离好玩的最近", "<b>Rossio 广场正中间</b>，老城、河边、地铁都在门口，含早餐"),
        bk("lis", "Wilde Aparthotels", "🛋 住得最舒服 · 可零成本占位", "9.2 分，整套开间带小厨房和桌子，在平路一侧",
           tags=["✅ 免费取消", "✅ 到店付款"]),
    ],
    "lon": [
        bk("lon", "Stylotel", "💰 普通酒店", "Paddington 站走路 3 分钟，位置 9.5，设计感小酒店", con="房间小（伦敦普遍）", vat=True),
        bk("lon", "Roseate House", "🏛 有特色 · 精品", "<b>8.7 分</b>，维多利亚式联排别墅改的精品酒店，Hyde Park 走路 5 分钟", vat=True),
        {"kind": "酒店", "pick": "🛋 住得最舒服 · 整套公寓", "name": "Native Hyde Park", "eur": 854, "score": "", "vat": True,
         "note": "整套开间，有厨房和洗碗机。<b>免费取消到 10/12、10/10 之前不扣钱</b>",
         "con": "", "tags": ["✅ 免费取消", "✅ 整套公寓"], "imgs": nat["imgs"][:3], "url": nat["book_url"]},
        bk("lon", "Mercure London Hyde Park", "📍 大连锁 · 稳", "8.1 分，Paddington 站和 Hyde Park 之间", vat=True),
    ],
}

META = {
    "nice": ("🇫🇷 尼斯", "10/6 → 10/10 · 4 晚"),
    "lis": ("🇵🇹 里斯本", "10/10 → 10/14 · 4 晚"),
    "lon": ("🇬🇧 伦敦", "10/14 → 10/17 · 3 晚"),
}

CITIES = []
for key in ("nice", "lis", "lon"):
    abs_ = pick_airbnb(key)
    hs = HOTELS[key]
    for o in abs_ + hs:
        o["usd"] = round(o["eur"] * EUR_USD * (1.2 if o.get("vat") else 1))
    a_min = min(o["usd"] for o in abs_)
    h_min = min(o["usd"] for o in hs)
    CITIES.append({
        "key": key, "city": META[key][0], "when": META[key][1], "sold": unavail[key],
        "verdict": (f"Airbnb 最低 <b>${a_min:,}</b>，普通酒店最低 <b>${h_min:,}</b>（{NIGHTS[key]} 晚总价）—— "
                    + (f"酒店贵 <b>${h_min - a_min:,}</b>。" if h_min > a_min else f"<b>酒店反而便宜 ${a_min - h_min:,}</b>。")
                    + ("（伦敦酒店按另加 20% 增值税算的；如果 Booking 标价已含税，酒店还会再便宜）" if key == "lon" else "")),
        "opts": abs_ + hs,
    })

SITE.write_text("/* 由 notes/_research/build_solo.py 生成，别手改 */\nconst STAYS = "
                + json.dumps(CITIES, ensure_ascii=False, indent=1) + ";\n")
print("wrote", SITE)
for c in CITIES:
    print(c["key"], c["verdict"])
    for o in c["opts"]:
        print("  ", o["pick"], o["kind"], o["eur"], o["usd"], o["name"][:40])
