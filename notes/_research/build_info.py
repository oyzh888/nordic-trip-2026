#!/usr/bin/env python3
"""生成「实用信息」页的数据 + 两份日历（.ics）。

为什么单独一页：官网其它页是「为什么这么排」，这页只回答路上真正会问的三件事 ——
**在哪（地址 + 一点就开的地图）· 几点（入住窗口、取还车、集合时间）· 加进日历**。

输入：
  viz/timeline.js           北欧段 13 天的权威时刻表（EV）—— 用 node 读，不手抄
  site/solo/trip.js         Steve 后半段（方案 C）的逐日
  out_practical.json        practical_scrape.py：已订住宿的地址 / 坐标 / 入住退房时间（9/26 实抓）
  下面的 PLACE 表          航站楼、取车柜台、集合点 —— 每一条写了来源；不确定的写「搜索链接」不写门牌号
输出：
  site/info/info.js         页面数据
  site/cal/nordic.ics       全队 9/24–10/6（可订阅：改了行程重新生成，日历自己会更新）
  site/cal/steve-solo.ics   Steve 10/6–10/17（没买的票标「待订」）

时区：timeline.js 里的时刻都是**当地时间**。冰岛 UTC+0（不用夏令时），挪威 UTC+2（到 10/25），
法国 UTC+2，英国 / 葡萄牙 UTC+1。航班的起止各按起降机场的时区算（SK4787 06:15 是奥斯陆时间、07:05 是冰岛时间）。
.ics 里一律写成 UTC（…Z），手机会按你当时所在的时区显示。

Usage: python3 build_info.py
"""
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import urllib.parse

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
SITE = ROOT / "site"
PR = json.load(open(HERE / "out_practical.json"))


def node_eval(path, names):
    js = (f"const fs=require('fs');const src=fs.readFileSync('{path}','utf8');"
          f"const f=new Function(src+';return {{{','.join(names)}}}');console.log(JSON.stringify(f()))")
    return json.loads(subprocess.check_output(["node", "-e", js]))


TL = node_eval(ROOT / "viz/timeline.js", ["EV"])
SOLO = node_eval(ROOT / "site/solo/trip.js", ["TDAYS", "POI"])
STAYS = node_eval(ROOT / "site/solo/stays.js", ["STAYS"])["STAYS"]

strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()
gmaps = lambda q: "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q)
amaps = lambda q, ll=None: "https://maps.apple.com/?q=" + urllib.parse.quote(q) + (f"&ll={ll[0]},{ll[1]}" if ll else "")


def t24(s):
    """'3:00 PM' → '15:00'；'From 3:00 PM to 12:00 AM' → '15:00–24:00'"""
    def one(x):
        m = re.match(r"(\d{1,2}):(\d{2})\s*([AP])M", x.strip().replace("\u202f", " "), re.I)
        if not m:
            return x
        h, mi, ap = int(m.group(1)), m.group(2), m.group(3).upper()
        h = (h % 12) + (12 if ap == "P" else 0)
        return f"{h:02d}:{mi}"
    parts = re.findall(r"\d{1,2}:\d{2}\s*[AP]M", (s or "").replace("\u202f", " "), re.I)
    out = [one(p) for p in parts]
    if len(out) == 2 and out[1] == "00:00":
        out[1] = "24:00"
    return "–".join(out)


