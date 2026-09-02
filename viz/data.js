/* Nordic Trip 2026 — 数据层
 * 全部数字来源：notes/PLAN-booking.md · notes/OPTIONS-stay.md · notes/OPTIONS-cars.md · notes/OPTIONS-cruise.md
 * 抓取日 2026-09-01（Playwright 实时报价）。汇率 €1=¥8.0 · $1=¥7.1 · NOK1=¥0.67
 */

const RATE = { EUR: 8.0, USD: 7.1, NOK: 0.67 };

/* ---------- 地点坐标 ---------- */
const P = {
  osl:        [60.1939,  11.1004], nannestad: [60.2214, 11.0128],
  kef:        [63.9850, -22.6056], rvk:       [64.1466, -21.9426],
  bluelagoon: [63.8804, -22.4495], thingvellir:[64.2559,-21.1300],
  geysir:     [64.3104, -20.3024], gullfoss:  [64.3271, -20.1199],
  seljaland:  [63.6156, -19.9928], skogafoss: [63.5321, -19.5114],
  hvolsvollur:[63.7500, -20.2231], vik:       [63.4187, -19.0060],
  katla:      [63.5300, -19.0500], skaftafell:[64.0166, -16.9660],
  fosshotel:  [63.9720, -16.6800], jokulsarlon:[64.0483,-16.1794],
  diamond:    [64.0430, -16.1770], hofn:      [64.2539, -15.2082],
  arnanes:    [64.2200, -15.3200], reykjanes: [64.0043, -22.5644],
  ytritunga:  [64.8020, -23.0900], arnarstapi:[64.7680, -23.6200],
  djupalon:   [64.7530, -23.9000], kirkjufell:[64.9270, -23.3100],
  budakirkja: [64.8210, -23.3860],
  eve:        [68.4913,  16.6781], svolvaer:  [68.2340, 14.5680],
  henningsvaer:[68.1540, 14.2050], leknes:    [68.1470, 13.6120],
  ballstad:   [68.0730,  13.5350], ramberg:   [68.0870, 13.2340],
  nusfjord:   [68.0330,  13.3550], hamnoy:    [67.9500, 13.1350],
  reine:      [67.9330,  13.0890], aa:        [67.8810, 12.9770],
  tromso:     [69.6492,  18.9553], brensholmen:[69.5680,18.0170],
  botnhamn:   [69.4680,  17.8330], tungeneset:[69.4790, 17.4890],
  bergsbotn:  [69.4260,  17.5500], ersfjord:  [69.4930, 17.3140],
  finnsnes:   [69.2290,  17.9800]
};

/* ---------- 逐日行程 ----------
 * spend = 当天真实要花的钱（¥，4 人合计）。stay 里的 ¥/room 已经 ×2。
 */
