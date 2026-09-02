#!/usr/bin/env python3
"""把抓来的风光图 + 住宿实拍，编排成故事页的数据层 story/data.js。"""
import json, pathlib, re

R = pathlib.Path(".")
wiki = json.load(open(R/"out_wiki_picked.json"))
abnb = {r["slug"]: r for r in json.load(open(R/"out_img.json"))}
bkfix = json.load(open(R/"out_img_bk.json"))          # Booking：带签名 ?k= 的可外链大图

def W(slug, i=0):
    it = (wiki.get(slug) or {}).get("items") or []
    return it[i] if i < len(it) else None

def shots(slug, n=14):
    """Booking 的 cf.bstatic.com 图**必须带签名 ?k=**，不带就是 401（实测带不带 Referer 都一样），
    所以未签名的一律丢掉；Booking 那几家改用 bk_img_fix.py 抓到的签名大图（只有 1 张/家 ——
    它的图库有反爬，点不开，只能拿到主图）。"""
    src = (abnb.get(slug) or {}).get("images", [])
    # ⛔ AirbnbPlatformAssets = 站点品牌图/favicon，不是房源照片（camelCase，之前小写过滤没命中）
    src = [u for u in src if "airbnbplatformassets" not in u.lower()]
    src = [u for u in src if "bstatic.com" not in u or "?k=" in u]
    if not src and slug in bkfix:
        src = bkfix[slug].get("images", [])
        og = next((r.get("og_image") for r in json.load(open(R/"out_img.json"))
                   if r["slug"] == slug and r.get("og_image")), None)
        if og and og not in src: src = src + [og]
    return src[:n]

# ---------- 幕 ----------
ACTS = [
 dict(id="act0", num="序", title="夜航向北", sub="Oslo Gardermoen",
      lede="第一晚不看风景。落地、取箱子、开十五分钟到一栋农舍，把时差睡掉。"
           "真正的旅程从明天早上那班飞机开始。",
      hero="oslo", tone="#7dd3fc"),
 dict(id="act1", num="I", title="冰与水的边界", sub="Iceland · 9/25 – 9/29",
      lede="五天绕着一号公路的南半段走：瀑布从苔原上直落，冰川断成蓝色的碎块漂进黑沙滩，"
           "地热在脚下嘶嘶作响。这一段的密度高得不像度假 —— 但它是整趟旅程里最不像地球的部分。",
      hero="jokulsarlon", tone="#34d399"),
 dict(id="act2", num="II", title="海里立起来的山", sub="Lofoten · 9/30 – 10/2",
      lede="从 Evenes 开进 E10，山从海里垂直站起来，红色的渔屋钉在水边。"
           "九月末的罗弗敦刚好卡在秋色和极光季之间 —— 白天是金黄的山坡，天一黑就抬头。",
      hero="reine", tone="#fbbf24"),
 dict(id="act3", num="III", title="极光之城", sub="Tromsø & Senja · 10/2 – 10/6",
      lede="北纬 69 度。城在两座桥之间，缆车上去能看到整片群山。"
           "最后一整天开去 Senja —— 五百公里往返，只为几个没有名字的观景台。",
      hero="aurora_no", tone="#a78bfa"),
]

