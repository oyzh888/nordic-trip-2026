/* Nordic Trip 2026 — 数据层
 * 唯一权威来源：notes/PLAN-final.md（住宿 + 租车最终方案）
 * 候选池 / 被否掉的：notes/OPTIONS-stay.md · notes/OPTIONS-cars.md
 * 抓取日 2026-09-01（Playwright 打开真实页面、按真实日期抓的）。
 * 汇率 €1=¥8.0 · $1=¥7.1 · NOK1=¥0.67
 *
 * 🔴 与旧版（2026-09-01 上午那版）的区别：
 *   ① 游轮整段 pass 掉 → 10/2 改为 Svolvær→特罗姆瑟自驾，并并进船屋成 4 晚
 *   ② 罗弗敦改**东侧 Vågan**（理由是 10/2 车程，不是省钱）
 *   ③ 冰河湖那晚改住 **Höfn 的 Árnanes**（Fosshotel 只剩 1 间房）
 *   ④ Booking 的房价行是**每间每晚**，不是两间总价；冰岛酒店价要再加 11% VAT + 城市税
 *   ⑤ 挪威改成**一台车连开 6 天**（EVE 提 → 特罗姆瑟机场还），不再拆两段、不再异地还到 Svolvær
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
  arnanes:    [64.2472, -15.3175], stokksnes: [64.2470, -14.9930],
  reykjanes:  [64.0043, -22.5644],
  ytritunga:  [64.8020, -23.0900], arnarstapi:[64.7680, -23.6200],
  djupalon:   [64.7530, -23.9000], kirkjufell:[64.9270, -23.3100],
  budakirkja: [64.8210, -23.3860],
  eve:        [68.4913,  16.6781], svolvaer:  [68.2340, 14.5680],
  vagan:      [68.2180,  14.4680], henningsvaer:[68.1540,14.2050],
  leknes:     [68.1470,  13.6120], ballstad:  [68.0730, 13.5350],
  ramberg:    [68.0870,  13.2340], nusfjord:  [68.0330, 13.3550],
  hamnoy:     [67.9500,  13.1350], sakrisoy:  [67.9420, 13.1120],
  reine:      [67.9330,  13.0890], aa:        [67.8810, 12.9770],
  narvik:     [68.4385,  17.4272], nordkjosbotn:[69.2180,19.5480],
  tromso:     [69.6492,  18.9553], tosair:    [69.6819, 18.9189],
  houseboat:  [69.6560,  18.9640],
  brensholmen:[69.5680,  18.0170], botnhamn:  [69.4680, 17.8330],
  tungeneset: [69.4790,  17.4890], bergsbotn: [69.4260, 17.5500],
  ersfjord:   [69.4930,  17.3140], finnsnes:  [69.2290, 17.9800]
};

/* ---------- 住宿详情页链接（点了直接跳） ----------
 * Airbnb 用 rooms/<id> 并带上我们真实的入住日期；
 * 酒店用 Booking 物业页并带 checkin/checkout/2 间房/4 人/EUR。
 * ⚠️ Thon Gardermoen 那条是**搜索链接**（Booking 的 slug 猜不出来，只能采；这家还没采过）。
 */
const U = {
  nannestad:  'https://www.airbnb.com/rooms/1616864516592253636?check_in=2026-09-24&check_out=2026-09-25&adults=4&currency=EUR',
  nannestad2: 'https://www.airbnb.com/rooms/1616864516592253636?check_in=2026-09-29&check_out=2026-09-30&adults=4&currency=EUR',
  aurora:     'https://www.airbnb.com/rooms/1729852848905770040?check_in=2026-09-25&check_out=2026-09-26&adults=4&currency=EUR',
  hvols:      'https://www.booking.com/hotel/is/hvolvollur.html?checkin=2026-09-26&checkout=2026-09-27&group_adults=4&no_rooms=2&selected_currency=EUR',
  arnanes:    'https://www.booking.com/hotel/is/arnanes-sveitagisting.html?checkin=2026-09-27&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR',
  vatnajokull:'https://www.booking.com/hotel/is/vatnajokull.html?checkin=2026-09-27&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR',
  keflavik:   'https://www.airbnb.com/rooms/1231709933827491677?check_in=2026-09-28&check_out=2026-09-29&adults=4&currency=EUR',
  vagan:      'https://www.airbnb.com/rooms/1362321193877972891?check_in=2026-09-30&check_out=2026-10-02&adults=4&currency=EUR',
  ramberg:    'https://www.airbnb.com/rooms/1170849828585814519?check_in=2026-09-30&check_out=2026-10-02&adults=4&currency=EUR',
  houseboat:  'https://www.airbnb.com/rooms/1607078897559083655?check_in=2026-10-02&check_out=2026-10-06&adults=4&currency=EUR',
  thon:       'https://www.booking.com/searchresults.html?ss=Thon+Hotel+Gardermoen&checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  scandicosl: 'https://www.booking.com/searchresults.html?ss=Scandic+Oslo+Airport&checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  dcars:      'https://www.discovercars.com/'
};

/* ---------- 两台车的取/还点（画在地图上） ---------- */
const CARPTS = [
  {k:'pick', c:P.kef,    label:'冰岛提车',  when:'9/25 17:00', car:'Peugeot 2008 · 4x4 · 自动',
   note:'落地就取（不是第二天）：只贵 $4，但省掉 4 人 ×2 程机场大巴 ≈ ¥1,360'},
  {k:'drop', c:P.kef,    label:'冰岛还车',  when:'9/29 18:00', car:'Peugeot 2008 · 4x4 · 自动',
   note:'⚠️ 还车时间取决于 Kevin 的 KEF→OSL 起飞时间（见 B1）'},
  {k:'pick', c:P.eve,    label:'挪威提车',  when:'9/30 11:00', car:'Suzuki Vitara · 4WD · 自动',
   note:'⚠️ 押金 $1,805（冻结，不是扣款）→ 要一张额度够的信用卡'},
  {k:'drop', c:P.tosair, label:'挪威还车',  when:'10/6 10:00', car:'Suzuki Vitara · 4WD · 自动',
   note:'一台车连开 6 天，不拆两段：拆开省 $107 但要多跑一次柜台 + 多一次押金冻结，不值'}
];

/* ---------- 逐日行程 ----------
 * spend = 当天真实要花的钱（¥，4 人合计）。多晚连住的房价已按晚数摊平。
 * stay.pt = 住处坐标（地图上的 🛏 图钉）· stay.url = 详情页链接（可点）
 */