const DAYS = [
  {
    id:'D0', date:'9/24', wd:'周四', region:'oslo', base:'Oslo Gardermoen',
    title:'落地奥斯陆，只求近机场',
    anchor:P.nannestad,
    route:[{n:'OSL 机场',c:P.osl},{n:'Nannestad 住处',c:P.nannestad}],
    legs:[], drive:'—',
    stay:{name:'Modern. Quiet area. Large space.（Nannestad）',type:'Airbnb',rb:'3BR / 2BA',
          price:'€260 总价 · ¥1,040/room',cxl:'—',
          url:'https://www.airbnb.com/rooms/1616864516592253636',
          note:'唯一能订 1 晚的 3房2卫；酒店兜底 Thon Gardermoen 2 间房 €86–140/间（free-cxl 9/23）'},
    spend:{stay:2080}, supply:'green',
    hi:['中转睡一晚，不安排活动','9/25 一早飞 KEF'],
    watch:[]
  },
  {
    id:'D1', date:'9/25', wd:'周五', region:'iceland', base:'Reykjavík',
    title:'飞冰岛 · 雷市市区',
    anchor:P.rvk,
    route:[{n:'OSL',c:P.osl},{n:'KEF',c:P.kef},{n:'Reykjavík',c:P.rvk}],
    legs:[{k:'fly',from:P.osl,to:P.kef}], drive:'KEF→雷市 50 min',
    stay:{name:'Aurora view 3BR 2BATH Luxury down town',type:'Airbnb',rb:'3BR / 2BA',
          price:'€447 总价 · ¥1,788/room',cxl:'—',rating:'5.0',
          url:'https://www.airbnb.com/rooms/1729852848905770040',
          note:'雷市这一晚选项最多（5 个合格房源），压力最小'},
    spend:{stay:3576}, supply:'green',
    hi:['雷市市中心 · Hallgrímskirkja / 老港','这一晚不租车（次日 09:00 KEF 提车）'],
    watch:[]
  },
  {
    id:'D2', date:'9/26', wd:'周六', region:'iceland', base:'Hvolsvöllur',
    title:'提车 · 南岸瀑布线',
    anchor:P.hvolsvollur,
    route:[{n:'KEF 提车 09:00',c:P.kef},{n:'Seljalandsfoss',c:P.seljaland},
           {n:'Skógafoss',c:P.skogafoss},{n:'Hvolsvöllur 住处',c:P.hvolsvollur}],
    legs:[{k:'drive',pts:[P.kef,P.rvk,P.seljaland,P.skogafoss,P.hvolsvollur]}],
    drive:'约 250 km / 3h30',
    stay:{name:'Hlíðarból Guest House（Hvolsvöllur）',type:'Airbnb',rb:'5BR / 2BA',
          price:'€750 总价 · ¥3,000/room',cxl:'—',rating:'4.64',
          url:'https://www.airbnb.com/rooms/1554437248972293986',
          note:'⚠️ Vík 镇内 0 个 2房2卫整套房源；南岸只有 3 个合格选项，随时会变 0'},
    car:{name:'Peugeot 2008 4x4 自动挡',seg:'冰岛 KEF 取还 9/26–9/29',
         price:'$254 车价 + $100–160 全险 + $42 道路税 ≈ $400–500',cny:'¥2,840–3,550'},
    spend:{stay:6000, car:3550}, supply:'red',
    hi:['塞里雅兰瀑布（可绕到瀑布后面）','斯科加瀑布','9 月底不需要冬胎（11/1 才强制）'],
    watch:['南岸只有 3 个房源 → 排第 4 顺位下单','若 D3 改 Katla 冰洞，住 Hvolsvöllur 要早起多开 1h15，考虑换 Vík 酒店 2 间房']
  },
  {
    id:'D3', date:'9/27', wd:'周日', region:'iceland', base:'冰河湖 Jökulsárlón',
    title:'冰洞 / 冰川 · 冰河湖 + 钻石沙滩',
    anchor:P.jokulsarlon,
    route:[{n:'Hvolsvöllur',c:P.hvolsvollur},{n:'Vík（Katla 冰洞集合）',c:P.vik},
           {n:'Katla 冰洞',c:P.katla},{n:'Skaftafell',c:P.skaftafell},
           {n:'Fosshotel Glacier Lagoon',c:P.fosshotel},{n:'Jökulsárlón + 钻石沙滩',c:P.jokulsarlon}],
    legs:[{k:'drive',pts:[P.hvolsvollur,P.vik,P.skaftafell,P.fosshotel,P.jokulsarlon]}],
    drive:'约 330 km / 4h30',
    stay:{name:'Fosshotel Glacier Lagoon ×2 间房',type:'Booking 酒店',rb:'2 房 2 卫',
          price:'€508 两间总价 · ¥2,032/room',cxl:'free-cxl 到 9/25',
          note:'🔴 全程唯一没有 Airbnb 方案的一晚（Höfn–Jökulsárlón–Skaftafell 搜出 0 张卡）。离冰河湖 ~10 min。便宜替代：Árnanes（Höfn 西）¥992/room，但多开 40 min'},
    spend:{stay:4064}, supply:'red',
    hi:['🔴 天然蓝冰洞一般 11 月才开 → 9 月能做的是 Katla 冰洞（Mýrdalsjökull，Vík 出发，全年开）或冰川徒步',
        'Jökulsárlón 冰河湖 + Diamond Beach','晚上原地等极光（Fosshotel 的 10 min 车程值这个差价）'],
    watch:['🔴 最该第一个下单的一晚：free-cxl 只到 9/25，方圆 60 km 就那几家',
           '蓝冰洞 → Katla 冰洞的决定会连带改 D2/D3 住宿位置']
  },
  {
    id:'D4', date:'9/28', wd:'周一', region:'iceland', base:'Keflavík',
    title:'黄金圈 + 蓝湖，西返',
    anchor:P.reykjanes,
    route:[{n:'冰河湖',c:P.jokulsarlon},{n:'Þingvellir',c:P.thingvellir},
           {n:'Geysir',c:P.geysir},{n:'Gullfoss',c:P.gullfoss},
           {n:'Blue Lagoon',c:P.bluelagoon},{n:'Reykjanesbær 住处',c:P.reykjanes}],
    legs:[{k:'drive',pts:[P.jokulsarlon,P.vik,P.thingvellir,P.geysir,P.gullfoss,P.bluelagoon,P.reykjanes]}],
    drive:'约 480 km / 6h（最长的一天）',
    stay:{name:'3BR/2BA Reykjanesbær（KEF 旁）',type:'Airbnb',rb:'3BR / 2BA',
          price:'€424 总价 · ¥1,696/room',cxl:'—',rating:'4.92',
          url:'https://www.airbnb.com/rooms/1231709933827491677',
          note:'⚠️ 原计划想改住 Borgarnes 省次日 1.5h 车程 —— 实测 Borgarnes 8 个合格房源**全部 min-stay ≥2 晚**，1 晚订不到 → 只能住 Keflavík，斯奈山靠早出发解决'},
    spend:{stay:3392}, supply:'green',
    hi:['Þingvellir 裂谷 · Geysir 间歇泉 · Gullfoss 黄金瀑布','Blue Lagoon 泡汤（离 KEF 20 min）'],
    watch:['这一天车程最长，注意 9 月末南岸风暴封路（存 road.is）']
  },
  {
    id:'D5', date:'9/29', wd:'周二', region:'iceland', base:'Oslo Gardermoen',
    title:'🔴 斯奈山半岛 + 还车 + 飞奥斯陆（最紧的一天）',
    anchor:P.kirkjufell,
    route:[{n:'Keflavík 05:30 出发',c:P.reykjanes},{n:'Ytri-Tunga 海豹滩',c:P.ytritunga},
           {n:'Arnarstapi',c:P.arnarstapi},{n:'Djúpalónssandur',c:P.djupalon},
           {n:'Kirkjufell 草帽山',c:P.kirkjufell},{n:'Búðakirkja 黑教堂',c:P.budakirkja},
           {n:'KEF 还车 18:15',c:P.kef},{n:'OSL',c:P.osl}],
    legs:[{k:'drive',pts:[P.reykjanes,P.ytritunga,P.arnarstapi,P.djupalon,P.kirkjufell,P.budakirkja,P.kef]},
          {k:'fly',from:P.kef,to:P.osl}],
    drive:'约 7.5h 纯开车 + 3–4h 游玩 = 11–12 小时的一天',
    stay:{name:'Modern. Quiet area. Large space.（Nannestad，同 9/24 可连订）',type:'Airbnb',rb:'3BR / 2BA',
          price:'€260 总价 · ¥1,040/room',cxl:'—',
          url:'https://www.airbnb.com/rooms/1616864516592253636',
          note:'酒店兜底 Scandic Oslo Airport €141–188/间（34 个房型行有货，很宽松）'},
    spend:{stay:2080}, supply:'green',
    hi:['Keflavík → Ytri-Tunga 单程 2h45','半岛环线净开车 ~3h + 停留 3h','回 KEF 2h'],
    watch:['🔴 唯一硬前提 = Kevin 订的 KEF→OSL 起飞时间。18:35 → 这个环线做不了（只能玩 1 小时）；20:05 → 可以做，18:15 还车、19:00 到柜台',
           '9/29 冰岛日落 ~19:00，半岛最后一段会在暮色里开（54/574 铺装公路，不难但要算进去）']
  },
  {
    id:'D6', date:'9/30', wd:'周三', region:'lofoten', base:'罗弗敦（东侧或中部）',
    title:'飞 EVE · 提车 · 进罗弗敦',
    anchor:P.svolvaer,
    route:[{n:'OSL',c:P.osl},{n:'EVE 落地 10:35 · 提车 11:00',c:P.eve},
           {n:'Svolvær',c:P.svolvaer},{n:'Henningsvær',c:P.henningsvaer},{n:'Ramberg 住处',c:P.ramberg}],
    legs:[{k:'fly',from:P.osl,to:P.eve},
          {k:'drive',pts:[P.eve,P.svolvaer,P.henningsvaer,P.leknes,P.ramberg]}],
    drive:'EVE→Svolvær 165 km / 2h30；EVE→Reine 290 km / 4h15。E10 全程无渡轮、基本无收费站',
    stay:{name:'The heart of Ramberg（西侧）',type:'Airbnb',rb:'4BR / 2.5BA',
          price:'€647 / 2 晚 · ¥1,296/room/晚',cxl:'—',rating:'4.76',
          url:'https://www.airbnb.com/rooms/1170849828585814519',
          note:'东侧同价位替代：Vågan 5BR/2BA €674/2晚（¥1,348）。明确 2 卫的 rorbu 路线：Nusfjord「Village Cabin Suite Plus」€723/2晚（¥1,446，free-cxl 9/16）—— 页面明写 2 卫，但卧室数没写，订前必须问'},
    car:{name:'Ford Explorer 4WD（Full-size SUV）',seg:'罗弗敦 EVE 取 → Svolvær 还 9/30–10/2',
         price:'$644 / 3 天（含 ~$320 异地还车费）',cny:'¥4,570',
         note:'🔴 最便宜同时车最大，没有取舍。异地还车只有 6 个车源（同地还车 23 个）→ 最容易断，今天就订'},
    spend:{stay:2592, car:4570}, supply:'amber',
    hi:['Henningsvær 渔村（绕路值得）','原计划 D6 直接到 Reine 会近天黑 → 建议住中部/西侧 Ramberg 只搬一次箱子'],
    watch:['挪威交规：全天开近光灯 · 乡道默认 80 · 超 10 km/h 罚款 >NOK 2,500 · 酒驾 0.02% 近乎零容忍 · 单车道 møteplass 上坡优先 · 注意驯鹿和羊']
  },
  {
    id:'D7', date:'10/1', wd:'周四', region:'lofoten', base:'罗弗敦（西侧）',
    title:'Reine / Hamnøy / Å —— 明信片那一侧',
    anchor:P.reine,
    route:[{n:'Ramberg',c:P.ramberg},{n:'Nusfjord',c:P.nusfjord},{n:'Hamnøy',c:P.hamnoy},
           {n:'Reine（Reinebringen）',c:P.reine},{n:'Å i Lofoten',c:P.aa}],
    legs:[{k:'drive',pts:[P.ramberg,P.nusfjord,P.hamnoy,P.reine,P.aa]}],
    drive:'约 120 km 往返 / 2h 净开车',
    stay:{name:'同 D6（连订 2 晚，不搬箱子）',type:'Airbnb',rb:'4BR / 2.5BA',
          price:'含在 €647 / 2 晚内',cxl:'—',
          note:'罗弗敦是供给最好的一段：22 个合格 2房2卫房源。Sakrisøy Rorbuer / Reinefjorden Sjøhus 9/30–10/1 已确认卖完'},
    spend:{stay:2592}, supply:'amber',
    hi:['Hamnøy 那排最出名的红屋（Eliassen Rorbuer）','Reinebringen 阶梯（约 1.5–2h 往返）','晚上极光季已开季'],
    watch:['Hattvika / Eliassen / Svinøya 的卫生间数量 Booking 页面没写 → 要发邮件问']
  },
  {
    id:'D8', date:'10/2', wd:'周五', region:'cruise', base:'🚢 船上（Havila）',
    title:'🔴 还车 → Svolvær 22:15 上船',
    anchor:P.svolvaer,
    route:[{n:'罗弗敦西侧',c:P.reine},{n:'Leknes',c:P.leknes},
           {n:'Svolvær 还车 + 码头',c:P.svolvaer},{n:'夜航北上',c:[68.9,15.6]}],
    legs:[{k:'drive',pts:[P.reine,P.leknes,P.svolvaer]},
          {k:'cruise',pts:[P.svolvaer,[68.80,15.30],[69.05,15.60],[69.32,16.10],[69.65,18.10],P.tromso]}],
    drive:'回 Svolvær ~2h · 22:15 开船',
    stay:{name:'Havila 邮轮 ×2 间双人舱（port-to-port）',type:'邮轮',rb:'2 舱 4 人',
          price:'⚠️ 价格未验证 · 对标 Hurtigruten 4 人 ¥8,800–11,900',cxl:'分票种，FLEX 可改',
          note:'🔴 10/2 那班船不是 Hurtigruten 是 **Havila** —— Hurtigruten 那天根本没有 Svolvær 出发的船（API 查证：班期只有 9/22、23、25、27、30、10/3、4、6、8）。11 条船轮转 11 天，每天只有一家公司的船'},
    spend:{cruise:12000}, supply:'red',
    hi:['22:15 开船 → 次日 14:15 抵 Tromsø，整个上午在船上看 Vesterålen 海岸线','省一晚陆上住宿'],
    watch:['🔴 Svolvær 门店周五多数 15:30–16:00 就关门 → 22:15 开船，必须问清关门时间或改钥匙箱还车',
           '🔴 Cloudflare 挡住本机拿 Havila 实时价 → 必须用家用网/手机开 havilavoyages.com/nb/havn-til-havn，或邮件 booking@havilavoyages.com / 电话 +47 815 33 300',
           '要问 4 件事：还有几间舱 · 2 间双人舱总价 · 含不含早餐 · 退改政策',
           '🔴 一间舱装不下 4 人（API 返回空）→ 必须 2 舱']
  },
  {
    id:'D9', date:'10/3', wd:'周六', region:'tromso', base:'Tromsø',
    title:'14:15 抵特罗姆瑟 · 市区',
    anchor:P.tromso,
    route:[{n:'船抵 Tromsø 14:15',c:P.tromso}],
    legs:[], drive:'—',
    stay:{name:'Houseboat in Tromsø（住船上）',type:'Airbnb',rb:'3BR / 3BA',
          price:'€825 / 3 晚 · ¥1,100/room/晚',cxl:'—',rating:'5.0',
          url:'https://www.airbnb.com/rooms/1607078897559083655',
          note:'卫生间比人还多。替代：5BR/2.5BA €1,155/3晚（¥1,540）；酒店兜底 Thon Polar 2 间房 €690–908/3晚（free-cxl 10/2）；公寓锚 Enter Amalie Three-Bedroom Loft €925（¥1,233，不可退）'},
    spend:{stay:2200}, supply:'amber',
    hi:['北极大教堂 · Fjellheisen 缆车 · Polaria','晚上市区看极光'],
    watch:['✅ 顺手确认：Vervet Apartments 没有闭店（10/3–10/6 正常放房，free-cxl 到 9/19）',
           'Enter Viking 的 free-cxl 只到 9/3 —— 要用就今天定']
  },
  {
    id:'D10', date:'10/4', wd:'周日', region:'tromso', base:'Tromsø',
    title:'提车（提前一天）· 自由追极光',
    anchor:P.tromso,
    route:[{n:'TOS 机场提车 09:00',c:P.tromso}],
    legs:[], drive:'市区 + 郊外追极光',
    stay:{name:'同 D9（Houseboat，3 晚连住）',type:'Airbnb',rb:'3BR / 3BA',price:'含在 €825 / 3 晚内',cxl:'—'},
    car:{name:'Toyota RAV4 4x4 混动',seg:'特罗姆瑟 TOS 取还 10/4 09:00 → 10/6 09:00',
         price:'$261 / 2 天',cny:'¥1,850',
         note:'租 2 天几乎和租 1 天一样贵（单日 Ford Explorer $141）→ 多花 $30–120 换 10/4 晚一个自由追极光的夜。🔴 别订电车：Senja 往返 ~500 km、10 月初、岛上充电桩很稀 → 选汽油/混动'},
    spend:{stay:2200, car:1850}, supply:'green',
    hi:['自己有车 = 不被 tour 时间表绑住','挪威租车基本不限里程'],
    watch:[]
  },
  {
    id:'D11', date:'10/5', wd:'周一', region:'tromso', base:'Tromsø',
    title:'Senja 自驾一日（硬仗）',
    anchor:P.tungeneset,
    route:[{n:'Tromsø 07:00 出发',c:P.tromso},{n:'Brensholmen 渡轮',c:P.brensholmen},
           {n:'Botnhamn',c:P.botnhamn},{n:'Bergsbotn 观景台',c:P.bergsbotn},
           {n:'Tungeneset',c:P.tungeneset},{n:'Ersfjordstranda',c:P.ersfjord},
           {n:'回程（Finnsnes 陆路可选）',c:P.finnsnes}],
    legs:[{k:'drive',pts:[P.tromso,P.brensholmen]},
          {k:'ferry',pts:[P.brensholmen,P.botnhamn]},
          {k:'drive',pts:[P.botnhamn,P.bergsbotn,P.tungeneset,P.ersfjord,P.bergsbotn,P.finnsnes,P.tromso]}],
    drive:'约 500 km 往返 · 路上 5–6h，只剩 4–5h 玩',
    stay:{name:'同 D9（Houseboat，最后一晚）',type:'Airbnb',rb:'3BR / 3BA',price:'含在 €825 / 3 晚内',cxl:'—'},
    spend:{stay:2200, other:430}, supply:'green',
    hi:['✅ Brensholmen–Botnhamn 渡轮 2026 全年运营（不是季节性停开）· NOK 228/车/单程 · 航程 35–45 min',
        '开：08:45 / 10:45 / 12:45(周五停) / 15:00 / 17:00 / 19:00 / 20:45；回：08:00 / 09:45 / 11:45(周五停) / 14:00 / 16:00 / 18:00 / 20:00',
        '10/5 是周一，不受「周五停」影响',
        '陆路 Finnsnes / Gisund 大桥 ~2h30–3h，时间自由但慢'],
    watch:['10/5 特罗姆瑟日出 07:25 / 日落 18:15（10h50 日照）→ 07:00 出发是对的，别再晚',
           '出发前一周再核一次 Torghatten Nord / Entur 班次']
  }
];