# ---------------- 地点库 ----------------
# kind: stay / air / car / act。addr 只写**核实过**的；拿不准的只给 q（地图搜索词）。
#
# 2026-09-26：Airbnb 5 家已订房源的精确地址 —— 逐单从用户 Airbnb 订单页实查
# （公开房源页不显示门牌号，9/26 的 practical_scrape.py 抓不到，所以在这里覆盖）。
# 另：njardvik 实际订单不是 Ocean Break，而是 "Family friendly home!"（Gónhóll 18，
# €289.26，确认码 HMRZQFBWRS），名称和房源链接一并更正。
ADDR_FIX = {
    "rvk":         "Hringbraut 120, Reykjavík, Reykjavíkurborg 101, Iceland",
    "njardvik":    "Gónhóll 18, Njarðvík, Reykjanesbær 260, Iceland",
    "lyngvaer":    "Veg 2803, Vågan, Nordland 8313, Norway",
    "tromso":      "Tønsvikvegen 444, Tromsø, Troms og Finnmark 9022, Norway",
    "konglehytta": "Lushattvegen 16 Konglehytte III, Stange, Innlandet 2338, Norway",
}
def stay(key, name, q, how_note=""):
    p = PR[key]
    exact = p["src"] == "booking"
    ci = t24(p.get("checkin_t") or p.get("checkin") or "")
    co = t24(p.get("checkout_t") or p.get("checkout") or "")
    addr = ADDR_FIX.get(key) or (re.split(r"\s*After booking", p.get("addr", ""))[0].strip() if exact else None)
    area = p.get("where") if p.get("where") and "," in p.get("where", "") else q    # 「Find things to do」这种是抓错了
    return {"kind": "stay", "name": name, "addr": addr,
            "area": None if exact else area,
            "exact": exact, "ll": p.get("ll"), "q": addr or q,
            "checkin": ci, "checkout": co,
            "how": {"lockbox": "密码箱自助取钥匙", "keypad": "门锁密码自助入住"}.get(
                next((w for w in ("lockbox", "keypad") if w in (p.get("how") or "")), ""), "") or how_note,
            "url": p["url"]}


PLACE = {
    # 住宿（9/26 实抓 Booking / Airbnb 房源页）
    "radisson": stay("radisson-osl", "Radisson Blu Airport Hotel, Oslo", "Radisson Blu Airport Hotel Oslo Gardermoen",
                     "24 小时前台 · 从到达大厅走连廊约 5 分钟"),
    "rvk": stay("rvk", "雷克雅未克 · Aurora view 3BR 2BATH（Airbnb）", "Reykjavík"),
    "horgsland": stay("horgsland", "Hörgsland Cottages", "Hörgsland Cottages", "前台办理"),
    "birkifell": stay("birkifell", "Guesthouse Birkifell", "Guesthouse Birkifell"),
    "njardvik": stay("njardvik", "Njarðvík · Family friendly home!（Airbnb）", "Njarðvík, Reykjanesbær"),
    "lyngvaer": stay("lyngvaer", "Nordic Lodge Retreat · Lyngvær（Airbnb）", "Lyngvær, Vågan"),
    "tromso": stay("tromso", "特罗姆瑟 4 房公寓（Airbnb）", "Tromsø"),
    "kongle": stay("konglehytta", "Konglehytta 3 · Star View（Airbnb）", "Stange, Innlandet, Norway"),
    # 机场（航站楼按出票信息 / 机场官方：OSL / KEF / TOS 都只有一个客运航站楼）
    "PEK": {"kind": "air", "name": "北京首都国际机场 T2", "q": "Beijing Capital International Airport Terminal 2", "tz": 8},
    "OSL": {"kind": "air", "name": "奥斯陆加勒穆恩机场 OSL", "q": "Oslo Airport Gardermoen", "tz": 2},
    "KEF": {"kind": "air", "name": "冰岛凯夫拉维克机场 KEF", "q": "Keflavík International Airport", "tz": 0},
    "EVE": {"kind": "air", "name": "哈尔斯塔/纳尔维克埃沃内斯机场 EVE", "q": "Harstad/Narvik Airport Evenes", "tz": 2},
    "LKN": {"kind": "air", "name": "莱克内斯机场 LKN（罗弗敦）", "q": "Leknes Airport", "tz": 2},
    "TOS": {"kind": "air", "name": "特罗姆瑟机场 TOS", "q": "Tromsø Airport", "tz": 2},
    "NCE": {"kind": "air", "name": "尼斯蔚蓝海岸机场 NCE", "q": "Nice Côte d'Azur Airport", "tz": 2},
    "LHR": {"kind": "air", "name": "伦敦希思罗机场 LHR", "q": "Heathrow Airport", "tz": 1},
    "LTN": {"kind": "air", "name": "伦敦卢顿机场 LTN", "q": "London Luton Airport", "tz": 1},
    "LIS": {"kind": "air", "name": "里斯本 Humberto Delgado 机场 LIS", "q": "Lisbon Humberto Delgado Airport", "tz": 1},
    "SFO": {"kind": "air", "name": "旧金山国际机场 SFO", "q": "San Francisco International Airport", "tz": -7},
    # 取还车（柜台位置按租车单：KEF 的 Avis 是航站楼外摆渡车；其它三家 SIXT 在航站楼内）
    "car_kef": {"kind": "car", "name": "Avis · 凯夫拉维克机场", "q": "Avis Keflavík Airport",
                "hint": "航站楼外坐租车摆渡车（KEF 所有自动挡四驱都不在楼内）"},
    "car_eve": {"kind": "car", "name": "SIXT · 埃沃内斯机场", "q": "SIXT Harstad/Narvik Airport Evenes", "hint": "航站楼内柜台"},
    "car_lkn": {"kind": "car", "name": "SIXT 还车 · 莱克内斯机场", "q": "Leknes Airport", "hint": "异地还车"},
    "car_tos": {"kind": "car", "name": "SIXT · 特罗姆瑟机场", "q": "SIXT Tromsø Airport", "hint": "航站楼内柜台"},
    "car_osl": {"kind": "car", "name": "SIXT · 奥斯陆机场", "q": "SIXT Oslo Airport Gardermoen", "hint": "航站楼内柜台"},
    # 活动
    "bluelagoon": {"kind": "act", "name": "蓝湖温泉 Blue Lagoon", "addr": "Norðurljósavegur 9, 240 Grindavík, Iceland",
                   "q": "Blue Lagoon Iceland", "hint": "必须提前订时段票；有行李寄存"},
    "troll": {"kind": "act", "name": "Troll.is 集合点 · 冰河湖停车场", "q": "Jökulsárlón Glacier Lagoon parking",
              "hint": "停车场里食物车后面、公共厕所旁边的 Troll.is 拖车。徒步 09:10、皮划艇 13:10 到（按票面）"},
}


