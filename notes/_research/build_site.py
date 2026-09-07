#!/usr/bin/env python3
"""生成 site/data.js —— 官网唯一的数据层。

为什么要生成而不是手写：这个 repo 已经有过「三份各自独立的 data.js，改一个预订要改三处」
的教训（见 README 那节结构隐患）。官网这一份**全部从既有真相合并出来**，所以：
  · 时刻 / 已订状态 / 待办  ← viz/timeline.js（唯一权威时刻表，ISO 时刻可计算）
  · 逐日文案 / 风光图 / 房源照 ← styles/data.js（已有的漂亮版，图是 Wikimedia CC + Airbnb CDN）
  · 四台车的照片 + 许可     ← notes/_research/out_cars_imgs.json（Commons API 抓的）
改任何一处，重跑这个脚本，官网跟着变。

Usage: python3 notes/_research/build_site.py
"""
import json, re, subprocess, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

def js_export(path, names):
    """把一个 data.js 里的若干个 const 取出来（用 node 求值，不做正则解析）。"""
    # 用 node 求值而不是正则解析 —— data.js 里有字符串拼接和注释，正则一定会解析错。
    # 名字必须逐个显式列出：这样某个来源改名/删了会当场报错，而不是静默变 null。
    expr = "{" + ",".join(names) + "}"
    out = subprocess.run(["node", "-e",
        f"const s=require('fs').readFileSync({json.dumps(str(ROOT/path))},'utf8');"
        f"const v=new Function(s+'\\nreturn {expr}')();"
        "process.stdout.write(JSON.stringify(v))"], capture_output=True, text=True)
    if out.returncode:
        sys.exit(f"读 {path} 失败（要的名字：{names}）：\n{out.stderr.strip()[:600]}")
    return json.loads(out.stdout)

tl  = js_export("viz/timeline.js",  ["EV", "TOFILL", "DAY0", "DAYN"])
st  = js_export("styles/data.js",   ["DAYS", "ACTS", "CREDITS", "STATS", "ALTSTAYS"])
cars_raw = json.loads((ROOT / "notes/_research/out_cars_imgs.json").read_text())

# ---------- 四台车：真实订单 + 一张 CC 图 ----------
# 挑图的规则（写下来免得以后不知道为什么是这张）：
#   · Explorer 必须挑标题里带 "Explorer EV" 的 —— 欧版 Explorer 才是电车，
#     那张 12070px 的 "2024 Ford Explorer.jpg" 是别的车，不能用。
#   · EQS 挑 V297（轿车）而不是 X296（SUV）—— SIXT 那张单子写的是 EQS 4WD 轿车。
#   · Macan 挑 "Macan Turbo Electric"。
def pick(key, must=None, avoid=None):
    for c in cars_raw[key]:
        t = c["title"]
        if must and must.lower() not in t.lower(): continue
        if avoid and avoid.lower() in t.lower(): continue
        return c
    return cars_raw[key][0]

CARS = [
 dict(id="defender", seg="🇮🇸 冰岛 · 5 天", name="Land Rover Defender 110",
      klass="Premium SUV", supplier="Avis", ev=False,
      pick="KEF 9/25 08:00", drop="KEF 9/29 18:00",
      total="$1,020.00", paid="全额已付清", cxl="9/23 08:00",
      why="把「4 人 4 箱塞不进」一次解决掉的那台。冰岛环岛路的碎石段正是它的主场；"
          "而且这是四台里唯一的燃油车 —— 冰岛充电桩远不如挪威密，这一段用油车是对的。",
      img=pick("defender", must="P400SE AWD front")),
 dict(id="explorer", seg="🇳🇴 罗弗敦 · 3 天", name="Ford Explorer 4WD",
      klass="Full-size SUV · 纯电", supplier="SIXT", ev=True,
      pick="埃沃内斯 EVE 9/30 11:00", drop="莱克讷斯 Leknes 10/2 14:30",
      total="$646.14", paid="已付 $14.01 · 取车再付 $632.13", cxl="9/28 11:00",
      why="四台里最难订的一台 —— Leknes 异地还车全网只有 5 个报价（同期 Evenes 有 22 个）。"
          "EVE→Lyngvær 175 km 在一次续航内，罗弗敦 Svolvær / Leknes 都有快充。",
      img=pick("explorer", must="Explorer EV")),
 dict(id="eqs", seg="🇳🇴 特罗姆瑟 · 3 天", name="Mercedes-Benz EQS 4WD",
      klass="纯电", supplier="SIXT",  ev=True,
      pick="TOS 10/2 17:00", drop="TOS 10/5 17:00（实际 10:00 就还）",
      total="$455.59", paid="已付 $33.77 · 取车再付 $421.82", cxl="9/30 17:00",
      why="全程唯一需要提前做功课的一台：10/4 要跑 Senja 往返 500 km，10 月、山路、夜里还在外面追极光。"
          "EQS 电池约 107 kWh，但低温 + 暖风 + 爬坡会把续航按下来 → 现实里要算一次充电停留。"
          "还车约到 17:00 是免费的富余（取车 17:00 起算正好 72 小时 = 3 个计费日）。",
      img=pick("eqs", must="EQS 580", avoid="X296")),
 dict(id="macan", seg="🇳🇴 奥斯陆 · 1 天", name="Porsche Macan 4WD",
      klass="纯电 · 保证车型", supplier="SIXT", ev=True,
      pick="OSL 10/5 13:00", drop="OSL 10/6 13:00",
      total="$288.10", paid="已付 $26.45 · 取车再付 $261.65", cxl="10/3 13:00",
      why="四台里唯一「保证车型」——到店就是这台，不是 or similar。这一段最不用担心电："
          "OSL→Stange 小屋单程只 30–40 分钟。⚠️ 但还车约的是 10/6 13:00，"
          "洲际若在上午起飞必须改早到 09:00（24 小时内同为 1 个计费日，改早不涨价）。",
      img=pick("macan", must="Macan Turbo Electric")),
]