/* ---------- 抢库存顺序（按会先卖光排） ---------- */
const URGENCY = [
  {rank:1, sev:'red',   what:'Havila 邮轮 10/2 Svolvær 22:15 → Tromsø ×2 舱',
   why:'port-to-port 舱位极少，卖光整段行程断掉；且本机拿不到实时价，必须人工去订',
   deadline:'今天', how:'家用网开 havilavoyages.com/nb/havn-til-havn，或 booking@havilavoyages.com / +47 815 33 300'},
  {rank:2, sev:'red',   what:'Fosshotel Glacier Lagoon 9/27 两间房',
   why:'全程唯一没有 Airbnb 方案的一晚，方圆 60 km 就那几家',
   deadline:'free-cxl 到 9/25', how:'Booking.com，两间 Standard Double/Twin €508'},
  {rank:3, sev:'red',   what:'罗弗敦租车 EVE→Svolvær（Ford Explorer 4WD $644）',
   why:'异地还车只有 6 个车源（同地还车 23 个），最容易断',
   deadline:'今天', how:'DiscoverCars，可免费取消'},
  {rank:4, sev:'amber', what:'罗弗敦住宿 9/30–10/1',
   why:'秋色 + 极光季；Hattvika 的 free-cxl 已经是 9/16，比别家早',
   deadline:'9/16 前', how:'先订可退的 Airbnb（Ramberg 4BR/2.5BA €647/2晚）'},
  {rank:5, sev:'amber', what:'特罗姆瑟 3 晚 10/3–10/5',
   why:'极光季开季，Houseboat 这种独一份的先没；Enter Viking free-cxl 只到 9/3',
   deadline:'9/3（若用 Enter Viking）', how:'Airbnb Houseboat €825/3晚 优先'},
  {rank:6, sev:'amber', what:'南岸 9/26',
   why:'只有 3 个合格选项，等于随时会变成 0 个',
   deadline:'尽快', how:'Hlíðarból Guest House €750'},
  {rank:7, sev:'green', what:'冰岛租车 9/26–9/29（Peugeot 2008 4x4 auto）',
   why:'16 个车源还算宽松，但 9 月底旺季尾巴',
   deadline:'本周', how:'线上先买 SCDW+GP+SAAP，比柜台加保便宜'},
  {rank:8, sev:'green', what:'Gardermoen 9/24 + 9/29、Keflavík 9/28、特罗姆瑟租车',
   why:'供给最充足，可以等决策定了再订',
   deadline:'决策后', how:'—'}
];