const DAYS = [
  {
    id:'D0', date:'9/24', wd:'周四', region:'oslo', base:'Oslo Gardermoen',
    title:'落地奥斯陆，只求近机场',
    anchor:P.nannestad,
    route:[{n:'OSL 机场',c:P.osl},{n:'Nannestad 住处',c:P.nannestad}],
    legs:[], drive:'—',
    stay:{name:'Modern. Quiet area. Large space.',type:'Airbnb',rb:'3房/5床/2卫',
          price:'€260 总价 · ¥1,040/房',cxl:'⛔ 不可退',
          url:U.nannestad, pt:P.nannestad, place:'Nannestad（OSL 西 15 min）',
          note:'唯一能只订 1 晚的 3房2卫，性价比碾压。但**不可退** → 放最后订（等 Kevin 机票定）。'+
               '要弹性就换 <a href="'+U.thon+'" target="_blank">Thon Hotel Gardermoen</a> €86–140/间、退到 9/23'},
    spend:{stay:2080}, supply:'green',
    hi:['中转睡一晚，不安排活动','9/25 一早飞 KEF'],
    watch:['⛔ 这一晚是全程唯一不可退的（9/24+9/29 两晚共 €520 敞口）']
  },
  {
    id:'D1', date:'9/25', wd:'周五', region:'iceland', base:'Reykjavík',
    title:'飞冰岛 · 落地 KEF 提车 · 雷市市区',
    anchor:P.rvk,
    route:[{n:'OSL',c:P.osl},{n:'KEF 提车 17:00',c:P.kef},{n:'Reykjavík 住处',c:P.rvk}],
    legs:[{k:'fly',from:P.osl,to:P.kef},{k:'drive',pts:[P.kef,P.rvk]}],
    drive:'KEF→雷市 50 min',
    stay:{name:'Aurora view 3BR 2BATH Luxury down town',type:'Airbnb',rb:'3房/3床/2卫',
          price:'€647 → €447 · ¥1,788/房',cxl:'✅ 24h 内免费，9/18 前部分退',rating:'5.0',
          url:U.aurora, pt:P.rvk, place:'雷市市中心',
          note:'€647 打到 €447，是这次抓到最大的折扣之一。雷市这一晚候选最多（5 个合格房源），压力最小'},
    car:{name:'Peugeot 2008 · 4x4 · 自动挡',seg:'冰岛 · KEF 9/25 17:00 → KEF 9/29 18:00（5 天）',
         price:'$258 裸车 → 含全险约 $400–480',cny:'¥1,832 → 最坏 ¥3,408（¥682/天）',
         url:U.dcars, pick:P.kef, drop:P.kef, pickWhen:'9/25 17:00', dropWhen:'9/29 18:00',
         note:'冰岛必买三险：SCDW（超级碰撞险）+ gravel（砂石）+ sand&ash（火山沙尘）+ 2026 道路税。'+
              '⛔ 别订 Suzuki Jimny（$247/$251）：装不下 4 人 + 4 个大箱子。不限里程、可免费取消'},
    spend:{stay:3576, car:3408}, supply:'green',
    hi:['Hallgrímskirkja / 老港 / Sun Voyager','落地就提车 = 省掉 4 人来回机场大巴 ¥1,360'],
    watch:['🟠 保险包实价要在 DiscoverCars 结账页读一次（$258 → $400–480 的区间还没收窄）']
  },
  {
    id:'D2', date:'9/26', wd:'周六', region:'iceland', base:'Hvolsvöllur',
    title:'南岸瀑布线（塞里雅兰 + 斯科加）',
    anchor:P.hvolsvollur,
    route:[{n:'Reykjavík',c:P.rvk},{n:'Seljalandsfoss',c:P.seljaland},
           {n:'Skógafoss',c:P.skogafoss},{n:'Hotel Hvolsvöllur',c:P.hvolsvollur}],
    legs:[{k:'drive',pts:[P.rvk,P.seljaland,P.skogafoss,P.hvolsvollur]}],
    drive:'约 200 km / 2h45',
    stay:{name:'Hotel Hvolsvöllur ×2 间 Double/Twin',type:'酒店（Booking）',rb:'2 房 / 2 卫',
          price:'€326 + 11% VAT/城市税 = €374 · ¥1,496/房',cxl:'✅ 到 9/24，且到店付',
          url:U.hvols, pt:P.hvolsvollur, place:'Hvolsvöllur 镇上',
          note:'🔴 **这一晚只能是酒店** —— 南岸乡下 4 个 Airbnb 候选全部「日期不可用」或 min-stay ≥2 晚，'+
               '冰岛南岸基本不接 1 晚。页面写 **"We have 2 left"**，正好是我们要的数量 → 随时变 0。'+
               '含早 + hot tub + 独立卫浴，**不用预付**'},
    spend:{stay:2992}, supply:'red',
    hi:['塞里雅兰瀑布（能绕到瀑布后面）','斯科加瀑布','9 月底不需要冬胎（11/1 才强制）'],
    watch:['🔴 "We have 2 left" —— 排下单顺序第 3 位，且零风险（到店付、退到 9/24）',
           '代价：Hvolsvöllur 在 Vík 西 1h15 → 9/27 往东是 ~4h30 的开车日']
  },
  {
    id:'D3', date:'9/27', wd:'周日', region:'iceland', base:'Höfn（冰河湖以东）',
    title:'冰河湖 + 钻石沙滩 · 夜里去 Stokksnes 等极光',
    anchor:P.hofn,
    route:[{n:'Hvolsvöllur',c:P.hvolsvollur},{n:'Vík',c:P.vik},{n:'Skaftafell',c:P.skaftafell},
           {n:'Jökulsárlón 冰河湖',c:P.jokulsarlon},{n:'Diamond Beach',c:P.diamond},
           {n:'Árnanes 住处',c:P.arnanes},{n:'Stokksnes / Vestrahorn',c:P.stokksnes}],
    legs:[{k:'drive',pts:[P.hvolsvollur,P.vik,P.skaftafell,P.jokulsarlon,P.arnanes,P.stokksnes,P.arnanes]}],
    drive:'约 390 km / 4h30（当天最长）',
    stay:{name:'Árnanes Sveitagisting ×2 间 Double/Twin（私卫）',type:'酒店（Booking）',rb:'2 房 / 2 卫',
          price:'€553 + 税 = €626 · ¥2,504/房',cxl:'✅ 到 9/20，9/18 前一分钱不付',
          url:U.arnanes, pt:P.arnanes, place:'Höfn 西 · 离冰河湖 ~45 min',
          note:'🥇 **交给我的决定 2 的答案**：Fosshotel Glacier Lagoon 的 Standard **只剩 1 间**，'+
               '凑 2 间要 €1,194 含税 = ¥4,776/房**超预算** → 被算术排除。Árnanes **还有 4 间**、'+
               '含早、私卫、页面明写 **"Interconnected rooms available"（可要相连两间）**。'+
               '备选 <a href="'+U.vatnajokull+'" target="_blank">Fosshotel Vatnajökull</a> €345/间（剩 2 间，退到 9/25）= ¥3,104/房'},
    spend:{stay:5008}, supply:'red',
    hi:['Jökulsárlón 冰河湖 + Diamond Beach','🥇 Stokksnes / Vestrahorn 离 Höfn 只 15 min —— 黑沙滩 + 尖角山，极光前景比冰河湖好',
        '住 Höfn 换来「冰河湖看两次两种光」（9/27 往东 + 9/28 往西）',
        'Höfn 是真镇子，有挪威海螯虾（langoustine）餐厅'],
    watch:['🔴 天然蓝冰洞一般 11 月才开 → 9 月能做的是 Katla 冰洞（Vík 出发，全年开）或冰川徒步，Kevin 在找票',
           '订房时在备注里写「interconnected rooms」']
  },
  {
    id:'D4', date:'9/28', wd:'周一', region:'iceland', base:'Reykjanesbær（KEF 旁）',
    title:'西返 · 黄金圈 + 蓝湖',
    anchor:P.reykjanes,
    route:[{n:'Höfn',c:P.arnanes},{n:'冰河湖（再看一次）',c:P.jokulsarlon},
           {n:'Þingvellir',c:P.thingvellir},{n:'Geysir',c:P.geysir},{n:'Gullfoss',c:P.gullfoss},
           {n:'Blue Lagoon',c:P.bluelagoon},{n:'Reykjanesbær 住处',c:P.reykjanes}],
    legs:[{k:'drive',pts:[P.arnanes,P.jokulsarlon,P.vik,P.thingvellir,P.geysir,P.gullfoss,P.bluelagoon,P.reykjanes]}],
    drive:'约 520 km / 6h30（全程最长的一天）',
    stay:{name:'3BR/2BA Reykjanesbær',type:'Airbnb',rb:'3房/4床/2卫',
          price:'€424 总价 · ¥1,696/房',cxl:'✅ 24h 内免费',rating:'4.92',
          url:U.keflavik, pt:P.reykjanes, place:'Reykjanesbær（KEF 旁）',
          note:'原想改住 Borgarnes 省次日 1.5h 车程 → 实测那一带 8 个合格房源**全部 min-stay ≥2 晚**，'+
               '1 晚订不到 → 只能住 KEF 旁，斯奈山靠早出发解决（见 B1）'},
    spend:{stay:3392}, supply:'green',
    hi:['Þingvellir 裂谷 · Geysir 间歇泉 · Gullfoss 黄金瀑布','Blue Lagoon 泡汤（离 KEF 20 min）'],
    watch:['这一天车程最长，注意 9 月末南岸风暴封路（存 road.is）']
  },
  {
    id:'D5', date:'9/29', wd:'周二', region:'iceland', base:'Oslo Gardermoen',
    title:'🔴 斯奈山半岛 + 还车 + 飞奥斯陆（最紧的一天）',
    anchor:P.kirkjufell,
    route:[{n:'Reykjanesbær 05:30 出发',c:P.reykjanes},{n:'Ytri-Tunga 海豹滩',c:P.ytritunga},
           {n:'Arnarstapi',c:P.arnarstapi},{n:'Djúpalónssandur',c:P.djupalon},
           {n:'Kirkjufell 草帽山',c:P.kirkjufell},{n:'Búðakirkja 黑教堂',c:P.budakirkja},
           {n:'KEF 还车 18:15',c:P.kef},{n:'OSL',c:P.osl}],
    legs:[{k:'drive',pts:[P.reykjanes,P.ytritunga,P.arnarstapi,P.djupalon,P.kirkjufell,P.budakirkja,P.kef]},
          {k:'fly',from:P.kef,to:P.osl}],
    drive:'约 7.5h 纯开车 + 3–4h 游玩 = 11–12 小时的一天',
    stay:{name:'Modern. Quiet area. Large space.（同 9/24）',type:'Airbnb',rb:'3房/5床/2卫',
          price:'€260 总价 · ¥1,040/房',cxl:'⛔ 不可退',
          url:U.nannestad2, pt:P.nannestad, place:'Nannestad（同 9/24，可分开订同一家）',
          note:'酒店兜底 <a href="'+U.scandicosl+'" target="_blank">Scandic Oslo Airport</a> €141–188/间（34 个房型行有货，很宽松）'},
    spend:{stay:2080}, supply:'green',
    hi:['Keflavík → Ytri-Tunga 单程 2h45','半岛环线净开车 ~3h + 停留 3h','回 KEF 2h'],
    watch:['🔴 唯一硬前提 = Kevin 的 KEF→OSL 起飞时间。18:35 → 这个环线做不了（要 16:00 前回 KEF）；20:05 → 可以，18:15 还车',
           '9/29 冰岛日落 ~19:00，半岛最后一段在暮色里开（54/574 铺装公路，不难但要算进去）']
  },
  {
    id:'D6', date:'9/30', wd:'周三', region:'lofoten', base:'罗弗敦东侧 · Vågan',
    title:'飞 EVE · 提车 · 进罗弗敦东侧',
    anchor:P.vagan,
    route:[{n:'OSL',c:P.osl},{n:'EVE 提车 11:00',c:P.eve},{n:'Svolvær',c:P.svolvaer},
           {n:'Henningsvær',c:P.henningsvaer},{n:'Vågan 住处',c:P.vagan}],
    legs:[{k:'fly',from:P.osl,to:P.eve},
          {k:'drive',pts:[P.eve,P.narvik,P.svolvaer,P.henningsvaer,P.vagan]}],
    drive:'EVE→Svolvær 165 km / 2h30（E10 全程无渡轮、基本无收费站）',
    stay:{name:'Waterfront Nordic house with fjord views',type:'Airbnb',rb:'5房/8床/2卫',
          price:'€602 → €553 / 2 晚 · ¥1,106/房/晚',cxl:'✅ 24h 内免费，9/23 前部分退',rating:'4.93',
          url:U.vagan, pt:P.vagan, place:'Vågan（Svolvær 旁）· 住 2 晚不搬箱子',
          note:'🥇 **交给我的决定 1 的答案：选东侧。** Guest favorite + Superhost + 页面明写 "Prices include all fees"。'+
               '西侧对照 <a href="'+U.ramberg+'" target="_blank">The heart of Ramberg</a> €647 且**完全不可退** —— '+
               '东侧便宜 €94 还能退'},
    car:{name:'Suzuki Vitara · 4WD · 自动挡',seg:'挪威 · EVE 9/30 11:00 → 特罗姆瑟机场 10/6 10:00（6 天）',
         price:'$762 / 6 天',cny:'¥5,410（¥902/天）',
         url:U.dcars, pick:P.eve, drop:P.tosair, pickWhen:'9/30 11:00', dropWhen:'10/6 10:00',
         note:'一台车连开 6 天，不拆两段。⚠️ **押金 $1,805**（冻结）。'+
              '🔴 更便宜的三台（$569 Urban Cruiser / $581 Peugeot 2008 / $694 ID.4）**全是纯电** —— '+
              '10/5 Senja 往返 ~500 km、10 月低温 + 岛上充电桩稀 → 排除。Corolla $730 是两驱'},
    spend:{stay:2212, car:5410}, supply:'amber',
    hi:['Svolvær 是罗弗敦唯一像样的镇子：超市 / 餐厅 / 加油站 / 药店都在这儿（我们 4 人自炊，每天要用）',
        'Henningsvær（礁石上的渔村 + 著名足球场）离 Svolvær 只 30 min',
        '10 月初 EVE 19:00 前后天就黑 → 开 2h30 是从容的到达，开 4h 到西侧是更糟的第一晚'],
    watch:['挪威交规：全天开近光灯 · 乡道默认 80 · 超 10 km/h 罚款 >NOK 2,500 · 酒驾近乎零容忍 · 单车道 møteplass 上坡优先 · 注意驯鹿和羊',
           '🟠 押金 $1,805 要一张额度够的信用卡（见 B4）']
  },
  {
    id:'D7', date:'10/1', wd:'周四', region:'lofoten', base:'罗弗敦东侧 · Vågan',
    title:'西行一日游 —— 明信片那一侧（当天往返）',
    anchor:P.reine,
    route:[{n:'Vågan 出发',c:P.vagan},{n:'Leknes',c:P.leknes},{n:'Hamnøy',c:P.hamnoy},
           {n:'Sakrisøy',c:P.sakrisoy},{n:'Reine（Reinebringen）',c:P.reine},{n:'回 Vågan',c:P.vagan}],
    legs:[{k:'drive',pts:[P.vagan,P.leknes,P.ramberg,P.hamnoy,P.sakrisoy,P.reine,P.hamnoy,P.leknes,P.vagan]}],
    drive:'单程 2h · 往返约 4h 净开车',
    stay:{name:'同 D6（Waterfront Nordic house，连住第 2 晚）',type:'Airbnb',rb:'5房/8床/2卫',
          price:'含在 €553 / 2 晚内 · ¥1,106/房/晚',cxl:'✅ 24h 内免费',rating:'4.93',
          url:U.vagan, pt:P.vagan, place:'Vågan',
          note:'**选东侧不等于放弃西侧风景** —— 这一天专门西行：Hamnøy 那排最出名的红屋、Sakrisøy、Reine，沿路停，晚饭前回来'},
    spend:{stay:2212}, supply:'amber',
    hi:['Hamnøy 红屋（Eliassen Rorbuer 那排）','Sakrisøy 黄房子','Reinebringen 阶梯往返约 1.5–2h','极光季已开季'],
    watch:['🟠 E10 风暴封路在 9 月末–10 月很常见 → 这也是「东侧 + 可退」比「西侧 + 不可退」好的原因']
  },
  {
    id:'D8', date:'10/2', wd:'周五', region:'tromso', base:'特罗姆瑟（船屋）',
    title:'Svolvær → 特罗姆瑟 自驾 6h30（原游轮那天）',
    anchor:P.tromso,
    route:[{n:'Vågan 出发',c:P.vagan},{n:'Narvik',c:P.narvik},{n:'Nordkjosbotn',c:P.nordkjosbotn},
           {n:'特罗姆瑟船屋 check-in',c:P.houseboat}],
    legs:[{k:'drive',pts:[P.vagan,P.svolvaer,P.eve,P.narvik,P.nordkjosbotn,P.tromso,P.houseboat]}],
    drive:'约 480 km / 6h30 · 傍晚到，自助 check-in',
    stay:{name:'Houseboat "Grosso" in Tromsø（住船上）',type:'Airbnb',rb:'3房/7床/3卫',
          price:'€1,818 → €1,033 / 4 晚 · ¥1,033/房/晚',cxl:'✅ 24h 内免费',rating:'5.0',
          url:U.houseboat, pt:P.houseboat, place:'特罗姆瑟港区 · 住 4 晚（10/2–10/6）',
          note:'🥇 **游轮 pass 掉空出来的 10/2 直接并进船屋**：4 晚 €1,033 vs 3 晚 €825 → '+
               '多住这一晚只多付 €208（¥832/房），比单独找一晚便宜得多，还少搬一次行李。'+
               '3 房 3 卫 = **卫生间比人多**，而且是全程单价最低的一段'},
    spend:{stay:2066}, supply:'amber',
    hi:['🔴 游轮已整段 pass —— 10/2 改自驾，行程不再有单点故障','东侧出发 6h30；若住西侧要 8h30，第一晚极光基本报废'],
    watch:['长途开车日：Narvik 一带 10 月初可能已有初雪，留出富余时间']
  },
  {
    id:'D9', date:'10/3', wd:'周六', region:'tromso', base:'特罗姆瑟',
    title:'特罗姆瑟市区 · 缆车 + 极光',
    anchor:P.tromso,
    route:[{n:'船屋',c:P.houseboat},{n:'北极大教堂 / Fjellheisen',c:P.tromso}],
    legs:[], drive:'市区 + 郊外追极光',
    stay:{name:'同 D8（Houseboat "Grosso"，4 晚连住）',type:'Airbnb',rb:'3房/7床/3卫',
          price:'含在 €1,033 / 4 晚内 · ¥1,033/房/晚',cxl:'✅ 24h 内免费',rating:'5.0',
          url:U.houseboat, pt:P.houseboat, place:'特罗姆瑟港区'},
    spend:{stay:2066}, supply:'green',
    hi:['北极大教堂 · Fjellheisen 缆车 · Polaria','自己有车 = 不被 tour 时间表绑住，可以往内陆躲云'],
    watch:[]
  },
  {
    id:'D10', date:'10/4', wd:'周日', region:'tromso', base:'特罗姆瑟',
    title:'自由日 · 峡湾 / 自己追极光',
    anchor:P.tromso,
    route:[{n:'船屋',c:P.houseboat},{n:'Ersfjordbotn 方向',c:[69.6600,18.5200]}],
    legs:[{k:'drive',pts:[P.houseboat,P.tromso,[69.6600,18.5200],P.tromso]}],
    drive:'弹性（车已经在手上，不用再取）',
    stay:{name:'同 D8（Houseboat "Grosso"）',type:'Airbnb',rb:'3房/7床/3卫',
          price:'含在 €1,033 / 4 晚内',cxl:'✅ 24h 内免费',rating:'5.0',
          url:U.houseboat, pt:P.houseboat, place:'特罗姆瑟港区'},
    spend:{stay:2066}, supply:'green',
    hi:['挪威租车基本不限里程','把 Senja 放 10/5、这天留弹性，天气不好可以两天互换'],
    watch:[]
  },
  {
    id:'D11', date:'10/5', wd:'周一', region:'tromso', base:'特罗姆瑟',
    title:'Senja 自驾一日（硬仗）',
    anchor:P.tungeneset,
    route:[{n:'船屋 07:00 出发',c:P.houseboat},{n:'Brensholmen 渡轮',c:P.brensholmen},
           {n:'Botnhamn',c:P.botnhamn},{n:'Bergsbotn 观景台',c:P.bergsbotn},
           {n:'Tungeneset',c:P.tungeneset},{n:'Ersfjordstranda',c:P.ersfjord},
           {n:'回程（Finnsnes 陆路可选）',c:P.finnsnes}],
    legs:[{k:'drive',pts:[P.houseboat,P.tromso,P.brensholmen]},
          {k:'ferry',pts:[P.brensholmen,P.botnhamn]},
          {k:'drive',pts:[P.botnhamn,P.bergsbotn,P.tungeneset,P.ersfjord,P.bergsbotn,P.finnsnes,P.tromso,P.houseboat]}],
    drive:'约 500 km 往返 · 路上 5–6h，只剩 4–5h 玩',
    stay:{name:'同 D8（Houseboat "Grosso"，最后一晚）',type:'Airbnb',rb:'3房/7床/3卫',
          price:'含在 €1,033 / 4 晚内',cxl:'✅ 24h 内免费',rating:'5.0',
          url:U.houseboat, pt:P.houseboat, place:'特罗姆瑟港区'},
    spend:{stay:2066, other:306}, supply:'green',
    hi:['✅ Brensholmen–Botnhamn 渡轮 2026 全年运营 · NOK 228/车/单程（往返 456 ≈ ¥306）· 航程 35–45 min',
        '开：08:45 / 10:45 / 12:45(周五停) / 15:00 / 17:00 / 19:00 / 20:45',
        '10/5 是周一，不受「周五停」影响','陆路 Finnsnes / Gisund 大桥 ~2h30–3h，时间自由但慢'],
    watch:['10/5 特罗姆瑟日出 07:25 / 日落 18:15 → 07:00 出发是对的，别再晚',
           '出发前一周再核一次 Torghatten Nord / Entur 班次']
  },
  {
    id:'D12', date:'10/6', wd:'周二', region:'oslo', base:'特罗姆瑟 → 奥斯陆', cond:true,
    title:'⚠️ 还车 10:00 · 飞奥斯陆（第 13 晚是否需要，看 Kevin 机票）',
    anchor:P.tosair,
    route:[{n:'船屋退房',c:P.houseboat},{n:'TOS 机场还车 10:00',c:P.tosair},
           {n:'OSL',c:P.osl},{n:'（若 10/7 才飞北京）Nannestad / Thon Gardermoen',c:P.nannestad}],
    legs:[{k:'drive',pts:[P.houseboat,P.tromso,P.tosair]},{k:'fly',from:P.tosair,to:P.osl}],
    drive:'船屋 → TOS 机场 15 min',
    stay:{name:'🅿️ 占位：Thon Hotel Gardermoen ×2 间（只在需要时才订）',type:'占位 · 酒店',rb:'2 房 / 2 卫',
          price:'€172–280（≈¥1,376–2,240）· **未计入总账**',cxl:'✅ 退到 9/23',
          url:U.thon, pt:P.nannestad, place:'OSL 机场旁（占位，等 Kevin 机票日期）',
          note:'🔴 **这一晚是条件性的**：若 Kevin 的 Oslo→北京 是 **10/6** 起飞就不需要；若是 **10/7** '+
               '就要多住第 13 晚。按你说的「不确定就先填个酒店」，这里先占 Thon Gardermoen（可退）。'+
               '也可以订同一家 <a href="'+U.nannestad+'" target="_blank">Nannestad Airbnb</a>（+€260，但不可退）'},
    spend:{}, supply:'amber',
    hi:['TOS→OSL 常见班次很多，还车 10:00 后从容','若当天直飞北京，行程在这里结束'],
    watch:['🔴 等 Kevin 确认 Oslo→北京 是 10/6 还是 10/7（见 B2）—— 这是唯一还会改结构的一条']
  }
];