ORDERS = [
 dict(kind="车", what="Land Rover Defender 110 · Avis 🇮🇸", when="KEF 9/25 08:00 → 9/29 18:00（5 日）",
      money="$1,020.00", sub="全额已付清", cxl="9/23 08:00"),
 dict(kind="车", what="Ford Explorer 4WD · 纯电 · SIXT 🇳🇴", when="EVE 9/30 11:00 → Leknes 10/2 14:30（3 日）",
      money="$646.14", sub="已付 $14.01 · 取车 $632.13", cxl="9/28 11:00"),
 dict(kind="车", what="Mercedes-Benz EQS 4WD · 纯电 · SIXT 🇳🇴", when="TOS 10/2 17:00 → 10/5 17:00（3 日）",
      money="$455.59", sub="已付 $33.77 · 取车 $421.82", cxl="9/30 17:00"),
 dict(kind="车", what="Porsche Macan 4WD · 纯电 · 保证车型 · SIXT 🇳🇴", when="OSL 10/5 13:00 → 10/6 13:00（1 日）",
      money="$288.10", sub="已付 $26.45 · 取车 $261.65", cxl="10/3 13:00"),
 dict(kind="机票", what="北京 → 奥斯陆（洲际 9h25）", when="9/24", money="已出票", sub="", cxl="—"),
 dict(kind="机票", what="SK4787 奥斯陆 → 冰岛（SAS · 当天唯一直飞）", when="9/25 06:15 → 07:05",
      money="已出票", sub="", cxl="—"),
 dict(kind="机票", what="DY1171 冰岛 → 奥斯陆（Norwegian）", when="9/29 20:05 → 00:45+1",
      money="已出票", sub="", cxl="—"),
 dict(kind="住", what="Nordic Lodge Retreat · Lyngvær（4 房 8 床 2 卫 · ★4.92）", when="9/30 → 10/2（2 晚）",
      money="€898", sub="", cxl="9/23 起部分退"),
]