/* ---------- 邮轮三方案 ---------- */
const CRUISE_OPT = [
  {name:'✅ Havila 10/2 + 2 舱（推荐）', transport:'未知（对标 ¥12,000）', dropfee:'+$320', total:'≈¥14,300?',
   pro:'唯一不动其它任何预订的选项；保持原行程、省一晚酒店、整个上午看 Vesterålen 海岸线', con:'价格未验证'},
  {name:'备选 A：Hurtigruten 10/3', transport:'$2,252（只剩 ArcticSuperior $563/人）', dropfee:'+$320', total:'≈¥18,200',
   pro:'舱位实时可订', con:'⛔ 整段后移一天 → Lofoten 多住一晚、Tromsø 少一晚，选好的 3 晚要整段重订。贵还要动住宿'},
  {name:'备选 B：飞 SVJ→TOS（Widerøe 直飞，待查）', transport:'~NOK 3,200–14,800', dropfee:'$0（省掉异地费）', total:'≈¥3,000–14,000',
   pro:'快（直飞 ~50 min）；同地还车最便宜 4x4 自动挡 Toyota Urban Cruiser 只 $167/3天',
   con:'Google Flights 卖不了 Widerøe 支线（不进 GDS）→ 必须去 wideroe.no 自己查。LKN/SVJ 班次极少，少了海岸线'}
];

