#!/usr/bin/env python3
"""生成 styles/data.js —— 四个风格版本共用的数据层。
行程以 viz/data.js（= notes/PLAN-final.md）2026-09-03 那版为准：
  · 10/5 不再是 Senja 日，改成还车 → 飞 TOS→OSL → 住 Stange/Mjøsli 森林小屋
  · Senja 因此挪到 10/4；特罗姆瑟回到 3 晚
  · 9/28 换成 Njarðvík 带热浴桶 + 桑拿那套
  · 10/2 改飞（Svolvær 还车 → 直飞 50 min → 特罗姆瑟再提车）
  · 9/29 已减负：斯奈山 7.5h → 雷克雅内斯 ~2h
"""
import json, pathlib

R = pathlib.Path(".")
wiki  = json.load(open(R/"out_wiki_picked.json"))
abnb  = {r["slug"]: r for r in json.load(open(R/"out_img.json"))}
abnb.update({r["slug"]: r for r in json.load(open(R/"out_img2.json"))})
bkfix = json.load(open(R/"out_img_bk.json"))

_used_img = set()
def W(slug, allow_reuse=False):
    """按顺序取该地点第一张还没被用过的图（避免两天用同一张）。"""
    for it in (wiki.get(slug) or {}).get("items") or []:
        if it["src"] in _used_img and not allow_reuse: continue
        _used_img.add(it["src"]); return it
    its = (wiki.get(slug) or {}).get("items") or []
    return its[0] if its else None

def shots(slug, n=16):
    src = (abnb.get(slug) or {}).get("images", [])
    src = [u for u in src if "airbnbplatformassets" not in u.lower()]      # 站点品牌图/favicon
    src = [u for u in src if "bstatic.com" not in u or "?k=" in u]         # Booking 未签名 = 401
    if not src and slug in bkfix:
        src = bkfix[slug].get("images", [])
        og = (abnb.get(slug) or {}).get("og_image")
        if og and og not in src: src = src + [og]
    return src[:n]

ACTS = [
 dict(id="act0", num="序", roman="0", title="第一夜", en="PROLOGUE",
      sub="Oslo Gardermoen · 9/24", hero="oslo", tone="#7dd3fc",
      lede="第一晚不看风景。落地、取箱子、往西开十五分钟到一栋农舍，把时差睡掉。"
           "真正的旅程从第二天早上那班飞机开始。"),
 dict(id="act1", num="I", roman="I", title="冰与水的边界", en="ICE & WATER",
      sub="Iceland · 9/25 – 9/29", hero="jokulsarlon", tone="#34d399",
      lede="五天沿着一号公路的南半段走：瀑布从苔原上直落，冰川断成蓝色的碎块漂进黑沙滩，"
           "地热在脚下嘶嘶作响。最后一天特意减了负 —— 把七个半小时的车程换成两个小时，"
           "剩下的时间泡在温泉里。"),
 dict(id="act2", num="II", roman="II", title="海里立起来的山", en="MOUNTAINS FROM THE SEA",
      sub="Lofoten · 9/30 – 10/2", hero="reine", tone="#fbbf24",
      lede="从 Evenes 开进 E10，山从海里垂直站起来，红色的渔屋钉在水边。"
           "九月末的罗弗敦刚好卡在秋色和极光季之间 —— 白天是金黄的山坡，天一黑就抬头。"),
 dict(id="act3", num="III", roman="III", title="极光之城", en="THE AURORA CITY",
      sub="Tromsø & Senja · 10/2 – 10/5", hero="aurora_no", tone="#a78bfa",
      lede="北纬 69 度。原计划坐夜航邮轮北上，最后改成一班五十分钟的支线飞机 ——"
           "省下来的半天留给了这座城。中间抽一整天开去 Senja，五百公里往返，"
           "只为几个连名字都记不住的观景台。"),
 dict(id="act4", num="IV", roman="IV", title="回到森林", en="BACK TO THE WOODS",
      sub="Mjøsli, Stange · 10/5 – 10/6", hero="mjosa", tone="#e0bf95",
      lede="最后一段是新加的。从北极圈飞回奥斯陆，再往北开三十分钟进 Stange 的林子里 ——"
           "一栋看得见星星的小屋，带一间私人桑拿。十三天从森林开始，也在森林里结束。"),
]

