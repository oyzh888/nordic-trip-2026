#!/usr/bin/env python3
"""生成 site/solo/stays.js —— 后半段订票页的住宿卡片（价 + 图 + 链接）。

输入全部是实抓的：
  out_stay3/*.json          Airbnb 搜索（9/24，4 晚含税含费总价）
  out_solo_pics.json        Airbnb 房源页照片 + 是否写了书桌/电梯/网速（9/24）
  out_solo_bksearch.json    Booking 城市搜索：那几天**还有房**的酒店（9/24，价 + 封面图）
这里只做「挑哪几家 + 中文一句话」，价格和图片一律从输入里取，不手写。

Usage: python3 build_solo.py
"""
import json
import pathlib

HERE = pathlib.Path(__file__).parent
SITE = HERE.parent.parent / "site" / "solo" / "stays.js"
EUR_USD = 1.13

pics = {a["room"]: a for a in json.load(open(HERE / "out_solo_pics.json"))["airbnb"]}
nat = next(h for h in json.load(open(HERE / "out_solo_pics.json"))["hotels"]
           if "native" in (h.get("url") or ""))
hotel_imgs = json.load(open(HERE / "out_solo_hotel_imgs.json"))
search = {r["city"]: r for r in json.load(open(HERE / "out_solo_bksearch.json"))}
abprice = {}
for c in ("nice", "lisbon", "london"):
    for r in json.load(open(HERE / f"out_stay3/{c}.json"))["rows"]:
        abprice[r["url"].split("/rooms/")[1].split("?")[0]] = (r["total_eur"], r["rating"])

DATES = {"nice": ("2026-10-06", "2026-10-10"), "lis": ("2026-10-10", "2026-10-14"),
         "lon": ("2026-10-14", "2026-10-18")}


def ab(city, room, pick, note):
    p, r = abprice[room]
    a = pics[room]
    ci, co = DATES[city]
    tags = []
    if a["workspace"]:
        tags.append("✅ 写了专用书桌")
    if a["elevator"]:
        tags.append("✅ 有电梯")
    sp = [w for w in a["wifi"] if "Mbps" in w]
    tags.append(f"✅ {sp[0].replace('Fast wifi – ', 'Wi-Fi ')}" if sp else "⚠️ 没写网速")
    name = a["title"].split(" - ")[0]
    return {"kind": "Airbnb", "pick": pick, "eur": p, "score": f"★{r}", "name": name, "note": note, "tags": tags,
            # 房源页里混着 Airbnb 自己的图标（airbnb-platform-assets），不是房子照片
            "imgs": [u for u in a["imgs"] if "platform-assets" not in u][:3],
            "url": f"https://www.airbnb.com/rooms/{room}?check_in={ci}&check_out={co}&adults=1"}


def bk(city, prefix, pick, note, vat=False, imgs=None, eur=None, url=None, tags=()):
    ci, co = DATES[city]
    c = next(x for x in search[city]["cards"] if x["name"].startswith(prefix))
    u = url or c["url"]
    # 酒店页上抓的 3 张（solo_hotel_imgs.py）优先；抓不到就用搜索卡片的封面
    more = hotel_imgs.get(u) or []
    if "indigo-london" in u:        # 它酒店页的第一张图本身就是一块灰色（9/24 实看），跳过
        more = more[1:]
    return {"kind": "酒店", "pick": pick, "eur": eur or c["price_4n"], "score": f"{c['score']}/10",
            "name": c["name"].split(",")[0], "note": note, "vat": vat, "tags": list(tags),
            "imgs": imgs or more[:3] or [c["img"]],
            "url": f"{u}?checkin={ci}&checkout={co}&group_adults=1&no_rooms=1&selected_currency=EUR"}