/* ---------- Hurtigruten 价格锚（已验证，API 可复算） ---------- */
const HRG = [
  {d:'9/22', ship:'Nordlys',      inside:null, outside:418, sup:null},
  {d:'9/23', ship:'Nordkapp',     inside:null, outside:351, sup:540},
  {d:'9/25', ship:'Polarlys',     inside:310,  outside:364, sup:563},
  {d:'9/27', ship:'Richard With', inside:null, outside:418, sup:null},
  {d:'9/30', ship:'Kong Harald',  inside:null, outside:418, sup:563},
  {d:'10/1', ship:'— 无船（Havila 日）', inside:null, outside:null, sup:null},
  {d:'10/2', ship:'— 无船（Havila 日）★我们要坐的那天', inside:null, outside:null, sup:null},
  {d:'10/3', ship:'Nordlys',      inside:null, outside:null, sup:563},
  {d:'10/4', ship:'Nordkapp',     inside:null, outside:418, sup:563},
  {d:'10/6', ship:'Polarlys',     inside:310,  outside:364, sup:563},
  {d:'10/8', ship:'Richard With', inside:310,  outside:418, sup:563}
];

/* ---------- 未决问题 ---------- */
const OPEN = [
  {sev:'red',   q:'Kevin 订的 KEF→OSL 9/29 起飞时间？', why:'唯一决定 9/29 能不能跑斯奈山半岛的硬前提。18:35 → 做不了；20:05 → 可以', who:'Kevin'},
  {sev:'red',   q:'Havila 10/2 还有几间舱 / 2 间双人舱总价 / 含不含早餐 / 退改政策？', why:'整段行程能不能成立取决于它；本机被 Cloudflare 挡，拿不到价', who:'Steve（家用网或电话）'},
  {sev:'red',   q:'Svolvær 各租车门店 10/2（周五）关门时间？', why:'22:15 开船，多数门店 15:30–16:00 就关 → 要么钥匙箱还车，要么提前还车打车去码头', who:'邮件/电话'},
  {sev:'red',   q:'Nusfjord「Village Cabin Suite Plus」到底几间卧室？', why:'2 卫已确认（页面明写），卧室数没写。是全罗弗敦「明确 2 卫 + 在预算内」的唯一确定答案；若是 1 卧 2 卫就退回 Airbnb', who:'邮件'},
  {sev:'amber', q:'D3 蓝冰洞 → Katla 冰洞的决定？', why:'天然蓝冰洞一般 11 月才开。换 Katla 后集合点变 Vík → 连带改 D2/D3 住宿位置', who:'Steve + Kevin 找票'},
  {sev:'amber', q:'Rent a Car Lofoten（Svolvær 本地）的 EVE→Svolvær 异地费？', why:'本地小公司常显著低于国际品牌的 $320', who:'邮件'},
  {sev:'amber', q:'Hattvika / Eliassen / Svinøya 的卫生间数量？', why:'Booking 页面没写。「一定要 2 卫」目前只能靠 Airbnb 那批（明写 2BA/2.5BA/3BA）', who:'邮件'},
  {sev:'amber', q:'冰岛 SCDW+GP+SAAP 打包价准确数字 + 第二驾驶员是否免费？', why:'各家差很多，柜台加保最贵，线上先买便宜', who:'各家官网'},
  {sev:'green', q:'挪威两段是否含 AutoPASS 标签，手续费怎么收？', why:'E10 这段几乎没收费站，金额很小', who:'租车公司'},
  {sev:'green', q:'酒店那几行的 €/$ 是单间价还是两间总价？', why:'Radisson 两家返回 USD 而非 EUR，说明它忽略了货币参数 → 下单前页面上再核一眼', who:'下单时'},
  {sev:'green', q:'Torghatten Nord 官网核 10/5 Brensholmen–Botnhamn 确切班次', why:'低季会改点', who:'出发前一周'}
];

/* ---------- 风险 ---------- */
const RISKS = [
  {r:'Havila 10/2 舱位卖光', imp:'D8–D9 整段断，且没有等价替代', act:'第一个去查，今天就查', sev:'red'},
  {r:'D5 斯奈山赶飞机', imp:'误机 / 全天在车上', act:'先确认 KEF→OSL 起飞时间；20:05 才做，18:35 就砍掉半岛', sev:'red'},
  {r:'蓝冰洞 9 月不开', imp:'D3 白跑', act:'换 Katla 冰洞（Vík 出发，全年开）→ 连带改 D2/D3 住宿', sev:'amber'},
  {r:'Svolvær 门店 10/2 提前关门', imp:'还不掉车 → 上不了船', act:'询价时一并问关门时间', sev:'amber'},
  {r:'罗弗敦 2 卫房源卖光', imp:'退到 1 卫或 2 间连通房', act:'接受兜底方案，别死磕', sev:'amber'},
  {r:'秋季风暴封路（冰岛南岸 / E10）', imp:'单日行程作废', act:'订可免费取消的房；存 road.is 和 vegvesen.no', sev:'amber'},
  {r:'~~中国驾照无 IDP，租车公司拒租~~', imp:'—', act:'✅ 已消除：用美国驾照，冰岛/挪威都直接认，不需要 IDP', sev:'done'},
  {r:'~~9 月底冰岛要不要冬胎~~', imp:'—', act:'✅ 已消除：11/1 起才强制，这个日期不需要', sev:'done'},
  {r:'~~Brensholmen 渡轮季节性停开~~', imp:'—', act:'✅ 已消除：2026 全年运营，10/5 周一不受「周五停」影响', sev:'done'},
  {r:'~~Vervet Apartments 2026-08→2027-08 闭店~~', imp:'—', act:'✅ 已消除：实测 10/3–10/6 正常放房正常报价，那条信息是错的', sev:'done'}
];