/* ---------- 逐晚汇总表（表格用；链接可点） ---------- */
const STAYTAB = [
  {d:'9/24',       place:'Oslo Gardermoen', name:'Modern. Quiet area. Large space.', url:U.nannestad, type:'Airbnb', rb:'3房/5床/2卫', tot:'€260',  room:'1,040', cxl:'⛔ 不可退'},
  {d:'9/25',       place:'雷克雅未克',       name:'Aurora view 3BR 2BATH ★5.0',       url:U.aurora,    type:'Airbnb', rb:'3房/3床/2卫', tot:'€647→€447', room:'1,788', cxl:'✅ 24h / 9/18'},
  {d:'9/26',       place:'Hvolsvöllur',     name:'Hotel Hvolsvöllur ×2 间',          url:U.hvols,     type:'酒店',   rb:'2 房 2 卫',   tot:'€374 含税', room:'1,496', cxl:'✅ 9/24 · 到店付'},
  {d:'9/27',       place:'Höfn（冰河湖）',   name:'Árnanes Sveitagisting ×2 间',       url:U.arnanes,   type:'酒店',   rb:'2 房 2 卫',   tot:'€626 含税', room:'2,504', cxl:'✅ 9/20 · 9/18 前不付'},
  {d:'9/28',       place:'Reykjanesbær',    name:'3BR/2BA ★4.92',                    url:U.keflavik,  type:'Airbnb', rb:'3房/4床/2卫', tot:'€424',  room:'1,696', cxl:'✅ 24h'},
  {d:'9/29',       place:'Oslo Gardermoen', name:'同 9/24 · Nannestad',              url:U.nannestad2,type:'Airbnb', rb:'3房/5床/2卫', tot:'€260',  room:'1,040', cxl:'⛔ 不可退'},
  {d:'9/30–10/1',  place:'罗弗敦东侧 Vågan', name:'Waterfront Nordic house ★4.93',    url:U.vagan,     type:'Airbnb', rb:'5房/8床/2卫', tot:'€602→€553/2晚', room:'1,106', cxl:'✅ 24h / 9/23'},
  {d:'10/2–10/5',  place:'特罗姆瑟',         name:'Houseboat "Grosso" ★5.0',          url:U.houseboat, type:'Airbnb', rb:'3房/7床/3卫', tot:'€1,818→€1,033/4晚', room:'1,033', cxl:'✅ 24h'},
  {d:'10/6',       place:'（条件性）奥斯陆',  name:'🅿️ 占位 Thon Hotel Gardermoen ×2', url:U.thon,      type:'占位',   rb:'2 房 2 卫',   tot:'€172–280', room:'688–1,120', cxl:'✅ 9/23'}
];