# ---------- 文案覆盖：漂亮版的叙述还停在旧方案上 ----------
# 为什么要有这一层：styles/data.js 的逐日文案是 9-02 写的，之后行程改过两轮
#   ① 9-04 SK4787 出票 → 蓝湖和雷克雅内斯半岛从 9/28、9/29 挪到 9/25，9/29 变成休息日
#   ② 9-05「舒适优先」→ 两个奥斯陆中转夜从 20 分钟车程外的 Airbnb 换成连廊直通航站楼的酒店
# 官网如果照抄旧文案，就会出现「页面上说往西开十五分钟到农舍、账单上写着机场酒店」这种自相矛盾。
# 覆盖写在这里而不是去手改生成物，这样下次重跑脚本不会把修正冲掉。
OVERRIDE_ACTS = {
 "act0": dict(lede="第一晚不看风景。落地、取箱子，顺着连廊走五分钟进酒店，把时差睡掉 —— "
                   "明早六点一刻的飞机，多睡的每一分钟都算数。真正的旅程从那班飞机开始。"),
}
OVERRIDE_DAYS = {
 "9/24": dict(body="傍晚的飞机落在 Gardermoen。不打车、不等班车 —— 顺着连廊走五分钟就是酒店。"
                   "行李不用全拆，明早六点一刻还要飞。",
              stayname="Radisson Blu Airport Hotel ×2 间",
              staymeta="酒店 · 连廊直通航站楼 · 1 间大床 + 1 间双床 · 含早 · 可退到当天 18:00",
              shots=[]),
 "9/25": dict(body="落地才七点零五 —— 这一天是白得的。先去二十分钟外的蓝湖，把长途飞行泡掉；"
                   "中午沿雷克雅内斯半岛绕一圈：两块大陆之间的一座小桥、冒着白汽的泥浆池、被浪凿出来的石头浴缸。"
                   "傍晚才进城，那座混凝土教堂被造成玄武岩柱的样子，老港边上停着一艘钢骨头做的维京船。"),
 "9/28": dict(body="黄金圈：一道裂开的大陆缝、一口每隔几分钟就炸上来的间歇泉、一条把整条河横着切断的瀑布。"
                   "蓝湖挪到第一天之后，这天从六个半小时降到五小时。晚上住 KEF 旁边那栋带热浴桶和桑拿的房子。"),
 "9/29": dict(body="什么都不排的一天。睡到自然醒，在雷市随便走走 —— 因为今晚二十点零五起飞、"
                   "午夜过后才落回奥斯陆，明早还要再飞一趟。今天越轻越好。",
              stayname="Radisson Blu Airport Hotel ×2 间",
              staymeta="酒店 · 连廊直通航站楼 · 凌晨一点进房、七点五十再走 · 可退到当天 18:00",
              shots=[]),
 "10/2": dict(body="本来想坐海岸邮轮夜航 —— 后来改成飞。上午在罗弗敦还是白得半天，"
                   "中午从 Leknes 机场还车，Widerøe 的支线小飞机五十分钟跨过北极圈，落地再提一台车。"),
 "10/6": dict(body="车就在手上，不用叫车。十三天，两个国家，四台车，大约两千四百公里 —— "
                   "从奥斯陆机场的那条连廊出发，回到同一条连廊。"),
}
for a in st["ACTS"]:
    a.update(OVERRIDE_ACTS.get(a["id"], {}))
_seen = set()
for d in st["DAYS"]:
    if d["date"] in OVERRIDE_DAYS:
        d.update(OVERRIDE_DAYS[d["date"]]); _seen.add(d["date"])
missing = set(OVERRIDE_DAYS) - _seen
if missing:
    sys.exit(f"文案覆盖对不上日期（DAYS 里没有这些）：{missing} —— 说明上游 styles/data.js 变了，去核对")
print(f"   文案覆盖：ACTS {len(OVERRIDE_ACTS)} 处 · DAYS {len(_seen)} 处")

out = f"""/* site/data.js —— 官网数据层 · 自动生成，别手改
 * 生成脚本：notes/_research/build_site.py（改数据改那三个来源，然后重跑）
 * 来源：viz/timeline.js（时刻/已订/待办）· styles/data.js（文案/图）· out_cars_imgs.json（车图+许可）
 */
const DAY0 = {json.dumps(tl['DAY0'])}, DAYN = {tl['DAYN']};
const EV      = {json.dumps(tl['EV'], ensure_ascii=False)};
const TOFILL  = {json.dumps(tl['TOFILL'], ensure_ascii=False)};
const DAYS    = {json.dumps(st['DAYS'], ensure_ascii=False)};
const ACTS    = {json.dumps(st['ACTS'], ensure_ascii=False)};
const STATS   = {json.dumps(st['STATS'], ensure_ascii=False)};
const CREDITS = {json.dumps(st['CREDITS'], ensure_ascii=False)};
const CARS    = {json.dumps(CARS, ensure_ascii=False)};
const ORDERS  = {json.dumps(ORDERS, ensure_ascii=False)};
"""
(ROOT / "site").mkdir(exist_ok=True)
(ROOT / "site/data.js").write_text(out)
print(f"→ site/data.js  {len(out):,} 字节")
print(f"   EV {len(tl['EV'])} · TOFILL {len(tl['TOFILL'])} · DAYS {len(st['DAYS'])} · ACTS {len(st['ACTS'])} · CARS {len(CARS)} · ORDERS {len(ORDERS)}")
for c in CARS:
    print(f"   {c['id']:9} {c['img']['w']}x{c['img']['h']} {c['img']['lic']:<13} {c['img']['title'][5:60]}")