/* ---------- 黑话表 ---------- */
const GLOSSARY = [
  ['rorbu','罗弗敦传统红色渔屋改的自炊小屋，通常带厨房，是当地主流住宿形态'],
  ['port-to-port','港到港：只买挪威海岸邮轮的一段船票，不是买 6–12 天的整趟巡游'],
  ['deck space','甲板票 / 无舱位票：只买船票不要房间，通宵靠躺椅'],
  ['free-cxl','可免费取消的截止日期'],
  ['min-stay','房东设的最少入住晚数，比你要住的天数长就订不了'],
  ['AutoPASS','挪威高速自动收费，车上有电子标签，租车公司事后从卡上扣，另加手续费'],
  ['CDW','车损免责，含在车价里，但有自付额'],
  ['SCDW','把 CDW 的自付额再降低'],
  ['GP','Gravel Protection：碎石打伤车漆/前挡，冰岛特有，标准 CDW 不赔'],
  ['SAAP','Sand & Ash Protection：火山沙尘暴磨伤车身，冰岛特有，标准 CDW 不赔'],
  ['einveisleie','挪威语「异地还车费」'],
  ['møteplass','挪威单车道公路的会车位。上坡车优先，别停在会车位里'],
  ['PolarInside / PolarOutside / ArcticSuperior','Hurtigruten 舱型：内舱无窗 / 外舱有窗 / 高一档位置更好'],
  ['不限里程','Unlimited mileage，挪威冰岛基本都是']
];

/* ---------- 数据来源 ---------- */
const PROV = [
  ['Airbnb 实时房源','Playwright，URL 里强制 min_bedrooms≥2 & min_bathrooms≥2 & 整套房源，并用经纬度框锁死地理范围（避免 Airbnb 把「Vík」搜成 2.5h 外的 Selfoss）','notes/_research/abnb_scrape.py'],
  ['Booking.com 房型行','逐物业房型页抓真实房价行 + free-cxl 日期。修正过 8 个错 slug（svinoya 不是 svinoya-rorbuer、nusfjord-as、ta-vervet-apartment…）','notes/_research/bk_prop.py'],
  ['Hurtigruten 实时舱价','⭐ 直接 POST 它的可用性 API（无签名、可复算），几秒出一整周班期+舱型价','notes/_research/hrg_api.py'],
  ['Havila','四条路全部被 Cloudflare 挡（403 / Flutter CanvasKit 零 DOM / main.dart.js 403）→ 必须人工','notes/_research/havila_*.py'],
  ['DiscoverCars 实时车价','搜索结果页 sq 参数里 Hash 字段为空 = 未签名，路径 UUID 不校验 → 可自拼 payload 拿真实报价。地点 ID：KEF 1787 · EVE 2088 · Svolvær 2092 · TOS 2195','notes/_research/dc_direct.py'],
  ['航班','Google Flights 实时（注意它卖不了 Widerøe 支线，SVJ→TOS 直飞要去 wideroe.no）','notes/_research/flights_gf.py']
];

const PITFALLS = [
  'Hurtigruten 的出发日期框是掩码输入：写 10/02/2026 会被读成 02/10/2026 并报 "Date must be today or later"，搜索按钮永远 disabled。能用的写法是不带斜杠的 02102026（DMY 纯数字）。→ 每次写完日期都要回读 + 检查搜索按钮是否可点。',
  'DiscoverCars 首页表单点日历点不动（react-date-range），日期没生效 → 拿到的是默认 9/04–9/12 的价，看起来正常其实全错。同一类错误。',
  'Kayak 深链全部重定向回首页；DiscoverCars 带参数的 URL 404。别重试。',
  '一间邮轮舱装不下 4 个人：用 1 舱 4 人查，API 返回 200 但结果为空 → 必须 2 舱。',
  'Airbnb 不锁经纬度框就会把「Vík」搜成 2.5 小时外的 Selfoss，返回一堆看起来合格实际开不到的房源。'
];

/* ================================================================
 * 需要人拍板的问题 —— 从四份文档里抽出来，附出处 file:line
 * kind: 'block' = 不定就没法订 / 订了要重订（会改行程结构）
 *       'detail' = 不定也能先订（都可免费取消），只影响某一项的钱或舒适度
 * ================================================================ */