# ---------------- 北欧段：从 EV 变成「带地点的事件」 ----------------
def zone(ts):
    d = ts[:10]
    return 0 if "2026-09-25" <= d < "2026-09-30" else 2


FLIGHTS = [  # (匹配文本, 起飞机场, 降落机场, 航班号)
    ("北京首都 → 奥斯陆", "PEK", "OSL", "海南航空"), ("SK4787", "OSL", "KEF", "SK4787"),
    ("DY1171", "KEF", "OSL", "DY1171"), ("OSL → EVE", "OSL", "EVE", "挪威航空"),
    ("WF816", "LKN", "TOS", "WF816"), ("特罗姆瑟 → OSL", "TOS", "OSL", "挪威航空"),
    ("OSL 17:20 → 尼斯", "OSL", "NCE", "Steve 单飞 · 挪威航空"), ("OSL → 北京", "OSL", "PEK", "洲际（未定）"),
]
STAY_KEY = [("Radisson Blu Airport", "radisson"), ("Aurora view", "rvk"), ("Hörgsland", "horgsland"),
            ("Birkifell", "birkifell"), ("Njarðvík", "njardvik"), ("Nordic Lodge", "lyngvaer"),
            ("特罗姆瑟 4 房", "tromso"), ("Konglehytta", "kongle")]
CAR_KEY = [("冰岛 · Land Rover", "car_kef", "car_kef"), ("车①", "car_eve", "car_lkn"),
           ("车②", "car_tos", "car_tos"), ("车③", "car_osl", "car_osl")]


def utc(ts, tz):
    return dt.datetime.fromisoformat(ts) - dt.timedelta(hours=tz)