/* ---------- 我替你做的两个决定 ---------- */
const DECISIONS = [
  {id:'决定 1', q:'罗弗敦住东侧还是西侧？', a:'东侧（Svolvær / Vågan）',
   why:'主要理由**不是省钱，是 10/2 那天的车程**：东侧 6h30，西侧 8h30 —— 从西侧走 10/2 整天就没了，'+
        '到特罗姆瑟已 17:00 以后，第一晚极光报废。',
   rows:[['9/30 EVE→住处','东 2h30 · 西 4h（黑天开一台刚提的陌生车）'],
         ['10/1','东：自由日 + 可选西行 4h 往返；西：车程最少'],
         ['10/2 →特罗姆瑟','东 6h30 · 西 8h30'],
         ['总车程','东 ~13h · 西 ~14h30（差不多，但分布是决定性的）']],
   plus:['Svolvær 是罗弗敦唯一像样的镇子（超市/餐厅/加油站/药店）—— 我们 4 人自炊，每天要用',
         'Henningsvær 离 Svolvær 只 30 min，最出名的两个取景点东侧就占一个',
         '钱和风险上也赢：东 €553 可退 vs 西 €647 完全不可退；E10 风暴封路常见，「最西头 + 不可退」是最差组合'],
   keep:'西侧风景一点没丢 —— 10/1 专门西行一天：Vågan → Hamnøy → Sakrisøy → Reine（单程 2h），沿路停，晚饭前回来。'},
  {id:'决定 2', q:'冰河湖那晚住哪？', a:'Höfn 的 Árnanes Sveitagisting（不是冰河湖旁的 Fosshotel）',
   why:'这不是口味问题，是**算出来的**：Fosshotel Glacier Lagoon 的 Standard **只剩 1 间**，'+
        '我们要 2 间只能配成 €1,067 不含税 → 加 11% VAT + 城市税 ≈ €1,194 = **¥4,776/房，超你 ¥4,000 上限**。',
   rows:[['🥇 Árnanes（Höfn 西）','还有 4 间 · €626 含税 · **¥2,504/房** · 退到 9/20 · 离冰河湖 45 min'],
         ['备选 Fosshotel Vatnajökull','剩 2 间 · €776 · ¥3,104/房 · 退到 9/25 · 55 min'],
         ['⛔ Fosshotel Glacier Lagoon','只剩 1 间 · €1,194 · ¥4,776/房 超预算 · 10 min'],
         ['⛔ Klaustur / Laki / Magma','多数只剩 1 间 · ¥2,852–5,056 · 更远']],
   plus:['冰河湖会看两次、两种光（9/27 往东 + 9/28 往西返）——住冰河湖旁反而是「看一次然后掉头」',
         '🥇 Stokksnes / Vestrahorn 离 Höfn 只 15 min，黑沙滩 + 尖角山当极光前景比冰河湖好',
         'Höfn 是真镇子（有 langoustine 餐厅），比荒野里一家孤零零的酒店过夜舒服',
         'Árnanes 页面明写 "Interconnected rooms available" —— 对「两男 + 一对夫妻」正好'],
   keep:'代价是单程多开约 50 min。想住正规连锁就换 Fosshotel Vatnajökull ¥3,104/房，也在预算内、退改期还更晚。'}
];