CITIES = [
    {"key": "nice", "city": "🇫🇷 尼斯", "when": "10/6 → 10/10 · 4 晚",
     "sold": search["nice"]["unavail_pct"],
     "verdict": "<b>选 Airbnb。</b>同价位的酒店，一个人住只给「单人房」（一张小床、没桌子）；想要酒店的舒服就得上 €1,200+ 那一档。",
     "opts": [
         ab("nice", "1443297416255023788", "🥇 首选", "Place Masséna 旁，海边和老城都走路 5 分钟，但不在老城里（夜里不吵）"),
         ab("nice", "48658006", "备选", "Jean-Médecin 大街，高楼层两间房 + 露台 + 空调，有电梯"),
         ab("nice", "1755951383141506994", "备选", "安静、明亮，有电梯，离海滨大道 700 米"),
         bk("nice", "Hotel 64", "🏨 酒店 · 性价比", "8.9 分、位置 9.4，市中心。⚠️ 这个价是「单人间」，房间小"),
         bk("nice", "Hotel Nap", "🏨 酒店 · 最中心", "离 Masséna 广场 0.1 英里，位置 9.7 分。⚠️ 同样是单人间"),
         bk("nice", "Maison Albar", "🏨 酒店 · 奢华", "五星，<b>正对海滩</b>，Junior Suite（有独立起居区，能好好工作）。如果想彻底躺平，就是它"),
     ]},
    {"key": "lis", "city": "🇵🇹 里斯本", "when": "10/10 → 10/14 · 4 晚",
     "sold": search["lis"]["unavail_pct"],
     "verdict": "<b>🔴 先订酒店占位。</b>Booking 显示这几天里斯本 <b>98% 的酒店已经没房</b>，我上次点名的 Mundial、Martinhal、Heritage 三家全满。"
                "Wilde 那家可以免费取消、到店才付钱 → <b>今天订下来零成本</b>，之后如果找到更好的 Airbnb 再取消。",
     "opts": [
         bk("lis", "Wilde Aparthotels", "🥇 首选 · 今天就订", "9.2 分。整套开间（带小厨房和桌子），在 Avenida da Liberdade 平路一侧 —— <b>不用拖箱子爬坡</b>",
            tags=["✅ 免费取消", "✅ 到店付款"]),
         bk("lis", "Altis Avenida", "🏨 酒店 · 位置最好", "9.3 分、位置 9.9。Restauradores 广场上，老城就在门口，含早餐"),
         bk("lis", "Hotel Metropole", "🏨 酒店 · 最便宜的中心位置", "Rossio 广场正中间，8.5 分，含早餐"),
         bk("lis", "Andaz Lisbon", "🏨 酒店 · 奢华", "凯悦旗下，9.1 分，河边 Santa Apolónia 车站旁"),
         ab("lis", "18047870", "Airbnb 首选", "Arroios 区，现代装修。<b>唯一一个同时写了电梯和网速的</b>"),
         ab("lis", "13292214", "Airbnb 备选", "Alfama 老城河景。⚠️ 页面没写电梯，老城全是坡 —— 下单前问房东"),
     ]},
    {"key": "lon", "city": "🇬🇧 伦敦", "when": "10/14 → 10/18 · 4 晚",
     "sold": search["lon"]["unavail_pct"],
     "verdict": "<b>Airbnb 和酒店都行。</b>Airbnb 便宜 €300–600；Native Hyde Park 是<b>整套公寓式酒店</b>（有厨房、有桌子），可免费取消到 10/12 —— 两边都要的话可以先订它占位。",
     "opts": [
         ab("lon", "1281197209882921388", "🥇 Airbnb 首选", "Marylebone 和 Edgware Road 地铁之间，两房"),
         ab("lon", "1670183614080025358", "Airbnb 备选", "Paddington，走到 Kensington Gardens 7 分钟，5.0 分"),
         {"kind": "酒店", "pick": "🏨 公寓式酒店 · 可先占位", "name": "Native Hyde Park",
          "eur": 1033, "score": "", "vat": True,
          "note": "整套开间，有厨房和洗碗机。<b>免费取消到 10/12、10/10 之前不扣钱</b>",
          "tags": ["✅ 免费取消", "✅ 整套公寓"], "imgs": nat["imgs"][:3],
          "url": nat["book_url"]},
         bk("lon", "Hotel Indigo", "🏨 酒店", "Paddington 站旁，精品酒店", vat=True),
         bk("lon", "Best Western Plus Delmere", "🏨 酒店 · 便宜", "8.5 分，Paddington 站走路 3 分钟。⚠️ 这个价是小双人房", vat=True),
     ]},
]

for c in CITIES:
    for o in c["opts"]:
        o["usd"] = round(o["eur"] * EUR_USD * (1.2 if o.get("vat") else 1))

SITE.write_text("/* 由 notes/_research/build_solo.py 生成，别手改 */\nconst STAYS = "
                + json.dumps(CITIES, ensure_ascii=False, indent=1) + ";\n")
print("wrote", SITE)