def status(e):
    return {"booked": "已订", "ok": "计划", "tbd": "待定"}.get(e["st"], e["st"])


items = []   # 页面 + 日历共用：{day, s_local, e_local, tz_s, tz_e, title, place, place2, note, st, warn}
for e in TL["EV"]:
    t = strip(e["t"])
    note = strip(e.get("note"))
    base = {"st": status(e), "raw_st": e["st"], "note": note, "link": e.get("link")}
    if e["lane"] == "fly":
        f = next((f for f in FLIGHTS if f[0] in t), None)
        if not f or "北京" in t and "OSL → 北京" in t and False:
            continue
        a, b = PLACE[f[1]], PLACE[f[2]]
        tz_s = a["tz"] if f[1] != "PEK" else 2      # 北京那班 timeline 里已换算成奥斯陆时间
        items.append({**base, "kind": "fly", "s": e["s"], "e": e["e"], "tz_s": tz_s, "tz_e": b["tz"] if f[2] != "PEK" else 2,
                      "title": f"✈ {f[3]} · {a['name'].split(' ')[0]} → {b['name'].split(' ')[0]}",
                      "place": f[1], "place2": f[2], "detail": t})
    elif e["lane"] == "stay":
        k = next((k for m, k in STAY_KEY if m in t), None)
        if not k:
            continue
        tz = zone(e["s"])
        p = PLACE[k]
        warn = []
        # 到达时间 vs 入住窗口：到得太早 / 太晚都要提醒
        arr = e["s"][11:16]
        if p["checkin"]:
            lo = p["checkin"].split("–")[0]
            hi = p["checkin"].split("–")[1] if "–" in p["checkin"] else None
            if arr < lo and arr > "06:00":
                warn.append(f"时刻表上 {arr} 就到了，但 {lo} 以后才能入住 —— 先去别处转转或寄存行李")
            wraps = hi and hi < lo            # 例如 14:00–02:00：截止在第二天凌晨
            if hi and hi != "24:00" and not wraps and arr > hi:
                warn.append(f"时刻表上 {arr} 才到，已经过了 {hi} 的入住截止 —— 提前联系房东")
            if hi == "24:00" and ("01:00" <= arr < "06:00"):
                warn.append(f"{arr} 才到，Booking 上写的入住截止是 24:00 —— 在 Booking 订单里给酒店留言「凌晨 1 点到」（24 小时前台，但先说一声）")
        items.append({**base, "kind": "stay", "s": e["s"], "e": e["e"], "tz_s": tz, "tz_e": zone(e["e"]),
                      "title": f"🛏 {p['name']}", "place": k, "detail": t, "warn": warn})
    elif e["lane"] == "car":
        c = next((c for c in CAR_KEY if c[0] in t), None)
        if not c:
            continue
        warn = []
        m = re.search(r"(\d{1,2}/\d{1,2}) (\d{1,2}:\d{2}) 取", note)
        if m and m.group(2) != e["s"][11:16]:
            warn.append(f"订单说明里写的是 {m.group(1)} {m.group(2)} 取车，时刻表是 {e['s'][11:16]} —— 以租车单为准，对不上就改单")
        warn_ret = []
        m = re.search(r"(\d{1,2}/\d{1,2}) (\d{1,2}:\d{2}) 还", note)
        if m and m.group(2) != e["e"][11:16]:
            warn_ret.append(f"订单说明里写的是 {m.group(1)} {m.group(2)} 还车，时刻表是 {e['e'][11:16]} —— 以租车单为准，对不上就改单")
        name = re.sub(r"^✅\s*", "", t.split("（")[0])
        items.append({**base, "kind": "car", "s": e["s"], "e": e["s"], "tz_s": zone(e["s"]), "tz_e": zone(e["s"]),
                      "title": f"🚗 取车 · {name}", "place": c[1], "detail": t, "warn": warn, "dur": 0.5})
        items.append({**base, "kind": "car", "s": e["e"], "e": e["e"], "tz_s": zone(e["e"]), "tz_e": zone(e["e"]),
                      "title": f"🚗 还车 · {name}", "place": c[2], "detail": t, "warn": warn_ret, "dur": 0.5, "ret": True})
    elif e["lane"] == "act":
        k = "bluelagoon" if "蓝湖泡汤" in t else ("troll" if "皮划艇" in t else None)
        items.append({**base, "kind": "act", "s": e["s"], "e": e["e"], "tz_s": zone(e["s"]), "tz_e": zone(e["e"]),
                      "title": ("🧊 冰川徒步 09:30 → 🛶 冰河湖皮划艇 13:30（Troll.is · 4 人已订）" if k == "troll"
                                else re.sub(r"^🆕+\s*", "", t.split("（")[0])), "place": k, "detail": t, "warn": []})