/* ---------- 下单顺序（按会先没排，不按贵排） ---------- */
const URGENCY = [
  {rank:1, sev:'red',   what:'罗弗敦东侧 Vågan 5房2卫 €553 / 2 晚',
   why:'Guest favorite ★4.93 且只有 14 条评价的抢手房；9/23 是部分退款的悬崖',
   deadline:'越早越好（9/23 悬崖）', how:'Airbnb —— 24h 内可全额免费退 → 零风险'},
  {rank:2, sev:'red',   what:'Árnanes 9/27 两间 €553（+税 €626）',
   why:'冰河湖方圆 60 km 内唯一「在预算内 + 真有 2 间 + 能退」的',
   deadline:'free-cxl 到 9/20', how:'Booking —— 9/18 前一分钱不用付 → 零风险'},
  {rank:3, sev:'red',   what:'Hotel Hvolsvöllur 9/26 两间 €326（+税 €374）',
   why:'页面写 "We have 2 left" —— 正好是我们要的数量，随时变 0',
   deadline:'free-cxl 到 9/24', how:'Booking —— 到店付 → 零风险'},
  {rank:4, sev:'amber', what:'特罗姆瑟船屋 10/2–10/6 €1,033 / 4 晚',
   why:'极光季开季；3房3卫的船屋是独一份',
   deadline:'尽快', how:'Airbnb —— 24h 内免费退'},
  {rank:5, sev:'amber', what:'雷市 9/25 €447',
   why:'€647→€447 的折扣会过期；9/18 是部分退款悬崖',
   deadline:'9/18 前', how:'Airbnb —— 24h 内免费退'},
  {rank:6, sev:'amber', what:'两台车（冰岛 Peugeot 2008 $258 · 挪威 Suzuki Vitara $762）',
   why:'都可免费取消，而且只会越来越贵 → 先锁价',
   deadline:'现在', how:'DiscoverCars，零风险'},
  {rank:7, sev:'green', what:'Reykjanesbær 9/28 €424',
   why:'供给充足（3 个合格房源都有货）',
   deadline:'随时', how:'Airbnb —— 24h 内免费退'},
  {rank:8, sev:'green', what:'Nannestad 9/24 + 9/29 €260 ×2',
   why:'⛔ 不可退（€520 敞口）→ 等 Kevin 机票定了再订',
   deadline:'Kevin 机票确认后', how:'要弹性就换 Thon Hotel Gardermoen €86–140/间（退到 9/23）'}
];