DAYS = [
 dict(act="act0", d="D0", n="01", date="9/24", wd="周四", t="落地奥斯陆",
      en="Arrival", place="Nannestad, Norway", drive="—",
      body="下午的飞机落在 Gardermoen。往西开十五分钟，一栋安静的农舍，五个房间。"
           "行李不用全拆 —— 明早还要飞。",
      imgs=["oslo"], stay="d0-nann5br",
      stayname="Modern. Quiet area. Large space.", staymeta="Airbnb · 3 房 / 5 床 / 2 卫 · Nannestad"),
 dict(act="act1", d="D1", n="02", date="9/25", wd="周五", t="雷克雅未克",
      en="Reykjavík", place="Reykjavík, Iceland", drive="KEF → 雷市 50 min",
      body="落地就在 KEF 提车 —— 不进城再折回来，省掉四个人两趟机场大巴。"
           "傍晚在市中心：那座混凝土教堂被造成玄武岩柱的样子，老港边上停着一艘钢骨头做的维京船。",
      imgs=["hallgrim","sunvoyager","rvk"], stay="d1-aurora",
      stayname="Aurora View · 3BR 2BATH", staymeta="Airbnb · 3 房 / 3 床 / 2 卫 · 市中心 · €647 → €447"),
 dict(act="act1", d="D2", n="03", date="9/26", wd="周六", t="南岸的两道瀑布",
      en="The South Coast", place="Seljalandsfoss · Skógafoss · Klaustur",
      drive="约 300 km / 3h45",
      body="一号公路往东。第一道瀑布能从背后绕过去，水幕在你身后合上；"
           "第二道六十米宽，站在下面说话听不见。住处特意往东挪到 Klaustur 一侧 —— "
           "为的是让第二天从 390 公里降到 200 公里。",
      imgs=["seljalands","skogafoss","dyrholaey","reynisfjara"], stay="d2-horgsland",
      stayname="Hörgsland Cottages · Three-Bedroom", staymeta="Booking · 3 卧 · 整栋 · 私厨私卫"),
 dict(act="act1", d="D3", n="04", date="9/27", wd="周日", t="冰河湖与钻石沙滩",
      en="Glacier Lagoon", place="Jökulsárlón · Diamond Beach · Stokksnes",
      drive="约 200 km / 2h30",
      body="瓦特纳冰川的舌头断在这里。蓝白色的冰块顺着一条很短的河漂进大西洋，"
           "又被浪推回黑沙滩上搁着 —— 所以那片沙滩叫钻石。"
           "夜里开去 Stokksnes，在那座尖山下等极光。",
      imgs=["jokulsarlon","fjallsarlon","stokksnes","svartifoss"], stay="d3-birkifell",
      stayname="Guesthouse Birkifell · Two-Bedroom House", staymeta="Booking · 2 卧 · 整栋 · 厨房 + 私卫"),
 dict(act="act1", d="D4", n="05", date="9/28", wd="周一", t="黄金圈，然后西返",
      en="The Golden Circle", place="Þingvellir · Geysir · Gullfoss · Blue Lagoon",
      drive="约 520 km / 6h30 —— 全程最长的一天",
      body="裂谷把两块大陆掰开一条缝，间歇泉每几分钟炸一次，"
           "然后是那道拐着直角掉下去的金瀑布。傍晚泡进乳蓝色的温泉，"
           "回到 KEF 旁边一栋带热浴桶和桑拿的房子 —— 这一天需要它。",
      imgs=["thingvellir","geysir","gullfoss","bluelagoon"], stay="d4-njardvik3",
      stayname="Hot tub & Sauna · Ocean Break", staymeta="Airbnb ★5.0 · 3 房 / 3 床 · Njarðvík · €531 → €335"),
 dict(act="act1", d="D5", n="06", date="9/29", wd="周二", t="减负的一天",
      en="Reykjanes, Lightened", place="Reykjanes Peninsula → OSL",
      drive="约 2h 纯开车（原方案 7.5h）",
      body="原本排的是斯奈山半岛 —— 七个半小时的车程，砍掉了。"
           "改成机场边上这个半岛：两块大陆之间的一座小桥、冒着白汽的泥浆池、"
           "被浪凿出来的石头浴缸。所有点都在 KEF 十五到五十分钟内。下午还车，飞回奥斯陆。",
      imgs=["bridge2cont","gunnuhver","brimketill","krysuvik","reykjanesviti"], stay="d0-nann5br",
      stayname="Nannestad 5 房（换来可退）", staymeta="Airbnb · 5 房 / 5 床 / 1.5 卫", reuse=1),
 dict(act="act2", d="D6", n="07", date="9/30", wd="周三", t="进罗弗敦",
      en="Into Lofoten", place="Evenes → Svolvær → Vågan",
      drive="EVE → Svolvær 165 km / 2h30",
      body="十点半落在 Evenes，提车，上 E10。一百六十五公里没有渡轮、几乎没有收费站，"
           "路两边的山一座比一座陡。傍晚到 Vågan。",
      imgs=["e10","lofoten","henningsvaer"], stay="d6-vagan3br",
      stayname="Lyngvær Arctic Lodge · Jacuzzi & Sauna", staymeta="Airbnb · 3 房 / 5 床 / 2 卫 · 罗弗敦东侧"),
 dict(act="act2", d="D7", n="08", date="10/1", wd="周四", t="明信片那一侧",
      en="The Postcard Side", place="Reine · Hamnøy · Sakrisøy · Å",
      drive="单程 2h · 往返约 4h",
      body="往西开到群岛的尽头，当天回。Hamnøy 那排红屋是全挪威被拍得最多的一张画；"
           "Reine 背后的 Reinebringen 有一段石阶，爬上去两个小时，整个峡湾在脚下摊开。",
      imgs=["hamnoy","reine","reinebringen","sakrisoy","skagsanden"], stay="d6-vagan3br",
      stayname="同 D6（连住第 2 晚，不搬箱子）", staymeta="Airbnb · Vågan", reuse=1),
 dict(act="act3", d="D8", n="09", date="10/2", wd="周五", t="五十分钟，跨过北极圈",
      en="Fifty Minutes North", place="Svolvær ✈ Tromsø",
      drive="开车只剩 30 min",
      body="本来想坐海岸邮轮夜航 —— 后来改成飞。Svolvær 还车，Widerøe 的支线小飞机五十分钟，"
           "落地再提一台车。省下来的整个上午白得了半天。",
      imgs=["narvik","tromso","arcticcath"], stay="d8-tos4br",
      stayname="Tromsø 4 房 · 3 晚连住", staymeta="Airbnb · 4 房 / 4 床 / 2 卫 · 10/2 – 10/5"),
 dict(act="act3", d="D9", n="10", date="10/3", wd="周六", t="缆车上去看整座城",
      en="The Cable Car", place="Tromsø · Fjellheisen · Ishavskatedralen",
      drive="市区 + 郊外追极光",
      body="北极大教堂是一排白色的三角形，正对着桥。缆车上到 Storsteinen，"
           "城市、两座桥、后面一层一层的雪山全在一个画面里。晚上往内陆开，躲开云。",
      imgs=["fjellheisen","aurora_no","aurora_lof"], stay="d8-tos4br",
      stayname="同 D8", staymeta="Airbnb · 特罗姆瑟", reuse=1),
 dict(act="act3", d="D10", n="11", date="10/4", wd="周日", t="Senja，五百公里的硬仗",
      en="Senja", place="Senja · Tungeneset · Bergsbotn · Ersfjord",
      drive="约 500 km 往返 · 路上 5–6h",
      body="天没亮就出发 —— 原本排在 10/5，因为最后一天改飞奥斯陆而挪到了今天。"
           "渡轮四十分钟过去，然后是一条贴着海岸凿出来的路：花岗岩的獠牙立在海里、"
           "悬空的木头观景台、一片白得不像北极圈的沙滩。",
      imgs=["tungeneset","senja","bergsbotn","ersfjord","segla"], stay="d8-tos4br",
      stayname="同 D8（特罗姆瑟最后一晚）", staymeta="Airbnb · 特罗姆瑟", reuse=1),
 dict(act="act4", d="D11", n="12", date="10/5", wd="周一", t="从北极圈飞回森林",
      en="Back to the Woods", place="Tromsø ✈ Oslo → Mjøsli, Stange",
      drive="落地后再开 30 min",
      body="还车，飞回奥斯陆，再往北开三十分钟，进 Stange 的林子。"
           "一栋叫 Konglehytta 的小屋，能看见星星，带一间私人桑拿 —— "
           "房源页上写着「A car is required」，所以车还得再留一天。"
           "这一晚也顺便当了防延误的缓冲。",
      imgs=["mjosa","kvalvika"], stay="d11-konglehytta",
      stayname="Konglehytta 3 · Star View · Sauna", staymeta="Airbnb ★4.98 · 整栋 · 2 房 / 3 床 · Mjøsli"),
 dict(act="act4", d="D12", n="13", date="10/6", wd="周二", t="还车，回家",
      en="Homeward", place="Mjøsli → Oslo Gardermoen",
      drive="Mjøsli → OSL 机场 30 min",
      body="车已经在手上，不用叫车。十三天，两个国家，两台车，大约两千四百公里 ——"
           "从奥斯陆西边的一栋农舍出发，回到奥斯陆机场。",
      imgs=["oslo"], stay=None,
      stayname="Clarion Hotel Oslo Airport ×2（占位，还没定）", staymeta="Booking · 2 房 / 2 卫"),
]