# ---------------- Steve 后半段（方案 C） ----------------
SOLO_FLY = {"10/6": None,   # 10/6 那班已经在北欧段里了
            "10/10": ("NCE", "LHR", "英国航空"), "10/13": ("LTN", "LIS", "卢顿 → 里斯本"),
            "10/17": ("LIS", "SFO", "葡萄牙航空 TAP 直飞")}
solo = []
for d in SOLO["TDAYS"]:
    mm, dd = d["d"].split("/")
    day = f"2026-{int(mm):02d}-{int(dd):02d}"
    for b in d["blocks"]:
        if b["k"] not in ("act", "fly", "opt"):
            continue
        if b["k"] == "fly" and d["d"] == "10/6":
            continue
        hs = lambda h: f"{day}T{int(h):02d}:{round((h % 1) * 60):02d}"
        tz = d["tz"]
        s_l, e_l = hs(b["a"]), hs(min(b["b"], 23.98))
        if b["k"] == "fly":
            fa, fb, name = SOLO_FLY[d["d"]]
            A, B = PLACE[fa], PLACE[fb]
            # 起飞按出发地时区，落地按目的地时区（10/10 那班 trip.js 按英国时间画的）
            tz_s = A["tz"]
            start = utc(s_l, tz)                                   # trip.js 里统一按当天 tz 画
            dur = {"10/10": 2.25, "10/13": 2.92, "10/17": 12.42}[d["d"]]
            end = start + dt.timedelta(hours=dur)
            solo.append({"kind": "fly", "st": "待订", "raw_st": "tbd", "title": f"✈ {name} · {A['name'].split(' ')[0]} → {B['name'].split(' ')[0]}",
                         "s_utc": start, "e_utc": end, "tz_s": tz_s, "tz_e": B["tz"], "place": fa, "place2": fb,
                         "detail": b["t"], "note": "", "warn": []})
        else:
            poi = SOLO["POI"].get(b.get("poi") or "", {})
            solo.append({"kind": "act", "st": "计划" if b["k"] == "act" else "可选", "raw_st": "ok",
                         "title": "（可选）" + b["t"].split("（")[0].replace("可选：", "")[:50] if b["k"] == "opt" else b["t"].split("（")[0][:50],
                         "s_utc": utc(s_l, tz), "e_utc": utc(e_l, tz), "tz_s": tz, "tz_e": tz,
                         "place": None, "q": poi.get("name"), "ll": poi.get("ll"),
                         "detail": b["t"] + (f" · 从住处：{b['mode']}" if b.get("mode") else ""), "note": "", "warn": []})