const BLOCKERS = [
  {id:'B1', kind:'block', sev:'red',
   q:'Kevin 订的 KEF→OSL 9/29 航班是几点起飞？',
   blocks:'9/29 斯奈山半岛到底做不做',
   detail:'从 Keflavík 05:30 出发跑完半岛（Ytri-Tunga 海豹滩 2h45 + 环线净开车 3h + 停留 3h + 回 KEF 2h）= 11–12 小时的一天，18:00–18:30 回 KEF 还车。傍晚常见班次是 ~18:35（Norwegian/SAS）和 ~20:05（Norwegian）。',
   ifUnknown:'<b>18:35 → 这个环线做不了</b>（要 16:00 前回 KEF，等于只能玩 1 小时，只能砍掉半岛留在雷市）；<b>20:05 → 可以做</b>，18:15 还车、19:00 到柜台刚好。它还顺带决定冰岛租车的还车时间怎么填。',
   who:'Kevin（票是他订的）',
   days:['D4','D5'],
   src:[['notes/OPTIONS-stay.md','25–46（结论在第 43 行：「请先跟 Kevin 确认航班号和起飞时间」）'],
        ['notes/PLAN-booking.md','34（§0② 三处地理打结的第一处 D4→D5）'],
        ['notes/OPTIONS-stay.md','256（§四 待办第 1 条）']],
   nowdo:'先按 20:05 那套订（车和房都可免费取消），拿到时间再决定砍不砍。'},

  {id:'B2', kind:'block', sev:'red',
   q:'Havila 10/2 Svolvær 22:15 那班：还有几间舱？2 间双人舱总价？含不含早餐？退改政策？',
   blocks:'D8–D9 整段，以及连带的罗弗敦还车地点、$320 异地还车费、Tromsø 3 晚的起始日',
   detail:'10/2 那班船不是 Hurtigruten 是 <b>Havila</b>（Hurtigruten 那天根本没有 Svolvær 出发的船）。而 <b>本机拿不到 Havila 的实时价</b>——Cloudflare 把这个 pod 挡在它的订票引擎外（订票按钮跳到另一个域的 Flutter/CanvasKit 应用，零 DOM，main.dart.js 返回 403）。所以这一条<b>只能人去问</b>，没有技术办法绕。',
   ifUnknown:'拿不到就要在两个备选里挑，<b>两条都会动已经选好的预订</b>：备选 A（Hurtigruten 10/3）整段后移一天 → Tromsø 那 3 晚要整段重订，还贵 ¥4,000；备选 B（飞 SVJ→TOS）要把罗弗敦租车改成同地还车（省 $320），但 Widerøe 直飞的票价本身也还没验证。',
   who:'Steve 本人 —— 用<b>家用网/手机</b>开 havilavoyages.com/nb/havn-til-havn →「Bestill havn-til-havn」（Cloudflare 只挡这个 pod）；或邮件 booking@havilavoyages.com；或电话 +47 815 33 300',
   days:['D8','D9'],
   src:[['notes/OPTIONS-cruise.md','30–61（§1 「价格未验证，必须人工确认」，行动项在 56–59）'],
        ['notes/OPTIONS-cruise.md','104–141（§3 两个备选的代价已量化）'],
        ['notes/PLAN-booking.md','83 + 155（Phase 2 第 1 位 + 风险清单第 1 条）']],
   nowdo:'今天就打。这是整个行程的单点故障，也是唯一一条「没有 plan B 能不动其它预订」的。'},

  {id:'B3', kind:'block', sev:'red',
   q:'Svolvær 各租车门店 10/2（周五）几点关门？',
   blocks:'D8 当天几点必须离开罗弗敦西侧 → 直接决定 D7/D8 能玩到几点',
   detail:'邮轮 22:15 开船，但 Svolvær 各家门店周五关门时间不一，<b>多数 15:30–16:00 就关</b>。我给的 Ford Explorer $644 是<b>按 17:00 还车</b>报的价。',
   ifUnknown:'如果真是 15:30 关门，那就等于<b>要提前 6 个多小时还车</b>，然后拖着行李在 Svolvær 等到晚上 —— 要么改成机场式钥匙箱还车，要么提前还车再打车去码头。这条不问清，D8 的时间表是假的。',
   who:'邮件/电话问 Svolvær 门店（Avis / Hertz / Sixt / Budget，或本地 Rent a Car Lofoten）',
   days:['D7','D8'],
   src:[['notes/OPTIONS-cars.md','111–112（§二 「这条必须问」）'],
        ['notes/OPTIONS-cars.md','179–180（§五 必须发邮件问的第 1 条）'],
        ['notes/PLAN-booking.md','101 + 160（Phase 3 + 风险清单）']],
   nowdo:'和 B2 一起问 —— 如果最后走备选 B（飞 SVJ→TOS）就同地还车，这条自动消失。'},

  {id:'B4', kind:'block', sev:'red',
   q:'D3（9/27）蓝冰洞换不换成 Katla 冰洞？',
   blocks:'D2 和 D3 的住宿位置',
   detail:'<b>天然蓝冰洞（瓦特纳冰川）一般 11 月才开</b>。9 月能做的是 <b>Katla 冰洞</b>（Mýrdalsjökull 冰川下，全年开）或冰川徒步 —— 但 Katla 的<b>集合点在 Vík，不是 Skaftafell</b>。',
   ifUnknown:'现在方案 D2 住 Hvolsvöllur（离 Vík 还有 1h15 回头路）。若确定换 Katla，D2 该改住 <b>Vík 的酒店 2 间房</b>（Hótel Vík í Mýrdal / Hótel Katla，报价还没抓）—— 而 Vík 镇内 <b>0 个</b> 2房2卫整套房源，所以只能走酒店路线。不换的话 D3 就是白跑一趟。',
   who:'Steve + Kevin（Kevin 在找票）',
   days:['D2','D3'],
   src:[['notes/PLAN-booking.md','35（§0② 第二处打结）+ 159（风险清单）'],
        ['notes/OPTIONS-stay.md','84–85（南岸那晚的替代建议）'],
        ['notes/OPTIONS-stay.md','264 + 267（§四 待办最后两条）']],
   nowdo:'先订 9/27 的 Fosshotel（free-cxl 到 9/25，不冲突），只有 D2 那晚要等这个决定。'},

  {id:'B5', kind:'block', sev:'red', scope:'global',
   q:'住宿接不接受非酒店（Airbnb / rorbu 自炊）？罗弗敦要不要搬一次箱子？',
   blocks:'整套住宿方案的地基 —— 12 晚里有 9 晚是 Airbnb',
   detail:'现在这套 ¥32,976 的组合建立在 <b>A 方案（Airbnb / 公寓 2房2卫）</b>上。北欧酒店套房基本都是 1 卫，能真正拿到 2 卫只有三条路：A 公寓、B 大号 <abbr title="罗弗敦传统红色渔屋改的自炊小屋">rorbu</abbr>、C 两间相连酒店房。另外原计划是 D6 住 Svolvær 侧 + D7 挪到 Reine 侧，我改成了<b>连住 Ramberg 不搬箱子</b>。',
   ifUnknown:'如果只接受酒店，A 方案基本没了 → 整体换成 C 方案（2 间连通房，2 卫自动成立），<b>价格结构和每晚位置全变</b>，而且没厨房（挪威 4 人自炊能省很多）。这条不定，下面所有住宿链接都可能白订。',
   who:'Steve',
   days:['D0','D1','D2','D4','D5','D6','D7','D9','D10','D11'],
   src:[['notes/PLAN-booking.md','167–173（§5 待 Steve comment 的 7 条，尤其第 5、6 条）'],
        ['notes/PLAN-booking.md','16–28（§0① 「2 个卫生间」三条路 A/B/C）'],
        ['notes/OPTIONS-stay.md','221–237（§二 性价比最高的一套组合）']],
   nowdo:'默认按 A 优先、抢不到就 C 兜底执行。你说一句「接受/不接受」就够。'},

  {id:'B6', kind:'block', sev:'amber',
   q:'Nusfjord「Village Cabin Suite Plus」到底几间卧室？',
   blocks:'罗弗敦 2 晚选哪家（有替代，所以不致命）',
   detail:'它是<b>全罗弗敦唯一在 Booking 页面上明写「2 bathrooms」</b>的房源，€723/2晚（¥1,446/room/晚，free-cxl 到 9/16）。但<b>卧室数没写</b> ——「Suite」不等于 2 卧。',
   ifUnknown:'如果是 1 卧 2 卫，就退回 Airbnb 那批（Ramberg 4BR/2.5BA €647/2晚，页面明确标了 2.5BA）。所以这条只是「能不能用那个最优解」，不会让行程断。',
   who:'邮件问 Nusfjord Arctic Resort',
   days:['D6','D7'],
   src:[['notes/OPTIONS-stay.md','164–181（§D6–D7 补充，结论在 180–181）'],
        ['notes/OPTIONS-stay.md','258–259（§四 待办，标了 🔴）']],
   nowdo:'先把 Airbnb Ramberg 那个占住（可退），Nusfjord 回信了再换。'}
];