/* ---------- 未决问题 ---------- */
const OPEN = [
  {sev:'red',   q:'Kevin 的 9/29 KEF→OSL 起飞时间？', why:'唯一决定 9/29 能不能跑斯奈山半岛的硬前提。18:35 → 做不了；20:05 → 可以', who:'Kevin'},
  {sev:'red',   q:'Kevin 的 Oslo→北京 是 10/6 还是 10/7 起飞？', why:'10/7 → 10/6 在奥斯陆还要多一晚（第 13 晚，本方案没计入总账，地图上已按占位画出）', who:'Kevin'},
  {sev:'amber', q:'冰岛 SCDW + 砂石险 + 火山沙尘险 + 道路税的打包实价？', why:'$258 裸车 → 约 $400–480，是总账里唯一还会往上顶的一项', who:'DiscoverCars 结账页 / 供应商'},
  {sev:'amber', q:'挪威 Vitara 的 $1,805 押金', why:'会冻结额度（不是扣款）→ 要确认有一张额度够的信用卡', who:'Steve'},
  {sev:'amber', q:'D3（9/27）蓝冰洞 → Katla 冰洞的决定', why:'天然蓝冰洞一般 11 月才开。换 Katla 后集合点在 Vík —— 住宿不受影响（Höfn 方案不动）', who:'Kevin 找票'},
  {sev:'green', q:'Árnanes 能不能给到相连的两间（interconnected）？', why:'页面写「available」，但要在订单备注里主动要', who:'下单时备注'},
  {sev:'green', q:'挪威租车是否含 AutoPASS 标签，手续费怎么收？', why:'E10 + 特罗姆瑟这段收费站很少，金额很小', who:'租车公司'},
  {sev:'green', q:'Torghatten Nord 官网核 10/5 Brensholmen–Botnhamn 确切班次', why:'低季会改点（已确认 2026 全年运营、周一不受「周五停」影响）', who:'出发前一周'}
];

/* ---------- 风险 ---------- */
const RISKS = [
  {r:'Airbnb 房源到下单时已被订走（搜索页有价 ≠ 能订）', imp:'要重新找，可能只剩更贵的', act:'🔴 已经踩过 4 次（见下方「踩过的坑」）→ 排名前 3 的今天就占住，都可免费退', sev:'red'},
  {r:'D5 斯奈山赶飞机', imp:'误机 / 全天在车上', act:'先确认 Kevin 的 KEF→OSL 起飞时间；20:05 才做，18:35 就砍掉半岛', sev:'red'},
  {r:'Nannestad 两晚不可退（€520 敞口）', imp:'机票一改就是白扔 ¥4,160', act:'放最后订；或换 Thon Gardermoen（退到 9/23）', sev:'amber'},
  {r:'冰岛保险包把车价从 $258 顶到 $480', imp:'总账 +¥1,576', act:'仍远低于 ¥2,000/天上限；线上先买比柜台便宜', sev:'amber'},
  {r:'挪威 $1,805 押金冻结', imp:'卡额度不够就提不到车', act:'出发前确认额度，别用接近满额的卡', sev:'amber'},
  {r:'秋季风暴封路（冰岛南岸 / 罗弗敦 E10 / 10/2 长途）', imp:'单日行程作废', act:'订可免费取消的房；存 road.is 和 vegvesen.no；东侧方案已把最长车程从 8h30 降到 6h30', sev:'amber'},
  {r:'~~10/2 Havila 舱位卖光 = 整段行程单点故障~~', imp:'—', act:'✅ 已消除：游轮整段 pass 掉，10/2 改自驾 + 并进船屋（还便宜了 ¥12,000）', sev:'done'},
  {r:'~~9/27 冰河湖那晚只有 Fosshotel 一个选择~~', imp:'—', act:'✅ 已消除：Fosshotel 只剩 1 间反而被排除，Höfn 的 Árnanes 便宜一半还含早', sev:'done'},
  {r:'~~罗弗敦异地还车费 $320 + 只有 6 个车源~~', imp:'—', act:'✅ 已消除：不再还到 Svolvær，一台车直接开到特罗姆瑟机场', sev:'done'},
  {r:'~~中国驾照无 IDP，租车公司拒租~~', imp:'—', act:'✅ 已消除：用美国驾照，冰岛/挪威都直接认', sev:'done'},
  {r:'~~9 月底冰岛要不要冬胎~~', imp:'—', act:'✅ 已消除：11/1 起才强制', sev:'done'},
  {r:'~~Brensholmen 渡轮季节性停开~~', imp:'—', act:'✅ 已消除：2026 全年运营，10/5 周一不受「周五停」影响', sev:'done'}
];