ALT = [
 {"slug":"alt-houseboat","name":'Houseboat “Grosso”',
  "meta":"特罗姆瑟 · 住在船上 · 3 房 3 卫 · ★5.0",
  "why":"备选：卫生间比人多，也是当时算下来单价最低的一段。最后没选，因为默认那套 4 房离市区更方便。"},
 {"slug":"alt-ramberg","name":"The heart of Ramberg",
  "meta":"罗弗敦西侧 · 4 房 2.5 卫 · ★4.76",
  "why":"备选：住西侧，D7 就不用当天往返；代价是 10/2 去机场要多开两小时。"},
 {"slug":"alt-arnanes","name":"Árnanes Country Hotel",
  "meta":"Höfn · 酒店 2 间房",
  "why":"备选：冰河湖那晚的酒店路线，后来换成了整栋的 Birkifell。"},
]

def img(slug, reuse=False):
    it = W(slug, allow_reuse=reuse)
    if not it: return None
    return {"slug":slug,"src":it["src"],"w":it["w"],"h":it["h"],"title":it["title"],
            "author":it.get("author"),"license":it.get("license"),"page":it.get("page")}

out_days=[]
for d in DAYS:
    imgs=[i for i in (img(s, bool(d.get("reuse"))) for s in d["imgs"]) if i]
    out_days.append({**d,"imgs":imgs,"shots":shots(d["stay"]) if d.get("stay") else []})