# ---------- 每一天 ----------
DAYS = [
 dict(act="act0", d="D0", date="9/24", wd="周四", t="落地奥斯陆",
      place="Nannestad, Norway",
      body="下午的飞机落在 Gardermoen。往西开十五分钟，一栋安静的农舍，五个房间。"
           "行李不用全拆 —— 明早还要飞。",
      imgs=["oslo"], stay="d0-nann5br",
      stayname="Charming farmhouse near Gardermoen", staymeta="Airbnb · 5 房 · Nannestad"),
 dict(act="act1", d="D1", date="9/25", wd="周五", t="雷克雅未克",
      place="Reykjavík, Iceland",
      body="落地就在 KEF 提车 —— 这一步省掉了四个人来回机场大巴。"
           "傍晚在市中心：混凝土的教堂像玄武岩柱，老港边上停着那艘钢骨头做的维京船。",
      imgs=["hallgrim","sunvoyager","rvk"], stay="d1-aurora",
      stayname="Aurora View · 3BR 2BATH", staymeta="Airbnb · 市中心 · 3 房 2 卫"),
 dict(act="act1", d="D2", date="9/26", wd="周六", t="南岸的两道瀑布",
      place="Seljalandsfoss → Skógafoss → Klaustur",
      body="一号公路往东。第一道瀑布可以从背后绕过去，水幕在你身后合上；"
           "第二道六十米宽，站在下面说话听不见。当晚睡在 Klaustur 东边的草地小屋。",
      imgs=["seljalands","skogafoss","dyrholaey"], stay="d2-horgsland",
      stayname="Hörgsland Cottages", staymeta="Booking · 草地木屋 · Klaustur 东"),
 dict(act="act1", d="D3", date="9/27", wd="周日", t="冰河湖与钻石沙滩",
      place="Jökulsárlón · Diamond Beach · Stokksnes",
      body="瓦特纳冰川的舌头断在这里。蓝白色的冰块顺着一条短短的河漂进大西洋，"
           "又被浪推回黑沙滩上搁着 —— 所以那片沙滩叫钻石。夜里去 Stokksnes 那座尖山下等极光。",
      imgs=["jokulsarlon","fjallsarlon","vestrahorn","svartifoss"], stay="d3-birkifell",
      stayname="Guesthouse Birkifell", staymeta="Booking · 整栋 · Höfn 西"),
 dict(act="act1", d="D4", date="9/28", wd="周一", t="黄金圈，然后西返",
      place="Þingvellir · Geysir · Gullfoss",
      body="全程最长的一天。裂谷把两块大陆掰开一条缝，间歇泉每几分钟炸一次，"
           "然后是那道拐着直角掉下去的金瀑布。傍晚泡进乳蓝色的温泉里，把一天的公里数忘掉。",
      imgs=["thingvellir","geysir","gullfoss","bluelagoon"], stay="d4-njardvik",
      stayname="Cozy home in Njarðvík", staymeta="Airbnb · KEF 旁 · 4 房"),
 dict(act="act1", d="D5", date="9/29", wd="周二", t="雷克雅内斯，轻装的一天",
      place="Reykjanes Peninsula → OSL",
      body="原本排的是斯奈山半岛七个半小时的车程 —— 砍掉了。"
           "改成机场边上这个半岛：两块大陆之间的一座小桥、冒着白汽的泥浆池、"
           "被浪凿出来的石头浴缸。下午还车，飞回奥斯陆。",
      imgs=["bridge2cont","gunnuhver","brimketill","reykjanesviti"], stay=None,
      stayname="Nannestad（同 9/24 一带）", staymeta="Airbnb · 5 房 · 换来可退"),
 dict(act="act2", d="D6", date="9/30", wd="周三", t="进罗弗敦",
      place="Evenes → Svolvær → Vågan",
      body="十点半落在 Evenes，提车，上 E10。一百六十五公里没有渡轮、几乎没有收费站，"
           "路两边的山一座比一座陡。傍晚到 Vågan，木屋带按摩浴缸和桑拿 —— 泡着等天黑。",
      imgs=["e10","lofoten","henningsvaer"], stay="d6-vagan3br",
      stayname="Lyngvær Arctic Lodge · Jacuzzi & Sauna", staymeta="Airbnb · 3 房 · 罗弗敦东侧"),
 dict(act="act2", d="D7", date="10/1", wd="周四", t="明信片那一侧",
      place="Reine · Hamnøy · Sakrisøy · Å",
      body="往西开到群岛的尽头。Hamnøy 那排红屋是全挪威被拍得最多的一张画；"
           "Reine 背后的 Reinebringen 有一段石阶，爬上去两个小时，整个峡湾在脚下摊开。",
      imgs=["hamnoy","reine","reinebringen","sakrisoy","skagsanden"], stay=None,
      stayname="同 D6（连住两晚，不搬箱子）", staymeta="Airbnb · Vågan"),
 dict(act="act3", d="D8", date="10/2", wd="周五", t="五十分钟，跨过北极圈",
      place="Svolvær ✈ Tromsø",
      body="本来想坐海岸邮轮夜航 —— 后来改成飞。Widerøe 的支线小飞机五十分钟，"
           "省下的时间换成在特罗姆瑟的一整个下午。落地再提一台车。",
      imgs=["narvik","arcticcath","tromso"], stay="d8-tos4br",
      stayname="Queen size beds · Fantastisk nordlys · Jacuzzi", staymeta="Airbnb · 4 房 · 住 4 晚"),
 dict(act="act3", d="D9", date="10/3", wd="周六", t="缆车上去看整座城",
      place="Tromsø · Fjellheisen · Ishavskatedralen",
      body="北极大教堂是一排白色的三角形，正对着桥。缆车上到 Storsteinen，"
           "城市、两座桥、后面一层一层的雪山全在一个画面里。晚上往内陆开，躲开云。",
      imgs=["fjellheisen","arcticcath","aurora_no"], stay=None,
      stayname="同 D8（4 晚连住）", staymeta="Airbnb · 特罗姆瑟"),
 dict(act="act3", d="D10", date="10/4", wd="周日", t="留白的一天",
      place="Tromsø",
      body="故意什么都不排。有车、有一整天、有极光季刚开的天空 ——"
           "想往哪个方向躲云就往哪个方向开。",
      imgs=["aurora_lof","kvalvika"], stay=None,
      stayname="同 D8", staymeta="Airbnb · 特罗姆瑟"),
 dict(act="act3", d="D11", date="10/5", wd="周一", t="Senja，五百公里的硬仗",
      place="Senja · Tungeneset · Bergsbotn · Ersfjord",
      body="七点出发，天还没亮。渡轮四十分钟过去，然后是一条贴着海岸凿出来的路："
           "花岗岩的獠牙立在海里、悬空的木头观景台、一片白得不像北极圈的沙滩。"
           "日照只有十小时五十分钟 —— 所以不能晚出发。",
      imgs=["tungeneset","senja","bergsbotn","ersfjord","segla"], stay=None,
      stayname="同 D8（最后一晚）", staymeta="Airbnb · 特罗姆瑟"),
 dict(act="act3", d="D12", date="10/6", wd="周二", t="还车，回家",
      place="Tromsø → Oslo",
      body="十点还车，飞奥斯陆。十三天，两台车，两千四百公里。",
      imgs=["tromso"], stay=None, stayname="—", staymeta="—"),
]