/* ---------- 黑话表 ---------- */
const GLOSSARY = [
  ['free-cxl','可免费取消的截止日期'],
  ['non-ref','不可退：钱付了就退不回来，改期也不行'],
  ['min-stay','房东设的最少入住晚数，比你要住的天数长就订不了'],
  ['¥/房','总价 ÷ 实际住的房间数（按 Steve 的口径）。本页一律保守按 ÷2 算，3 房那几晚实际还更低'],
  ['VAT','增值税。冰岛酒店报价**不含**，要另加 11% + 每晚 €6 城市税'],
  ['rorbu','罗弗敦传统红色渔屋改的自炊小屋，通常带厨房，是当地主流住宿形态'],
  ['interconnected rooms','相连的两间房（中间有门），酒店里最接近「一套 2 卧 2 卫」的形态'],
  ['Guest favorite','Airbnb 给评分/入住体验最好的一小部分房源的标记'],
  ['CDW','车损免责，含在车价里，但有自付额'],
  ['SCDW','把 CDW 的自付额再降低'],
  ['gravel protection','砂石险：碎石打伤车漆/前挡，冰岛特有，标准 CDW 不赔'],
  ['sand & ash protection','火山沙尘险：沙尘暴磨伤车身，冰岛特有，标准 CDW 不赔'],
  ['押金 / deposit','租车公司在信用卡上**冻结**一笔额度（不是扣款），还车后释放'],
  ['AutoPASS','挪威高速自动收费，车上有电子标签，租车公司事后从卡上扣，另加手续费'],
  ['møteplass','挪威单车道公路的会车位。上坡车优先，别停在会车位里'],
  ['不限里程','Unlimited mileage，挪威冰岛基本都是']
];

/* ---------- 数据来源 ---------- */
const PROV = [
  ['Airbnb 搜索','Playwright，URL 里强制 min_bedrooms≥2 & min_bathrooms≥2 & 整套房源，并用经纬度框锁死地理范围（避免 Airbnb 把「Vík」搜成 2.5h 外的 Selfoss）','notes/_research/abnb_scrape.py'],
  ['⭐ Airbnb 房源页逐个复核','**关键一步**：按我们真实日期打开每个候选的房源页，读「N guests · N bedrooms · N beds · N baths」+ 评分 + 退改政策 + 真实折后价并截图。就是这一步抓出 4 个「搜索页有价、实际订不到」的假货','notes/_research/abnb_detail.py'],
  ['Booking 房型行 + 截图','逐物业房型页抓真实房价行、剩余间数、free-cxl 日期、"Select Rooms" 下拉框（1→€276 / 2→€553 就是这么确认「每间每晚」的）','notes/_research/bk_prop.py · bk_shot.py'],
  ['Booking 的酒店 slug','slug **猜不出来**（猜过两轮，16 个 slug → 0 行）→ 只能从它 SEO 落地页的 HTML 里正则刨出来','notes/_research/slug_find.py'],
  ['DiscoverCars 实时车价','搜索结果页 sq 参数里 Hash 字段为空 = 未签名，路径 UUID 不校验 → 可自拼 payload 拿真实报价。地点 ID：KEF 1787 · EVE 2088 · Svolvær 2092 · TOS 2195','notes/_research/dc_direct.py · dc_cars.py'],
  ['航班','Google Flights 实时（注意它卖不了 Widerøe 支线）','notes/_research/flights_gf.py']
];

const PITFALLS = [
  '🔴 <b>Airbnb 搜索卡片会撒谎</b>：4 个候选在搜索页有价、打开房源页却是 "Those dates are not available"（换干净浏览器复现过，不是反爬）。其中 2 个原本是 🥇 首选 —— 直接照搜索结果下单会以为订到了。<b>必须逐个开房源页复核。</b>',
  '🔴 <b>Booking 的房价行是「每间每晚」，不是「两间总价」</b>。我一开始记错了，导致所有酒店的 ¥/房 少算一半。三条独立证据：<code>no_rooms=1</code> 与 <code>no_rooms=2</code> 抓回的数字完全一样；截图里明写 "1 room / We have 1 left"；Árnanes 的 "Select Rooms" 下拉框写着 1→€276 / 2→€553。',
  '🔴 <b>冰岛酒店报价不含税</b>：页面小字写 "Excluded: 11 % VAT, ISK 800 / €6 City tax per night"。真实支出比标价高 11%+。挪威和 Airbnb 的价是含税含清洁费的（东侧那套还明写 "Prices include all fees"）。',
  '<b>剩余间数要单独看</b>：一家酒店「有房」不等于「有 2 间」。Fosshotel Glacier Lagoon 和 Boutique Hotel Anna 都是 "We have 1 left" —— 凑第 2 间就跳到更贵的房型，直接顶破预算。',
  'Airbnb 不锁经纬度框就会把「Vík」搜成 2.5 小时外的 Selfoss，返回一堆看起来合格实际开不到的房源。',
  'DiscoverCars 首页表单点日历点不动（react-date-range），日期没生效 → 拿到的是默认 9/04–9/12 的价，看起来正常其实全错。<b>每次都要回读页面上的日期。</b>'
];

/* ================================================================
 * 需要人拍板的问题 —— 附出处 file:line
 * ================================================================ */
const BLOCKERS = [
  {id:'B1', kind:'block', sev:'red',
   q:'Kevin 订的 KEF→OSL 9/29 航班是几点起飞？',
   blocks:'9/29 斯奈山半岛到底做不做 + 冰岛还车时间怎么填',
   detail:'从 Reykjanesbær 05:30 出发跑完半岛（Ytri-Tunga 海豹滩 2h45 + 环线净开车 3h + 停留 3h + 回 KEF 2h）= 11–12 小时的一天，18:00–18:30 回 KEF 还车。傍晚常见班次是 ~18:35（Norwegian/SAS）和 ~20:05（Norwegian）。',
   ifUnknown:'<b>18:35 → 这个环线做不了</b>（要 16:00 前回 KEF，等于只能玩 1 小时，只能砍掉半岛留在雷市）；<b>20:05 → 可以做</b>，18:15 还车、19:00 到柜台刚好。',
   who:'Kevin（票是他订的）',
   days:['D4','D5'],
   src:[['notes/PLAN-final.md','232（§七 第 1 条：唯一的硬前提）'],
        ['notes/OPTIONS-stay.md','56–63（时间表推算）']],
   nowdo:'先按 20:05 那套订（车和房都可免费取消），拿到时间再决定砍不砍。住宿完全不受影响。'},

  {id:'B2', kind:'block', sev:'red',
   q:'Kevin 的 Oslo→北京 是 10/6 还是 10/7 起飞？',
   blocks:'要不要第 13 晚（10/6 在奥斯陆）—— 本方案的总账只算了 12 晚',
   detail:'游轮 pass 掉之后，行程需要的是 <b>9/24 到 10/5 共 12 晚</b>。10/6 上午 10:00 在特罗姆瑟机场还车、飞奥斯陆。如果当天就接北京的航班，行程在奥斯陆机场结束；如果是 10/7 才飞，就要在奥斯陆多住一晚。',
   ifUnknown:'第 13 晚 <b>€172–280（Thon Gardermoen 2 间，可退）</b> 或 <b>+€260（Nannestad 那套 Airbnb，不可退）</b>。金额不大，但会决定 Nannestad 那两晚要不要一起订（它不可退，€520 敞口）。<b>地图上 D12 已经按「占位酒店」画出来了，钱没计入总账。</b>',
   who:'Kevin',
   days:['D12'],
   src:[['notes/PLAN-final.md','233（§七 第 2 条）'],
        ['notes/PLAN-final.md','220（§六 第 8 项：Nannestad 等机票确认后再订）']],
   nowdo:'先把 D12 当占位（Thon Gardermoen 可退到 9/23）。Kevin 一回信，要么删掉、要么点一下就订。'},

  {id:'B3', kind:'block', sev:'amber',
   q:'冰岛租车的保险包（SCDW + 砂石 + 火山沙尘 + 2026 道路税）实际多少钱？',
   blocks:'总账里唯一还会往上顶的一项：$258 → 约 $400–480',
   detail:'$258 是<b>裸车价</b>。冰岛这三个附加险不是推销：1 号环岛碎石路段多、10 月南岸沙尘暴是真实索赔项，而信用卡自带的 CDW 基本把这两项写进排除条款，还要先自己垫付再报销。',
   ifUnknown:'按最坏 $480 算，折 <b>¥3,408（¥682/天）</b> —— 仍然远低于你 ¥2,000/天 的上限，所以<b>它不会改变任何决定</b>，只影响总数从 ¥39,364 变成约 ¥40,900。',
   who:'DiscoverCars 结账页读实价，或直接问供应商',
   days:['D1','D2','D3','D4','D5'],
   src:[['notes/PLAN-final.md','28–33（§一 唯一会往上顶的一项）'],
        ['notes/PLAN-final.md','234（§七 第 3 条）']],
   nowdo:'先按可免费取消订下来锁价，结账页那一步再读准数。'},

  {id:'B4', kind:'block', sev:'amber',
   q:'挪威 Suzuki Vitara 的 $1,805 押金，有额度够的信用卡吗？',
   blocks:'9/30 在 EVE 能不能顺利提到车',
   detail:'$1,805 是<b>冻结额度</b>（不是扣款），还车后释放。挪威租车这个数字偏高是因为 4WD + 6 天 + 异地还车。',
   ifUnknown:'卡额度不够 = 现场提不到车，而那天下午要开 2h30 进罗弗敦，没有 plan B。',
   who:'Steve（确认卡额度）',
   days:['D6'],
   src:[['notes/PLAN-final.md','186（§五 表格最后一行 ⚠️）'],
        ['notes/PLAN-final.md','235（§七 第 4 条）']],
   nowdo:'现在看一眼卡的可用额度就行。不够就换卡，或者订价格接近、押金更低的一家。'}
];