/* 只影响某一项的细节 —— 不定也能先订（都可免费取消） */
const DETAILS = [
  {q:'Rent a Car Lofoten（Svolvær 本地）的 EVE→Svolvær 异地费是多少？', why:'本地小公司常显著低于国际品牌实测的 $320 —— 有可能省几百美元',
   who:'邮件', src:[['notes/OPTIONS-cars.md','106–107 + 181']]},
  {q:'Hattvika Lodge / Eliassen Rorbuer / Svinøya Rorbuer 的卫生间数？', why:'Booking 页面没写。「一定要 2 卫」目前只能靠 Airbnb 那批（明写 2BA/2.5BA/3BA）',
   who:'邮件', src:[['notes/OPTIONS-stay.md','161 + 257']]},
  {q:'冰岛 SCDW + GP + SAAP 打包价的准确数字？第二驾驶员免不免费？', why:'各家差很多，柜台加保最贵 → 线上先买便宜。目前按 $100–160 估',
   who:'各家租车官网', src:[['notes/OPTIONS-cars.md','182–183 + 68–76']]},
  {q:'挪威两段是否含 AutoPASS 标签，手续费怎么收？', why:'E10 这段几乎没收费站，金额很小 —— 知道就行，不影响选择',
   who:'租车公司', src:[['notes/OPTIONS-cars.md','184 + 116']]},
  {q:'酒店那几行的 €/$ 到底是单间价还是两间总价？', why:'Radisson 两家返回 USD 而不是 EUR，说明网站忽略了货币参数 → 下单前在页面上再核一眼',
   who:'下单时自己核', src:[['notes/OPTIONS-stay.md','265–266']]},
  {q:'Torghatten Nord 官网核 10/5 Brensholmen–Botnhamn 的确切班次', why:'低季会改点。已确认 2026 全年运营、10/5 周一不受「周五停」影响',
   who:'出发前一周', src:[['notes/OPTIONS-cars.md','185'],['notes/OPTIONS-cruise.md','145–153']]},
  {q:'Widerøe SVJ→TOS 直飞的真实票价（wideroe.no）', why:'只有走备选 B（不坐船）才需要。Google Flights 卖不了 Widerøe 支线（不进 GDS），官网区间 NOK 1,819–3,699/人',
   who:'wideroe.no', src:[['notes/OPTIONS-cruise.md','112–124']]}
];

/* 已经拍板 / 已经查实 —— 别再重新讨论一遍 */
const SETTLED = [
  {q:'几个人、怎么分房？', a:'<b>4 人 = 两男 + 一对夫妻 → 2 room / 2 cabin。</b>所有报价的「¥/room」都是整套总价 ÷ 2。',
   src:[['notes/PLAN-booking.md','167（原问题）'],['notes/OPTIONS-stay.md','8（口径）']]},
  {q:'驾照国别 / 要不要国际驾照 IDP？', a:'<b>美国驾照，冰岛和挪威都直接认，不需要 IDP。</b>原来那个「中国驾照没有 IDP → 三段自驾全废」的最大风险<b>已消除</b>。',
   src:[['notes/OPTIONS-cars.md','188'],['notes/PLAN-booking.md','72–74（原风险）']]},
  {q:'D4 改住 Borgarnes 省次日 1.5h 车程？', a:'<b>不可执行</b> —— Borgarnes 一带 8 个 2房2卫房源<b>全部 min-stay ≥ 2 晚</b>，1 晚订不到。→ 9/28 只能住 Keflavík，斯奈山靠早出发解决（见 B1）。',
   src:[['notes/OPTIONS-stay.md','20–23'],['notes/PLAN-booking.md','34 + 75（原方案）']]},
  {q:'免费取消 vs 更便宜的不可退？', a:'<b>全部买可免费取消</b>（我的建议，已按这个执行）。9 月末冰岛南岸和 E10 的风暴封路太常见，省下的那点不可退折扣不值得。<b>你反对就说一声。</b>',
   src:[['notes/PLAN-booking.md','173'],['notes/OPTIONS-stay.md','249–250']]},
  {q:'9 月底冰岛要不要冬胎？', a:'<b>不需要</b> —— 法律 11/1 起才强制。',
   src:[['notes/OPTIONS-cars.md','189']]},
  {q:'Brensholmen–Botnhamn 渡轮是季节性停开吗？', a:'<b>不是，2026 全年运营</b>。NOK 228/车/单程，航程 35–45 min。10/5 是周一，不受「周五停」影响。',
   src:[['notes/OPTIONS-cruise.md','145–153']]},
  {q:'Vervet Apartments 是不是 2026-08→2027-08 闭店？', a:'<b>没有闭店</b> —— 实测 10/3–10/6 正常放房正常报价（€535/3晚起，free-cxl 到 9/19）。那条 listing 信息是错的或已作废。',
   src:[['notes/OPTIONS-stay.md','214–215'],['notes/PLAN-booking.md','99（原疑问）']]},
  {q:'treg.to/people-search 要不要装？', a:'<b>不装</b> —— 那是 B2B 销售线索/SEO 数据平台（找人的工作邮箱电话），覆盖范围里<b>没有任何旅行/酒店/租车/机票数据源</b>，走错门了。真正需要的是能跑 JS 的浏览器读实时报价，本机 Playwright 已经有。',
   src:[['notes/PLAN-booking.md','38–50']]}
];