out_acts=[{**a,"heroImg":img(a["hero"], True)} for a in ACTS]
out_alt=[{**a,"shots":shots(a["slug"],16)} for a in ALT]

credits={}
for a in out_acts:
    if a["heroImg"]: credits[a["heroImg"]["src"]]=a["heroImg"]
for d in out_days:
    for i in d["imgs"]: credits[i["src"]]=i

STATS=[["13","天 · 9/24 → 10/6"],["5","幕 · 从森林到森林"],["2","个国家 · 冰岛 + 挪威"],
       ["2","台车 · 5 天 + 6 天"],["≈2,400","公里"],["69°N","最北 · Senja"]]

js=("/* 自动生成，别手改 —— 改 notes/_research/build_styles.py 然后重跑 */\n"
    "/* 行程 = viz/data.js（notes/PLAN-final.md）2026-09-03 版 */\n"
    +"".join(f"const {k} = {json.dumps(v,ensure_ascii=False,indent=1)};\n" for k,v in
      [("ACTS",out_acts),("DAYS",out_days),("ALTSTAYS",out_alt),
       ("CREDITS",sorted(credits.values(),key=lambda x:x["slug"])),("STATS",STATS)]))
p=pathlib.Path("../../styles/data.js"); p.parent.mkdir(exist_ok=True); p.write_text(js)
print("写入",p.resolve())
print(f"幕 {len(out_acts)} · 天 {len(out_days)} · 风光图 {sum(len(d['imgs']) for d in out_days)}"
      f" · 住宿实拍 {sum(len(d['shots']) for d in out_days)+sum(len(a['shots']) for a in out_alt)}"
      f" · 署名 {len(credits)}")
miss=[d["d"] for d in out_days if not d["imgs"]]
print("没图的天：",miss or "无")