# 三城住宿：还没订 → 用订票页每城「⚖️ 平衡最好」那套做占位
for c, (ci, co, tz) in {"nice": ("2026-10-06T21:15", "2026-10-10T09:00", 2), "lon": ("2026-10-10T14:00", "2026-10-13T10:15", 1),
                        "lis": ("2026-10-13T16:00", "2026-10-17T11:00", 1)}.items():
    s = next(x for x in STAYS if x["key"] == c)
    o = s["opts"][0]
    solo.append({"kind": "stay", "st": "待订", "raw_st": "tbd",
                 "title": f"🛏 {s['city']} {s['when'].split('·')[1].strip()}（还没订 · 首选：{o['name'][:40]}）",
                 "s_utc": utc(ci, tz), "e_utc": utc(co, tz), "tz_s": tz, "tz_e": tz, "place": None,
                 "q": o["name"], "ll": [o["lat"], o["lng"]] if o.get("lat") else None,
                 "detail": f"订票页：https://nordic.airacle.com/solo/ · 首选 {o['name']} €{o['eur']}", "note": "", "warn": [], "url": o["url"]})


# ---------------- 统一成 UTC ----------------
def finish(it):
    if "s_utc" not in it:
        it["s_utc"] = utc(it["s"], it["tz_s"])
        it["e_utc"] = utc(it["e"], it["tz_e"]) if it.get("dur") is None else it["s_utc"] + dt.timedelta(hours=it["dur"])
        if it["e_utc"] <= it["s_utc"]:
            it["e_utc"] = it["s_utc"] + dt.timedelta(minutes=30)
    it["local_s"] = (it["s_utc"] + dt.timedelta(hours=it["tz_s"])).strftime("%Y-%m-%dT%H:%M")
    it["local_e"] = (it["e_utc"] + dt.timedelta(hours=it["tz_e"])).strftime("%Y-%m-%dT%H:%M")
    p = PLACE.get(it.get("place") or "")
    q = (p or {}).get("q") or it.get("q")
    ll = (p or {}).get("ll") or it.get("ll")
    it["loc"] = ((p or {}).get("addr")
                 or ((p or {}).get("area") and f"{p['area']}（精确门牌号在 Airbnb 订单 / App 里）")
                 or (p or {}).get("name") or it.get("q") or "")
    if q:
        it["gmap"] = gmaps(f"{ll[0]},{ll[1]}" if (ll and (p or {}).get("exact")) else q)
        it["amap"] = amaps(q, ll if (p or {}).get("exact") else None)
    if it.get("place2"):
        p2 = PLACE[it["place2"]]
        it["loc2"] = p2["name"]
        it["gmap2"] = gmaps(p2["q"])
    return it


nordic = sorted((finish(i) for i in items), key=lambda x: x["s_utc"])
solo = sorted((finish(i) for i in solo), key=lambda x: x["s_utc"])


# ---------------- .ics ----------------
def ics(events, name, desc):
    def esc(s):
        return (s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    def fold(line):   # RFC 5545：每行 ≤75 字节
        b, out = line.encode(), []
        while len(b) > 74:
            cut = 74
            while (b[cut] & 0xC0) == 0x80:
                cut -= 1
            out.append(b[:cut].decode())
            b = b" " + b[cut:]
        out.append(b.decode())
        return "\r\n".join(out)
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//nordic-trip-2026//info//ZH", "CALSCALE:GREGORIAN",
         "METHOD:PUBLISH", f"X-WR-CALNAME:{esc(name)}", f"X-WR-CALDESC:{esc(desc)}", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for e in events:
        uid = hashlib.sha1((e["title"] + e["local_s"]).encode()).hexdigest()[:16] + "@nordic.airacle.com"
        lines = [f"【{e['st']}】" if e["st"] in ("待定", "待订") else "", e.get("detail", "")]
        if e.get("loc"):
            lines.append("📍 " + e["loc"])
        if e.get("gmap"):
            lines.append("地图：" + e["gmap"])
        if e.get("place") in PLACE and PLACE[e["place"]].get("checkin"):
            p = PLACE[e["place"]]
            lines.append(f"入住 {p['checkin']} · 退房 {p['checkout']}" + (f" · {p['how']}" if p.get("how") else ""))
        if e.get("place") in PLACE and PLACE[e["place"]].get("hint"):
            lines.append(PLACE[e["place"]]["hint"])
        for w in e.get("warn", []):
            lines.append("⚠️ " + w)
        lines.append("完整行程：https://nordic.airacle.com/info/")
        L += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
              f"DTSTART:{e['s_utc'].strftime('%Y%m%dT%H%M%SZ')}", f"DTEND:{e['e_utc'].strftime('%Y%m%dT%H%M%SZ')}",
              f"SUMMARY:{esc(('【' + e['st'] + '】') if e['st'] in ('待定', '待订') else '')}{esc(e['title'])}",
              f"LOCATION:{esc(e.get('loc', ''))}", f"DESCRIPTION:{esc(chr(10).join(x for x in lines if x))}",
              "END:VEVENT"]
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in L) + "\r\n"