/* 只影响某一项的细节 —— 不定也能先订（都可免费取消） */
const DETAILS = [
  {q:'Árnanes 能不能给到相连的两间（interconnected rooms）？', why:'页面写「available」，但要在订单备注里主动要 —— 对「两男 + 一对夫妻」正好',
   who:'下单时备注', src:[['notes/PLAN-final.md','124–126']]},
  {q:'D3（9/27）蓝冰洞换不换成 Katla 冰洞？', why:'天然蓝冰洞一般 11 月才开。<b>换了也不动住宿</b>（Höfn 方案不受影响）—— 这条已经从「卡住行程」降级成「细节」',
   who:'Kevin 找票', src:[['notes/PLAN-final.md','233 附近'],['viz/data.js','D3.watch']]},
  {q:'冰岛第二驾驶员免不免费？', why:'长途开车日多（9/28 是 6h30），能换人开更安全。各家政策差很多',
   who:'租车官网', src:[['notes/OPTIONS-cars.md','182–183']]},
  {q:'挪威租车是否含 AutoPASS 标签，手续费怎么收？', why:'E10 + 特罗姆瑟这段收费站很少，金额很小 —— 知道就行，不影响选择',
   who:'租车公司', src:[['notes/OPTIONS-cars.md','184 + 116']]},
  {q:'特罗姆瑟船屋的自助 check-in 流程 + 停车位', why:'10/2 傍晚开 6h30 才到，最好提前知道钥匙怎么拿、车停哪',
   who:'订完后给房东留言', src:[['notes/PLAN-final.md','60–65']]},
  {q:'Torghatten Nord 官网核 10/5 Brensholmen–Botnhamn 确切班次', why:'低季会改点。已确认 2026 全年运营、10/5 周一不受「周五停」影响',
   who:'出发前一周', src:[['notes/PLAN-final.md','202–206']]},
  {q:'Hotel Hvolsvöllur 的 hot tub 要不要预约', why:'纯舒适度。页面写含早 + hot tub + 独立卫浴',
   who:'到店问', src:[['notes/PLAN-final.md','246（截图 03b）']]}
];

/* 已经拍板 / 已经查实 —— 别再重新讨论一遍 */
const SETTLED = [
  {q:'游轮那段坐不坐？', a:'<b>整段 pass 掉</b>（Steve 定的）。10/2 改成 Svolvær→特罗姆瑟自驾 6h30，那一晚并进特罗姆瑟船屋。<b>顺带消掉了整个行程唯一的单点故障</b>（Havila 的价拿不到、舱位可能卖光），还省下约 ¥12,000。',
   src:[['notes/PLAN-final.md','60–63'],['notes/OPTIONS-cruise.md','整份文档已作废']]},
  {q:'住 Airbnb 还是酒店？', a:'<b>非常 prefer Airbnb</b>（Steve 明确说的）。已执行：12 晚里 <b>10 晚是 Airbnb 整套房</b>，只有 9/26、9/27 两晚因为冰岛乡下确实没有可订的 2房2卫整套房源，才用酒店 2 间房。',
   src:[['notes/PLAN-final.md','39–40'],['notes/OPTIONS-stay.md','98–101（南岸 4 个 Airbnb 全部订不到）']]},
  {q:'罗弗敦东侧还是西侧？', a:'<b>东侧（Svolvær / Vågan）</b> —— 交给我决定的，答案在上面「两个决定」那一节。核心理由是 10/2 车程 6h30 vs 8h30，其次是可退，省钱只是附带。',
   src:[['notes/PLAN-final.md','72–108']]},
  {q:'冰河湖那晚住哪？', a:'<b>Höfn 的 Árnanes</b> —— 也是交给我决定的。Fosshotel Glacier Lagoon 只剩 1 间房，凑 2 间 ¥4,776/房超预算，<b>是被算术排除的</b>。',
   src:[['notes/PLAN-final.md','110–138']]},
  {q:'几个人、怎么分房、¥/房怎么算？', a:'<b>4 人 = 两男 + 一对夫妻。</b>¥/房 = 总价 ÷ <b>实际用的房间数</b>。本页一律<b>保守按 ÷2</b> 算；3 房那几晚如果两个男生各住一间（÷3），数字还要再低三分之一。',
   src:[['notes/PLAN-final.md','10 + 54']]},
  {q:'预算够不够？', a:'<b>住宿 ¥1,326/房/晚，只有你预算下沿（¥2,000）的 2/3。</b>两台车 ¥366/天 和 ¥902/天，都远低于 ¥2,000/天的上限。',
   src:[['notes/PLAN-final.md','20–26']]},
  {q:'免费取消 vs 更便宜的不可退？', a:'<b>全部买可免费取消</b>。9 项里 <b>7 项零风险</b>，唯一例外是 Nannestad 两晚（€520），已给可退替代（Thon Gardermoen）。',
   src:[['notes/PLAN-final.md','222–224']]},
  {q:'挪威租车拆两段还是一台车连开？', a:'<b>一台车连开 6 天</b>（EVE 提 → 特罗姆瑟机场还）。拆开省 $107，但要多跑一次柜台 + 多一次押金冻结，而且 10/2 傍晚才到特罗姆瑟。不值。<b>顺带干掉了原方案里 $320 的异地还车费和「只有 6 个车源」的风险。</b>',
   src:[['notes/PLAN-final.md','190–194']]},
  {q:'驾照国别 / 要不要国际驾照 IDP？', a:'<b>美国驾照，冰岛和挪威都直接认，不需要 IDP。</b>',
   src:[['notes/PLAN-final.md','185']]},
  {q:'9 月底冰岛要不要冬胎？', a:'<b>不需要</b> —— 法律 11/1 起才强制。',
   src:[['notes/OPTIONS-cars.md','189']]}
];