def img(slug):
    it = W(slug)
    if not it: return None
    return {"slug":slug,"src":it["src"],"w":it["w"],"h":it["h"],
            "title":it["title"],"author":it.get("author"),
            "license":it.get("license"),"page":it.get("page")}

out_days=[]
for d in DAYS:
    imgs=[i for i in (img(s) for s in d["imgs"]) if i]
    out_days.append({**d,"imgs":imgs,"shots":shots(d["stay"]) if d.get("stay") else []})

out_acts=[]
for a in ACTS:
    out_acts.append({**a,"heroImg":img(a["hero"])})

# 备选住宿的画廊（也是「Airbnb 里的图」）
ALT=[
 {"slug":"alt-houseboat","name":'Houseboat “Grosso”',"meta":"特罗姆瑟 · 住在船上 · 3 房 3 卫 · ★5.0","why":"备选：卫生间比人多，全程单价最低的一段"},
 {"slug":"alt-ramberg","name":"The heart of Ramberg","meta":"罗弗敦西侧 · 4 房 2.5 卫 · ★4.76","why":"备选：住西侧就不用 D7 当天往返，代价是 10/2 多开 2 小时"},
 {"slug":"alt-arnanes","name":"Árnanes Country Hotel","meta":"Höfn · 酒店 2 间房","why":"备选：冰河湖那晚的酒店路线"},
]
out_alt=[{**a,"shots":shots(a["slug"],16)} for a in ALT]

# 全部用到的图 → 署名表
credits={}
for a in out_acts:
    if a["heroImg"]: credits[a["heroImg"]["src"]]=a["heroImg"]
for d in out_days:
    for i in d["imgs"]: credits[i["src"]]=i

js = ("/* 自动生成，别手改 —— 改 notes/_research/build_story.py 然后重跑 */\n"
      "const ACTS = %s;\nconst DAYS = %s;\nconst ALTSTAYS = %s;\nconst CREDITS = %s;\n"
      % (json.dumps(out_acts,ensure_ascii=False,indent=1),
         json.dumps(out_days,ensure_ascii=False,indent=1),
         json.dumps(out_alt,ensure_ascii=False,indent=1),
         json.dumps(sorted(credits.values(),key=lambda x:x["slug"]),ensure_ascii=False,indent=1)))
p=pathlib.Path("../../story/data.js"); p.write_text(js)
print("写入",p.resolve())
print(f"幕 {len(out_acts)} · 天 {len(out_days)} · 风光图 {sum(len(d['imgs']) for d in out_days)} · "
      f"住宿实拍 {sum(len(d['shots']) for d in out_days)+sum(len(a['shots']) for a in out_alt)} · 署名条目 {len(credits)}")
missing=[d["d"] for d in out_days if not d["imgs"]]
print("没图的天：",missing or "无")