(SITE / "cal").mkdir(exist_ok=True)
(SITE / "cal/nordic.ics").write_text(ics(nordic, "北欧 2026 · 全队", "9/24–10/6 · 4 人 · 航班 / 住宿 / 取还车 / 活动"))
(SITE / "cal/steve-solo.ics").write_text(ics(solo, "北欧 2026 · Steve 后半段", "10/6–10/17 · 尼斯 → 伦敦 → 里斯本 → SFO（方案 C）"))


def gcal(e):
    q = {"action": "TEMPLATE", "text": e["title"],
         "dates": e["s_utc"].strftime("%Y%m%dT%H%M%SZ") + "/" + e["e_utc"].strftime("%Y%m%dT%H%M%SZ"),
         "location": e.get("loc", ""), "details": (e.get("detail", "") + "\n完整行程：https://nordic.airacle.com/info/")[:900]}
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(q)


def page(e):
    p = PLACE.get(e.get("place") or "", {})
    return {k: v for k, v in {
        "kind": e["kind"], "st": e["st"], "raw": e.get("raw_st"), "title": e["title"], "s": e["local_s"], "e": e["local_e"],
        "tz_s": e["tz_s"], "tz_e": e["tz_e"], "loc": e.get("loc"), "loc2": e.get("loc2"),
        "gmap": e.get("gmap"), "amap": e.get("amap"), "gmap2": e.get("gmap2"),
        "exact": p.get("exact"), "area": p.get("area"), "checkin": p.get("checkin"), "checkout": p.get("checkout"),
        "how": p.get("how"), "hint": p.get("hint"), "warn": e.get("warn") or [], "url": p.get("url") or e.get("url") or e.get("link"),
        "detail": e.get("detail"), "gcal": gcal(e), "ret": e.get("ret"),
    }.items() if v not in (None, "", [])}


stays_tbl = []
for k in ("radisson", "rvk", "horgsland", "birkifell", "njardvik", "lyngvaer", "tromso", "kongle"):
    p = PLACE[k]
    nights = [e for e in nordic if e.get("place") == k and e["kind"] == "stay"]
    stays_tbl.append({"name": p["name"], "addr": p.get("addr"), "area": p.get("area"), "exact": p["exact"],
                      "checkin": p["checkin"], "checkout": p["checkout"], "how": p.get("how"), "url": p["url"],
                      "gmap": gmaps(f"{p['ll'][0]},{p['ll'][1]}" if p["exact"] and p.get("ll") else p["q"]),
                      "nights": [(n["local_s"][5:10], n["local_e"][5:10]) for n in nights]})

(SITE / "info").mkdir(exist_ok=True)
(SITE / "info/info.js").write_text("/* 由 notes/_research/build_info.py 生成，别手改 */\nconst INFO = " + json.dumps({
    "nordic": [page(e) for e in nordic], "solo": [page(e) for e in solo], "stays": stays_tbl,
    "built": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
}, ensure_ascii=False, indent=1) + ";\n")
print("nordic", len(nordic), "solo", len(solo))
for e in nordic + solo:
    w = " ⚠️" + " | ".join(e.get("warn", [])) if e.get("warn") else ""
    print(f"  {e['local_s']} (UTC{e['tz_s']:+d}) {e['st']:3} {e['title'][:52]:52} @ {e.get('loc', '')[:40]}{w}")
