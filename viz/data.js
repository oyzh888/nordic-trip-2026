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
 *
 * 🆕 2026-09-02 下午（Steve 两句话）：
 *   ⑥ 「9/29 丢一些景点别那么累」→ D5 从斯奈山半岛（7.5h 开车）改成**雷克雅内斯半岛轻档**（~2h），
 *      顺带消掉了「Kevin 的 KEF→OSL 起飞时间」这个原本唯一的硬前提
 *   ⑦ 「10/2 坐飞机别开车，前后可以继续开车」→ D8 改成 **Svolvær 还车 → Widerøe 直飞 SVJ→TOS 50 min
 *      → 特罗姆瑟机场再提车**，⑤ 那条被推翻：挪威又拆回两段（$650 + $343 = $993 vs $762）。
 *      ⚠️ 机票价**未核实** —— Widerøe 有反爬且不给 Google Flights 供货（见 B1）
 *
 * 🆕🆕 2026-09-02 傍晚（「帮我把这个方案作为默认，其他的作为备选」）：
 *   ⑧ **Steve 自己找的 9/25–10/5 那一套已经成为默认**，我原来挑的全部降级为备选（都保留、都标了差价）。
 *      6 个 Airbnb 链接 + 2 个 Booking 链接**逐个开真实页面验过可订**（2026-09-02）。
 *      变化：9/26 Hörgsland（Klaustur 东）· 9/27 Birkifell（Höfn 西，整栋）· 9/28 Njarðvík ·
 *      9/29 Nannestad 5房1.5卫（换来可退）· 9/30–10/1 Vågan 3房 · 10/2– 特罗姆瑟 4房。
 *      ③ 那条（Árnanes）因此被推翻 → 改 Birkifell。
 *   ⑨ 顺带把 9/26 的住处从 Hvolsvöllur 往东挪到 Klaustur 东侧 → **9/27 从 390 km 降到 200 km**。
 *   🔴 两个窟窿：**10/5 那晚没有**（同一套特罗姆瑟房延到 10/6 = €1,526→€1,979）；
 *      **9/24 那晚不在他的清单里**（沿用我原来的 Nannestad €260，或把 5房那套改成 9/24 —— 未验）。
 *
 * 🆕🆕🆕 2026-09-02 深夜（Steve 又给了两个链接）：
 *   ⑩ **9/28 换成 Njarðvík 的「Hot tub & Sauna · Ocean Break」★5.0 €531→€335**（3房/3床/**1卫**）——
 *      比原来那套便宜 €110，床型更好（king + 单人 + 单人），但**卫生间从 2 个变 1 个**。
 *   ⑪ 🔴 **10/5 给了奥斯陆一带的房源 → 行程结构变了**：10/5 不再是 Senja 日，而是
 *      **TOS 还车 → 飞 TOS→OSL → 住 Stange/Mjøsli 的 Konglehytta 3（★4.98，私人桑拿）**。
 *      连带三处改动：**Senja 挪到 10/4（周日 —— 渡轮班次要重核）**、
 *      **特罗姆瑟回到 3 晚（€1,526，日期不用改了，⑨ 那个「10/5 窟窿」自动消失）**、
 *      **车② 从 4 天缩到 3 天（$343 → ~$240）**。
 *      🔴 但小屋在 Stange 森林里、房源页写着 "A car is required" → **要在 OSL 加租 1 天车（$79–86）**。
 *      净结果：住宿 −€267、车 −$17 → **比上一版便宜约 ¥1,400**，还白得一个防延误的缓冲夜；
 *      代价是**特罗姆瑟极光夜从 4 个变 3 个**。
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
  reykjanes:  [64.0043, -22.5644], njardvik:  [63.9930, -22.5340],
  stange:     [60.6350, 11.2600],
  horgsland:  [63.8320, -18.0170], birkifell: [64.2810, -15.3520],
  gunnuhver:  [63.8186, -22.6836], bridge:    [63.8686, -22.6767],
  brimketill: [63.8322, -22.6247], valahnukur:[63.8117, -22.7057],
  reykjanesviti:[63.8151,-22.7053], krysuvik: [63.8940, -22.0550],
  skylagoon:  [64.1183, -21.9350],
  ytritunga:  [64.8020, -23.0900], arnarstapi:[64.7680, -23.6200],
  djupalon:   [64.7530, -23.9000], kirkjufell:[64.9270, -23.3100],
  budakirkja: [64.8210, -23.3860],
  eve:        [68.4913,  16.6781], svolvaer:  [68.2340, 14.5680],
  svjair:     [68.2433,  14.6692], bodo:      [67.2694, 14.3653],
  lknair:     [68.1525,  13.6094], leknesair: [68.1525, 13.6094],
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
 * ✅ 2026-09-02：Thon Gardermoen / Clarion / Scandic Oslo Airport 的 slug 已采到
 *    （no/thon-gardermoen · no/clarion-oslo-airport · no/scandic-oslo-airport），
 *    三条都从搜索链接换成了真正的物业页。
 */
const U = {
  /* 🆕 2026-09-05 舒适优先：OSL 唯一连廊直通航站楼的酒店 */
  rad24:      'https://www.booking.com/hotel/no/radisson-blu-airport-oslo.html?checkin=2026-09-24&checkout=2026-09-25&group_adults=4&no_rooms=2&selected_currency=EUR',
  rad29:      'https://www.booking.com/hotel/no/radisson-blu-airport-oslo.html?checkin=2026-09-29&checkout=2026-09-30&group_adults=4&no_rooms=2&selected_currency=EUR',
  rad1006:    'https://www.booking.com/hotel/no/radisson-blu-airport-oslo.html?checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
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
  clarion:    'https://www.booking.com/hotel/no/clarion-oslo-airport.html?checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  thon:       'https://www.booking.com/hotel/no/thon-gardermoen.html?checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  scandicosl: 'https://www.booking.com/hotel/no/scandic-oslo-airport.html?checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  parkinn:    'https://www.booking.com/hotel/no/park-inn-oslo-airport.html?checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  /* 🆕 2026-09-02 傍晚：Steve 自己找的这套成为默认，上面几条降为备选 */
  horgsland:  'https://www.booking.com/hotel/is/horgsland-cottages.html?checkin=2026-09-26&checkout=2026-09-27&group_adults=4&no_rooms=2&selected_currency=EUR',
  birkifell:  'https://www.booking.com/hotel/is/guesthouse-birkifell.html?checkin=2026-09-27&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR',
  njardvik:   'https://www.airbnb.com/rooms/1468029290775302593?check_in=2026-09-28&check_out=2026-09-29&adults=4&currency=EUR',
  nann5br:    'https://www.airbnb.com/rooms/1461656866395092330?check_in=2026-09-29&check_out=2026-09-30&adults=4&currency=EUR',
  nann5br24:  'https://www.airbnb.com/rooms/1461656866395092330?check_in=2026-09-24&check_out=2026-09-25&adults=4&currency=EUR',
  vagan3br:   'https://www.airbnb.com/rooms/1258848712541940268?check_in=2026-09-30&check_out=2026-10-02&adults=4&currency=EUR',
  lofnew:     'https://www.airbnb.com/rooms/1303545546783105490?check_in=2026-09-30&check_out=2026-10-02&adults=4&currency=EUR',
  tos4br:     'https://www.airbnb.com/rooms/825162133059470411?check_in=2026-10-02&check_out=2026-10-06&adults=4&currency=EUR',
  tos4br3n:   'https://www.airbnb.com/rooms/825162133059470411?check_in=2026-10-02&check_out=2026-10-05&adults=4&currency=EUR',
  njardvik3:  'https://www.airbnb.com/rooms/1139944377459145061?check_in=2026-09-28&check_out=2026-09-29&adults=4&currency=EUR',
  konglehytta:'https://www.airbnb.com/rooms/648419631702172808?check_in=2026-10-05&check_out=2026-10-06&adults=4&currency=EUR',
  stracta:    'https://www.booking.com/hotel/is/stracta-apartments.html?checkin=2026-09-26&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR',
  dcars:      'https://www.discovercars.com/',
  /* 🆕 2026-09-03：四台车各一条「直接落在我们那个日期+取还点的实时比价页」的链接。
     原理：DiscoverCars 的 /search/<uuid>?sq=<base64 json> 里 sq 是**未签名的**
     （payload 的 Hash 是空串），路径上的 uuid 也不校验 → 可以手工拼出深链，
     人点进去就是结果页，不用再填表单。生成 + 逐条验证：notes/_research/dc_links.py
     （验的是三件事：页面上的日期对不对 · 有没有报价 · 最低价对不对得上量级）*/
  dc1: 'https://www.discovercars.com/offer/e42e9998-7500-4027-90fa-bb087f945740-PMDB?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoxNzg3LCJEcm9wT2ZmTG9jYXRpb25JZCI6MTc4NywiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTA5LTI1VDA4OjAwOjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0wOS0yOVQxODowMDowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIyOGNlNjY3ZjI2ZWVkNTU4YTQzMTgwMjk2OGJhMDI0NSJ9',
  dc2: 'https://www.discovercars.com/search/fb22a8ce-3cbe-4fe3-9460-0f5c3b24eec4?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoyMDg4LCJEcm9wT2ZmTG9jYXRpb25JZCI6MjA5MSwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTA5LTMwIDExOjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wMiAxMTowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ',
  dc3: 'https://www.discovercars.com/offer/bd59ee39-0fd4-41ea-9e9e-ad3b5066c5d2-QR2J?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoyMTk1LCJEcm9wT2ZmTG9jYXRpb25JZCI6MjE5NSwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTEwLTAyVDE3OjAwOjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wNVQxMDowMDowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIxMzNkMzA5ZDQ0YWQwZDk4NjcxNTM3M2M4YWY0ZjdmMCJ9',
  dc2b: 'https://www.discovercars.com/search/fb22a8ce-3cbe-4fe3-9460-0f5c3b24eec4?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoyMDg4LCJEcm9wT2ZmTG9jYXRpb25JZCI6MjA5MSwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTA5LTMwIDExOjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wMiAxMTowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ',
  dc4: 'https://www.discovercars.com/offer/6c79398c-62fc-4e95-ad7e-e0790fb480b3-TMQD?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoxNzEwLCJEcm9wT2ZmTG9jYXRpb25JZCI6MTcxMCwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTEwLTA1VDEzOjAwOjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wNlQxMzowMDowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiJjYjMyOTFmMWNiYWQ2MjU1MTA4OTY5MDBiNmMwYjFhMSJ9'
};

/* ---------- 两台车的取/还点（画在地图上） ---------- */
const CARPTS = [
  {k:'pick', c:P.kef,    label:'✅ 冰岛提车',  when:'9/25 08:00', car:'Land Rover Defender 110 · Premium SUV · Avis',
   note:'落地就取（不是第二天）：省掉 4 人 ×2 程机场大巴 ≈ ¥1,360。🆕 **2026-09-04 实测：取车钟点对价格完全没影响** —— 08:00 / 10:00 / 12:00 / 13:00 / 15:00 / 16:00 六个点全部同价（$326 那台 Peugeot 2008 4x4 自动，17 个报价，都是 5 个计费日）。⛔ 所以旧注里那句「必须填 17:00，早 3 小时会跨进第 5 个计费日、白贵 $65」**是错的**：那 $65 是两次抓取之间的价格变动，不是计费悬崖。**唯一真的悬崖在 18:00**（9/25 18:00 之后取才降到 4 个计费日，但那就等于放弃第一天）。🔴 而且如果 Kevin 坐唯一那班直飞（SAS 06:15→**07:05**），17:00 取车等于在机场干等 10 小时 → **按落地时间填**'},
  {k:'drop', c:P.kef,    label:'冰岛还车',  when:'9/29 18:00', car:'Land Rover Defender 110',
   note:'⚠️ 还车时间取决于 Kevin 的 KEF→OSL 起飞时间（见 B1）'},
  {k:'pick', c:P.eve,    label:'✅ 挪威提车①', when:'9/30 11:00', car:'Ford Explorer 4WD · 纯电 · SIXT · $646.14',
   note:'已订。落地 10:35 → 11:00 取车；押金预授权 $1,170。免费取消截止 9/28 11:00。'},
  {k:'drop', c:P.lknair, label:'✈️ 还车① Leknes 机场（LKN）', when:'10/2 14:30', car:'Ford Explorer 4WD · 纯电',
   note:'🆕 **2026-09-04 改**：航班定了 —— **WF816 LKN 15:40 → TOS 16:35**，所以还车点从 Svolvær 换成 **Leknes**、时间从 08:30 推到 **14:30**（距起飞 70 分钟，Widerøe 国内线行李截止约 30 分钟前 → 够用，想更稳订 14:00）。Lyngvær → Leknes **63.6 km / 1h16**（OSRM 实测）。🔴 Leknes 异地还车**只有 5 个报价** → 最早订这段。🟠 48h 悬崖：10/2 11:00 前还 = 2 天 $571，14:30 还 = 3 天 $647，**多付 $76 买下最后 3.5 小时**'},
  {k:'pick', c:P.tosair, label:'✅ 挪威提车②', when:'10/2 17:00', car:'Mercedes-Benz EQS 4WD · 纯电 · SIXT · $455.59',
   note:'已订。16:35 落地 → 17:00 取车，等 25 分钟；押金 $1,500。免费取消截止 9/30 17:00。'},
  {k:'drop', c:P.tosair, label:'挪威还车②', when:'10/5 **17:00**', car:'Mercedes-Benz EQS 4WD · 纯电',
   note:'已订到 17:00，与 17:00 取车刚好满 72 小时。去 Senja 需要提前规划快充点。'},
  {k:'pick', c:P.osl, label:'✅ 奥斯陆提车③', when:'10/5 **13:00**', car:'Porsche Macan 4WD · 保证车型 · 纯电 · $288.10',
   note:'已订保证车型的 Macan。配 Norwegian TOS→OSL 10:45→12:40；落地后 20 分钟提车。押金 $1,340，免费取消截止 10/3 13:00。'},
  {k:'drop', c:P.osl, label:'奥斯陆还车③', when:'10/6 13:00', car:'Porsche Macan 4WD · 纯电',
   note:'从 Stange 开 30 min 回 OSL 还车，直接接洲际。若 Kevin 的北京航班是 10/7，这台顺延一天 +$79'}
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
    stay:{name:'🆕🆕 Radisson Blu Airport Hotel ×2 间（连廊直通航站楼）',type:'酒店',rb:'1 间 Superior 大床 + 1 间 Standard 双床',
          price:'€309 + €296 = €605（+12% VAT ≈ €678 ≈ ¥5,420）· 含早',cxl:'✅ 可退到当天 18:00',
          url:U.rad24, pt:P.osl, place:'OSL 航站楼连廊尽头，走 5 分钟',
          note:'🆕🆕 **2026-09-05 口径改成「舒适优先」后换成这家**（实价当日抓的）。'+
               '**它是 OSL 唯一走连廊直通航站楼的酒店** —— 不打车、不等班车、不出户。'+
               '这一夜是 **21:30 落地 / SK4787 06:15 起飞**，全程最不能出岔子的一夜：'+
               '住这里 22:20 进房、**05:00 走（6.7 小时）**；住 Nannestad 要打车 20 min、04:30 就得走（5.8 小时）。'+
               '<br>🛏 **房型分开挑**：Standard = 2 张单人床、Superior = queen、Superior Airport View = king '+
               '→ **夫妻订 Superior**，别两间都订 Standard。'+
               '<br>💰 比原方案（<a href="'+U.nannestad+'" target="_blank">Nannestad €260 不可退</a> + 两趟深夜打车）**多约 ¥2,700** —— 按新口径该花。'+
               '<br>🟢 **可退到当天 18:00**，是全程最宽的退改条件 → 洲际钟点还没确认也能现在就锁。'+
               '<br>🟠 想少花 ¥2,500 就退回 <a href="'+U.clarion+'" target="_blank">Clarion €138/间 ×2</a>（走 5 分钟，但也是双床房）'},
    spend:{stay:5420}, supply:'green',
    hi:['中转睡一晚，不安排活动','9/25 一早飞 KEF','🆕 打车那一段已删掉 —— 走连廊'],
    watch:['🆕 换成 Radisson 之后，**全程不可退的只剩 9/26 那一晚**（而且已改买可退档 → 归零）']
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
          note:'✅ **Steve 的清单和我原来的默认是同一套房** —— 这一晚没有分歧。'+
               '€647 打到 €447，是这次抓到最大的折扣之一。雷市这一晚候选最多（5 个合格房源），压力最小'},
    car:{name:'✅ Land Rover Defender 110 · Premium SUV · Avis',seg:'冰岛 · KEF 9/25 08:00 → KEF 9/29 18:00（5 天）',
         price:'$1,020.00（已全额预付）',cny:'¥7,242',
         url:U.dcars, pick:P.kef, drop:P.kef, pickWhen:'9/25 08:00', dropWhen:'9/29 18:00',
         note:'已订：自动挡、5 座、不限里程；押金 $330。页面提示取车时需出示保险证明。免费取消截止 9/23 08:00（当地时间）。'},
    spend:{stay:3576, car:7242}, supply:'green',
    hi:['Hallgrímskirkja / 老港 / Sun Voyager','落地就提车 = 省掉 4 人来回机场大巴 ¥1,360'],
    watch:['🟠 取车时带好保险证明；预订页没有加 DiscoverCars 第三方 Full Coverage']
  },
  {
    id:'D2', date:'9/26', wd:'周六', region:'iceland', base:'Hörgsland（Klaustur 东）',
    title:'南岸瀑布线（塞里雅兰 + 斯科加）',
    anchor:P.hvolsvollur,
    route:[{n:'Reykjavík',c:P.rvk},{n:'Seljalandsfoss',c:P.seljaland},
           {n:'Skógafoss',c:P.skogafoss},{n:'Vík',c:P.vik},{n:'Hörgsland 住处',c:P.horgsland}],
    legs:[{k:'drive',pts:[P.rvk,P.seljaland,P.skogafoss,P.vik,P.horgsland]}],
    drive:'约 300 km / 3h45（住处往东挪到 Klaustur 东侧）',
    stay:{name:'Hörgsland Cottages · Three-Bedroom Vacation Home（整栋）',type:'酒店/木屋（Booking）',rb:'3 卧 · 整栋 · 私厨私卫',
          price:'€448 + 11% VAT/城市税 = €503 · ¥2,012/房',cxl:'⛔ 不可退（€489→€549 可退到 9/12）',
          url:U.horgsland, pt:P.horgsland, place:'Hörgsland · Kirkjubæjarklaustur 东 10 km',
          note:'🥇 **Steve 自己选的，已设为默认**（2026-09-02 实测：3 卧整栋 €448，"We have 5 left"）。'+
               '整栋装 4 人（不是每间价），538 ft²、私人厨房、山景、含 1 车位。'+
               '🟠 **床型要注意：卧室 1/2 是上下铺、卧室 3 是两张单人床 —— 没有双人床**，那对夫妻要么睡两张单人。'+
               '在意就换 Klaustur 一带的 Fosshotel Núpar / Hótel Laki / Magma。'+
               '备选（我原来的默认）<a href="'+U.hvols+'" target="_blank">Hotel Hvolsvöllur ×2 间 €374 含税</a>，便宜 €129 且可退到 9/24 + 到店付'},
    spend:{stay:5512}, supply:'red',
    hi:['塞里雅兰瀑布（能绕到瀑布后面）','斯科加瀑布','9 月底不需要冬胎（11/1 才强制）',
        '🎯 住处从 Hvolsvöllur 往东挪到 Hörgsland：今天多开 100 km，**但 9/27 从 390 km 降到 200 km**，冰河湖那天变得很轻松'],
    watch:['⛔ 这一晚**不可退** —— 想留反悔权就订 €489（可退到 9/12，多付 €41 ≈ ¥328）',
           '🟠 三个卧室都没有双人床（上下铺 ×2 + 单人床 ×2）']
  },
  {
    id:'D3', date:'9/27', wd:'周日', region:'iceland', base:'Höfn（冰河湖以东）',
    title:'冰河湖 + 钻石沙滩 · 夜里去 Stokksnes 等极光',
    anchor:P.hofn,
    route:[{n:'Hörgsland',c:P.horgsland},{n:'Skaftafell',c:P.skaftafell},
           {n:'Jökulsárlón 冰河湖',c:P.jokulsarlon},{n:'Diamond Beach',c:P.diamond},
           {n:'Birkifell 住处',c:P.birkifell},{n:'Stokksnes / Vestrahorn',c:P.stokksnes}],
    legs:[{k:'drive',pts:[P.horgsland,P.skaftafell,P.jokulsarlon,P.birkifell,P.stokksnes,P.birkifell]}],
    drive:'约 200 km / 2h30（比原方案的 390 km 少一半 —— 因为 9/26 已经往东挪了）',
    stay:{name:'Guesthouse Birkifell · Two-Bedroom House（整栋）',type:'酒店/整栋（Booking）',rb:'2 卧 · 整栋 · 厨房 + 私卫',
          price:'€504 + 11% VAT/城市税 = €565 · ¥2,260/房',cxl:'✅ 免费退到 9/25 · **到店付**',
          url:U.birkifell, pt:P.birkifell, place:'Nesjahverfi · Höfn 西 10 km · 离 Stokksnes ~25 min',
          note:'🥇 **Steve 自己选的，已设为默认**（2026-09-02 实测：2 卧整栋 €504，"Only 1 left"）。'+
               '床型对这组人正好：**1 张 queen + 2 张单人床**（那对夫妻有双人床）。'+
               '整栋乡下独立屋 + 自带厨房 → 极光可以在屋里等、出去看、再回屋，这是极光夜真正值钱的东西。'+
               '🔴 **只剩 1 套 + 免费退 + 到店付 → 这一晚排下单第 1 位**，零风险。'+
               '备选（我原来的默认）<a href="'+U.arnanes+'" target="_blank">Árnanes ×2 间 €626 含税</a>，贵 €61 且是酒店房不是整栋'},
    spend:{stay:4520}, supply:'red',
    hi:['Jökulsárlón 冰河湖 + Diamond Beach','🥇 Stokksnes / Vestrahorn 离住处 ~25 min —— 黑沙滩 + 尖角山，极光前景比冰河湖好',
        '整栋房 + 厨房 → 极光可以「屋里等 · 出去看 · 再回屋」，不用在车里冻',
        'Höfn 是真镇子，有挪威海螯虾（langoustine）餐厅'],
    watch:['🔴 **Only 1 left** —— 但免费退到 9/25 且到店付 → 先订下来，零成本',
           '🔴 天然蓝冰洞一般 11 月才开 → 9 月能做的是 Katla 冰洞（Vík 出发，全年开）或冰川徒步，Kevin 在找票',
           '🟠 极光看不看得到主要取决于**云量**，不取决于住多东 —— 往东挪买到的是「前景近 + 能反复进出屋」，不是更高的 KP']
  },
  {
    id:'D4', date:'9/28', wd:'周一', region:'iceland', base:'Reykjanesbær（KEF 旁）',
    title:'西返 · 黄金圈 + 蓝湖',
    anchor:P.reykjanes,
    route:[{n:'Nesjahverfi',c:P.birkifell},{n:'冰河湖（再看一次）',c:P.jokulsarlon},
           {n:'Þingvellir',c:P.thingvellir},{n:'Geysir',c:P.geysir},{n:'Gullfoss',c:P.gullfoss},
           {n:'Blue Lagoon',c:P.bluelagoon},{n:'Njarðvík 住处',c:P.njardvik}],
    legs:[{k:'drive',pts:[P.birkifell,P.jokulsarlon,P.vik,P.thingvellir,P.geysir,P.gullfoss,P.bluelagoon,P.njardvik]}],
    drive:'约 520 km / 6h30（全程最长的一天）',
    stay:{name:'🆕 Holiday Home with Hot tub & Sauna · Ocean Break ★5.0',type:'Airbnb',rb:'3房/3床/**1卫**',
          price:'€531 → **€335** 总价 · ¥1,340/房',cxl:'✅ 免费退到 **9/23**',rating:'5.0',
          url:U.njardvik3, pt:P.njardvik, place:'Njarðvík · 离 KEF 机场 5 min',
          note:'🆕 **2026-09-02 Steve 换的第二个链接，已核可订，比原来那套便宜 €110 ≈ ¥880。** '+
               '床型正好：**卧 1 一张 king（给那对夫妻）· 卧 2、卧 3 各一张单人床** → 四个人一人一间。'+
               '还带 **hot tub + sauna**，★5.0。'+
               '🟠 唯一的降级是 **只有 1 个卫生间**（原来那套是 2 个）—— 4 个人 1 卫，'+
               '而且第二天要赶 Reykjanes 轻档，早上会排队。想要 2 卫就退回 '+
               '<a href="'+U.njardvik+'" target="_blank">Cozy home 4房/2卫 €445</a>（贵 €110）或我原来的 '+
               '<a href="'+U.keflavik+'" target="_blank">3BR/2BA Reykjanesbær €424 ★4.92</a>。'},
    spend:{stay:2680}, supply:'green',
    hi:['Þingvellir 裂谷 · Geysir 间歇泉 · Gullfoss 黄金瀑布','Blue Lagoon 泡汤（离 KEF 20 min）'],
    watch:['这一天车程最长，注意 9 月末南岸风暴封路（存 road.is）']
  },
  {
    id:'D5', date:'9/29', wd:'周二', region:'iceland', base:'Oslo Gardermoen',
    title:'🥇 已减负：雷克雅内斯半岛小环线 + 泡汤 + 还车飞奥斯陆',
    anchor:P.gunnuhver,
    route:[{n:'Njarðvík 08:30 出发（睡到自然醒）',c:P.njardvik},
           {n:'Gunnuhver 地热泥池',c:P.gunnuhver},
           {n:'大陆桥 Bridge Between Continents',c:P.bridge},
           {n:'Reykjanesviti 灯塔 + Valahnúkamöl 海崖',c:P.reykjanesviti},
           {n:'Brimketill 石潭',c:P.brimketill},
           {n:'泡汤：Blue Lagoon 或 Sky Lagoon',c:P.skylagoon},
           {n:'KEF 还车',c:P.kef},{n:'OSL',c:P.osl}],
    legs:[{k:'drive',pts:[P.njardvik,P.gunnuhver,P.bridge,P.reykjanesviti,P.brimketill,P.skylagoon,P.kef]},
          {k:'fly',from:P.kef,to:P.osl}],
    drive:'约 2h 纯开车（原方案 7.5h）· 所有点都在 KEF 15–50 min 圈内',
    stay:{name:'🆕🆕 Radisson Blu Airport Hotel ×2 间（连廊直通航站楼）',type:'酒店',rb:'1 间 Superior 大床 + 1 间 Standard 双床',
          price:'€256 + €240 = €496（+12% VAT ≈ €556 ≈ ¥4,450）· 含早',cxl:'✅ 可退到当天 18:00',
          url:U.rad29, pt:P.osl, place:'OSL 航站楼连廊尽头，走 5 分钟',
          note:'🆕🆕 **2026-09-05 舒适优先，这一晚也换成连廊那家。**🔴🔴 **这是全程最紧的一夜，而且 DY1171 已出票 —— 00:45 落地是事实。**'+
               '住这里 **01:00 进房、07:50 走（6.8 小时）**，中间一步不出楼；'+
               '原方案（<a href="'+U.nann5br+'" target="_blank">Nannestad 5房1.5卫 €292</a>）要在**凌晨 1 点等出租车**、01:30 才到、07:30 就得走，'+
               '而且只有 **1.5 个卫生间**、还要赌房东让不让深夜自助入住。'+
               '<br>**换到的是：不在凌晨等车 · 多睡约 50 分钟 · 24h 前台 · 走前吃上早餐。** 多花约 ¥2,400。'+
               '<br>🛏 同样**夫妻订 Superior 大床**。🟠 想少花就退回 <a href="'+U.clarion+'" target="_blank">Clarion €95/间 ×2</a>（走 5 分钟）。'+
               '<br>🟠 **另一条治本的解法**：若 9/30 那班 EVE 改成同价的 **13:20→15:00**，这一夜能睡 10 小时以上 —— '+
               '按舒适口径我倾向选它（连着两个短夜之后，进罗弗敦第一天本来也只是开车+入住）'},
    spend:{stay:4450}, supply:'green',
    hi:['🎯 按「9/29 丢一些景点别那么累」改的：开车 7.5h → **2h**，起床 05:30 → **08:30**',
        '🟢 附带红利：**不再依赖 Kevin 的 KEF→OSL 起飞时间**（16:00 前就能回 KEF），原来那个"唯一硬前提"消失了',
        '🥈 还想多玩就用中档：斯奈山**只走南半段** Ytri-Tunga + Búðakirkja + Arnarstapi–Hellnar，**丢掉草帽山 Kirkjufell 和 Djúpalónssandur** → 开车 ~5h，08:00 出发 16:30 回 KEF',
        '为什么先丢 Kirkjufell：它离 Keflavík **单程 4h / 275 km**，一个景点吃掉 3h+ 往返，是那天最大的一笔'],
    watch:['🟠 火山：2026-09 初**没有正在喷发**（上次 2025-08-05 结束），但 Svartsengi 下岩浆仍在积累、气象局说近期再喷"可能"。上面这些点目前都开放，但**43 号路（去 Grindavík/蓝湖）反复被熔岩切断**、425 常和它一起关 → 当天早上必看 road.is + safetravel.is',
           '泡汤选 **Sky Lagoon**（Kópavogur，离 KEF ~45 min）更稳 —— 它不在火山区；Blue Lagoon 离 KEF 只 20 min 但会因火山临时关，要提前订',
           '中档（斯奈山南半段）才需要留意起飞时间：要 18:00 之后的班',
           '⚠️ Keflavík→Ytri-Tunga 车程两个来源不一致（2h vs 我们旧文档的 2h45）→ 按 2–2h45 留富余']
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
    stay:{name:'Nordic Lodge Retreat · Lyngvær（已订）',type:'Airbnb',rb:'4房/8床/2卫',
          price:'€898 / 2 晚 · ¥1,796/房/晚',cxl:'✅ 24h 内免费 · 9/23 前部分退',
          url:U.lofnew, pt:P.vagan, place:'Lyngvær · Vågan（Svolvær 旁）· 住 2 晚不搬箱子',
          note:'✅ **Steve 已下单。** 2025 年 1 月新建的整栋 lodge，98 m²，**4 卧 8 床 2 卫**（10 人上限，'+
               '我们 4 人非常宽裕）· 按摩浴缸 + 桑拿 · ★4.92 · 38 条评价 · Superhost · 自助 keypad 入住。'+
               '在 Lyngvær，Svolvær 旁边 —— 仍是东侧，「决定 1：选东侧」不变。'+
               '⚠️ **表里的 €898 取自搜索页快照，请拿你订单上的实付金额对一下**（房源页在我们这台机器上不给价）。'},
    car:{name:'✅ Ford Explorer 4WD · 纯电 · Full-size SUV · SIXT',
         seg:'罗弗敦：EVE 9/30 11:00 → LKN 10/2 14:30（3 天）',
         price:'$646.14：已付 $14.01 · 取车付 $632.13',cny:'¥4,588',
         url:U.dcars, pick:P.eve, drop:P.lknair, pickWhen:'9/30 11:00', dropWhen:'10/2 14:30',
         note:'已订：自动挡、5 座、不限里程。到店价含租金 $309.70 + 异地还车费 $322.43；押金 $1,170。免费取消截止 9/28 11:00（当地时间）。'},
    spend:{stay:3592, car:4588}, supply:'amber',
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
    stay:{name:'同 D6（Nordic Lodge Retreat，连住第 2 晚）',type:'Airbnb',rb:'4房/8床/2卫',
          price:'含在 €898 / 2 晚内 · ¥1,796/房/晚',cxl:'✅ 24h 内免费 · 9/23 前部分退',
          url:U.lofnew, pt:P.vagan, place:'Lyngvær · Vågan',
          note:'**选东侧不等于放弃西侧风景** —— 这一天专门西行：Hamnøy 那排最出名的红屋、Sakrisøy、Reine，沿路停，晚饭前回来'},
    spend:{stay:3592}, supply:'amber',
    hi:['Hamnøy 红屋（Eliassen Rorbuer 那排）','Sakrisøy 黄房子','Reinebringen 阶梯往返约 1.5–2h','极光季已开季'],
    watch:['🟠 E10 风暴封路在 9 月末–10 月很常见 → 这也是「东侧 + 可退」比「西侧 + 不可退」好的原因']
  },
  {
    id:'D8', date:'10/2', wd:'周五', region:'tromso', base:'特罗姆瑟',
    title:'✈️ 航班已定：WF816 Leknes 15:40 → 特罗姆瑟 16:35（55 min）',
    anchor:P.tromso,
    route:[{n:'Lyngvær 出发（最晚 13:00；想去 Henningsvær 就 10:30 走）',c:P.vagan},
           {n:'（可选）Henningsvær 28 min → 再 1h05 到 Leknes',c:P.henningsvaer},
           {n:'🔴 Leknes 机场还车① **14:15–14:30**',c:P.lknair},
           {n:'WF816 LKN 15:40 → TOS 16:35（Widerøe Dash-8，直飞）',c:P.tosair},
           {n:'特罗姆瑟机场提车② 17:30',c:P.tosair},
           {n:'住处 check-in 约 18:15（天刚黑，当晚就能追极光）',c:P.tromso}],
    legs:[{k:'drive',pts:[P.vagan,P.henningsvaer,P.lknair]},
          {k:'fly',from:P.lknair,to:P.tosair},
          {k:'drive',pts:[P.tosair,P.tromso]}],
    drive:'Lyngvær → Leknes 机场 **63.6 km / 1h16**（OSRM 实测）· 上午整个是白得的，傍晚落地',
    stay:{name:'Tromsø 4 房 · 4 床 · 2 卫',type:'Airbnb',rb:'4房/4床/2卫',
          price:'€1,526 / **3 晚**（10/2–10/5）· ¥2,035/房/晚',cxl:'✅ 免费退到 10/1',
          url:U.tos4br3n, pt:P.tromso, place:'特罗姆瑟 · 住 3 晚（10/2–10/5）',
          note:'🥇 **Steve 自己选的，已设为默认**（2026-09-02 实测可订）。'+
               '✅ **2026-09-02 傍晚：原来那个「10/5 那晚没地方住」的窟窿已经不存在了** —— '+
               'Steve 又给了 10/5 的奥斯陆房源，说明 **10/5 就飞回奥斯陆**，特罗姆瑟只住 3 晚。'+
               '所以他给的原链接（10/2→10/5）本来就是对的，**不用改日期，也省下那 €453**。'+
               '🆕 **2026-09-05：船屋那条「便宜 ¥5,600」的建议已撤销 —— 就订这套。** 按舒适口径：这是全程唯一连住 3 晚的家，'+
               '而且每晚都要出去追极光、零点回来，**摇的、要上下船的、卫生间在船上的**，不是这一段该省钱的地方。'+
               '（原备选 <a href="'+U.houseboat+'" target="_blank">Houseboat "Grosso" 3房/7床/3卫 ★5.0（3 晚 €825）</a> '+
               '仍然便宜约 **€700 ≈ ¥5,600**、卫生间还多一个（住船上）—— 这一段的差价是全程最大的一笔，值得再比一次'},
    spend:{stay:4069, car:3235, other:5960}, supply:'amber',
    hi:['🆕🆕 **2026-09-04：航班从「未核实的 SVJ 早班」换成 Steve 查到的实班 —— WF816 Leknes 15:40 → 特罗姆瑟 16:35**（周五，Dash-8，直飞 55 min）。B1 这个红色阻塞**就此解除**',
        '🔴 **连带把车①的还车点从 Svolvær 换成 Leknes、还车时间从 08:30 推到 14:30** —— 因为飞机从 Leknes 起飞，而且是下午',
        '**车费几乎没变**：车① EVE 9/30 11:00 → **LKN 10/2 14:30 · 3 天 Ford Explorer 4WD $647**（旧方案 EVE→SVJ 2 天 Yaris Cross $650）—— 多一个计费日、车还大一号，价钱一样',
        '**车② 反而便宜了**：取车从 10:30 推到 **17:30**（等飞机落地），3 天自动四驱 **$224**（旧 $240）—— 晚取不加价，16 个报价里挑的',
        '机票实价（携程 2026-09-04）：**¥1,274/人不带行李 · ¥1,490/人含 23kg 托运 · ¥2,065/人免费退改**。4 人按含托运算 = **¥5,960**（旧账按 ¥5,360 估，实际只多 ¥600）',
        '这一改**上午整个白得**：Lyngvær 13:00 出发就够，想加 Henningsvær 10:30 走，想跑西侧沙滩（Ramberg → Leknes 35 min）09:00 走',
        '代价：**特罗姆瑟的下午没了** —— 18:15 才到住处（旧方案中午就到）。但 10 月初特罗姆瑟 18:30 天黑，等于只损失采购时间，极光夜完整'],
    watch:['🔴🔴 **机票只剩 6 张，我们要 4 张 → 这是现在最急的一件事**（携程页面写「剩 6 张」）。⚠️ 最便宜那档 ¥1,274 **不含托运也不含手提**（只给 1 件个人物品）—— 13 天的箱子装不下，**要买 ¥1,490 那档（含 1×23kg 托运 + 1 件手提）**',
           '🔴 **还车时间不能再往后拖**：14:30 还车 → 距 15:40 起飞 70 分钟。Widerøe 国内线行李截止约 30 分钟前、登机口 20 分钟前，70 分钟是舒服的；再晚就没有余量了。想更稳就订 **14:00**',
           '🟠 **48 小时那个计费悬崖在这里**：EVE 9/30 11:00 起算，10/2 **11:00 之前**还车 = 2 个计费日 $571；拖到 14:30 = 3 个计费日 $647。**多付 $76 ≈ ¥540 换罗弗敦最后 3.5 小时** —— 我建议付（不然就是在一个很小的机场干等 4h40）',
           '🔴 **Leknes 异地还车只有 5 个报价**（特罗姆瑟 16 个、Evenes 22 个）→ 库存薄、涨价快，**车①要最早订**',
           '🟡 Widerøe Dash-8 是小飞机，4 个大箱子的托运额要按人算清（¥1,490 档 = 每人 1×23kg，刚好 4 件）',
           '✅ **顺便结掉「同地还车 vs 异地还车」这个问题**：同地还回 EVE 确实便宜得多（2 天自动四驱只 $114–129，省 $500+），但**EVE→TOS 没有能用的航班** —— 直飞每月仅 4 班（≈每周 1），其余全经奥斯陆倒 1,200 km / 4–6h / NOK 7,768 起。而且 10/2 那天从 Lyngvær 回 EVE 要**倒开 175 km / 3h02**（去 Leknes 只要 63.6 km / 1h16）。所以：**异地还到 Leknes 是对的**，那 $500 是「不用往回开 175 km + 有飞机可坐」的价钱',
           '🟡 Svolvær(SVJ) 其实离住处更近（26 min vs 1h16）、异地费也差不多（3 天 $644）—— 但那班早班机我们从来没核实过，而 Leknes 这班是**真的能订的**。除非 SVJ 也查到同价位的班，否则不用回头',
           '⬅️ 不想多花钱就退回自驾：480 km / 6h30，Narvik 一带 10 月初可能已有初雪']
  },
  {
    id:'D9', date:'10/3', wd:'周六', region:'tromso', base:'特罗姆瑟',
    title:'特罗姆瑟市区 · 缆车 + 极光',
    anchor:P.tromso,
    route:[{n:'住处',c:P.tromso},{n:'北极大教堂 / Fjellheisen',c:P.tromso}],
    legs:[], drive:'市区 + 郊外追极光',
    stay:{name:'同 D8（Tromsø 4房/4床/2卫，3 晚连住）',type:'Airbnb',rb:'4房/4床/2卫',
          price:'含在 €1,526 / 3 晚内 · ¥2,035/房/晚',cxl:'✅ 免费退到 10/1',
          url:U.tos4br3n, pt:P.tromso, place:'特罗姆瑟'},
    spend:{stay:4069}, supply:'green',
    hi:['北极大教堂 · Fjellheisen 缆车 · Polaria','自己有车 = 不被 tour 时间表绑住，可以往内陆躲云'],
    watch:['🆕 **特罗姆瑟只剩 3 个极光夜了**（10/2 / 10/3 / 10/4）—— 10/5 就飞奥斯陆。所以这一晚别偷懒，天一晴就出门']
  },
  {
    id:'D10', date:'10/4', wd:'周日', region:'tromso', base:'特罗姆瑟',
    title:'🆕 Senja 自驾一日（硬仗 —— 原来在 10/5，因为 10/5 改飞奥斯陆而挪到今天）',
    anchor:P.tungeneset,
    route:[{n:'住处 07:00 出发',c:P.tromso},{n:'Brensholmen 渡轮',c:P.brensholmen},
           {n:'Botnhamn',c:P.botnhamn},{n:'Bergsbotn 观景台',c:P.bergsbotn},
           {n:'Tungeneset',c:P.tungeneset},{n:'Ersfjordstranda',c:P.ersfjord},
           {n:'回程（Finnsnes 陆路可选）',c:P.finnsnes}],
    legs:[{k:'drive',pts:[P.tromso,P.brensholmen]},
          {k:'ferry',pts:[P.brensholmen,P.botnhamn]},
          {k:'drive',pts:[P.botnhamn,P.bergsbotn,P.tungeneset,P.ersfjord,P.bergsbotn,P.finnsnes,P.tromso]}],
    drive:'约 500 km 往返 · 路上 5–6h，只剩 4–5h 玩',
    stay:{name:'同 D8（Tromsø 4房/4床/2卫，最后一晚）',type:'Airbnb',rb:'4房/4床/2卫',
          price:'含在 €1,526 / 3 晚内',cxl:'✅ 免费退到 10/1',
          url:U.tos4br3n, pt:P.tromso, place:'特罗姆瑟'},
    spend:{stay:4069, other:306}, supply:'green',
    hi:['✅ Brensholmen–Botnhamn 渡轮 2026 全年运营 · NOK 228/车/单程（往返 456 ≈ ¥306）· 航程 35–45 min',
        '开：08:45 / 10:45 / 12:45(周五停) / 15:00 / 17:00 / 19:00 / 20:45',
        '陆路 Finnsnes / Gisund 大桥 ~2h30–3h，时间自由但慢',
        '这是最后一个极光夜（回程晚上正好在路上，Senja 那侧光污染更少）'],
    watch:['🔴 **挪到 10/4 = 周日，班次要重新核。** 我抓到的那张时刻表只标了「12:45 周五停」，'+
           '**没有单独核过周日**；北欧低季渡轮周日常减班。出发前上 Torghatten Nord / Entur 逐班对一次，'+
           '万一周日班少就走陆路（Finnsnes 大桥，多 1h 但不看船）',
           '10/4 特罗姆瑟日出 07:20 / 日落 18:25 → 07:00 出发是对的，别再晚',
           '🟠 天气不好可以和 10/3 互换（市区那天几乎不受天气影响）']
  },
  {
    id:'D11', date:'10/5', wd:'周一', region:'oslo', base:'特罗姆瑟 → 奥斯陆（Stange 森林小屋）',
    title:'🆕 还车 → 飞 TOS→OSL → 开 30 min 进 Mjøsli 森林小屋（带桑拿）',
    anchor:P.stange,
    route:[{n:'住处退房',c:P.tromso},{n:'TOS 机场还车②',c:P.tosair},
           {n:'飞 TOS→OSL 约 2h',c:P.osl},{n:'OSL 提车③（1 天）',c:P.osl},
           {n:'Konglehytta 3 · Mjøsli / Stange',c:P.stange}],
    legs:[{k:'drive',pts:[P.tromso,P.tosair]},
          {k:'fly',from:P.tosair,to:P.osl},
          {k:'drive',pts:[P.osl,P.stange]}],
    drive:'落地后再开 30 min（OSL → Mjøsli）',
    stay:{name:'🆕 Konglehytta 3 · Star View · Sauna ★4.98（整栋小木屋）',type:'Airbnb',rb:'2房/3床/**1卫**',
          price:'可退档 **€306**（不可退 €296，只差 €10）· ¥1,224/房',cxl:'✅ 选可退那档，只贵 €10',
          url:U.konglehytta, pt:P.stange, place:'Mjøsli · Stange（Innlandet）· 离 OSL 机场 30 min 车程',
          note:'🆕 **2026-09-02 Steve 给的第二个链接，已核可订。这一晚把原来那个「10/5 窟窿」直接补掉了** —— '+
               '而且顺带省下特罗姆瑟第 4 晚的 €453，净结果**比原方案便宜**。'+
               '床型很好：**卧 1 两张双人床 + 卧 2 一张双人床**，★4.98，**私人桑拿** + Mjøsa 湖景 + 星空。'+
               '🔴 **两条必须先处理的：** ① 它**不在 Gardermoen**，在 Stange 的 Mjøsli 森林里，'+
               '房源页自己写着「**A car is required**」（离 OSL 机场 30 min、离 Hamar 30 min、最近超市 Kiwi Minnesund 15 min）'+
               '→ **必须在 OSL 机场加租一台 1 天的车**（实抓 23 个报价，自动挡 $79 起、自动四驱 $86 ≈ ¥611）。'+
               '② 只有 **1 个卫生间**，而第二天要赶洲际航班。'+
               '不想加租车就退回 <a href="'+U.clarion+'" target="_blank">机场旁的 Clarion / Thon / Scandic（€193–244，两间双人房）</a>，'+
               '走廊到航站楼，代价是没有桑拿和星空。'},
    spend:{stay:2448, car:2046}, supply:'green',
    hi:['🆕 **这个改动的真正价值是买了一个缓冲夜** —— 不用在 10/6 当天先飞 TOS→OSL 再接洲际，一旦特罗姆瑟天气延误就不会丢掉回国的航班',
        '代价是**少了一个特罗姆瑟极光夜**（4 → 3 夜）。Stange 在 60.6°N，极光概率低得多，但小屋主打星空、光污染很低',
        '钱上反而更省：特罗姆瑟 −€453、9/28 −€110、车② −$103，加上小屋 +€306 和 OSL 那台车 +$86 → 净**便宜约 ¥1,400**'],
    watch:['🔴 **TOS→OSL 10/5 的机票是 Kevin 的活，但时间要挑早一点** —— 落地后还要提车 + 开 30 min，'+
           '而 10 月初 Stange 日落约 18:40，天黑了在林间小路找小屋不好玩',
           '🟠 **OSL 那台车要连着订到 10/6**（还车时间对上洲际航班），别只订 10/5 当天',
           '🟠 若 Kevin 的回程是 **10/7**，这个小屋可以直接多住一晚（顺带把 D12 的占位酒店省掉），但要另核 10/6 有没有货']
  },
  {
    id:'D12', date:'10/6', wd:'周二', region:'oslo', base:'Stange → OSL → 北京', cond:true,
    title:'🆕 小屋退房 · 开 30 min 回 OSL 还车 · 飞北京（第 13 晚只在 10/7 起飞时才要）',
    anchor:P.osl,
    route:[{n:'Konglehytta 退房',c:P.stange},{n:'OSL 机场还车③',c:P.osl},
           {n:'OSL → 北京',c:P.osl}],
    legs:[{k:'drive',pts:[P.stange,P.osl]},{k:'fly',from:P.osl,to:P.osl}],
    drive:'Mjøsli → OSL 机场 30 min（车已经在手上，不用叫车）',
    stay:{name:'🅿️ 占位：Clarion Hotel Oslo Airport ×2 Standard Double（只在 10/7 起飞时才订）',type:'占位 · 酒店',rb:'2 房 / 2 卫',
          price:'€86/间 +12% VAT = €193（≈¥1,544 · ¥772/房）· **未计入总账**',cxl:'✅ 退到 **10/5**',
          url:U.clarion, pt:P.osl, place:'OSL 机场旁（占位，等 Kevin 机票日期）',
          note:'🔴 **这一晚是条件性的**：若 Kevin 的 Oslo→北京 是 **10/6** 起飞就不需要 —— '+
               '🆕 而且现在**已经有了 10/5 那个缓冲夜**，10/6 当天直飞完全从容（不再是「当天先飞 TOS→OSL 再接洲际」）。'+
               '若是 **10/7** 起飞，最省事的是把 <a href="'+U.konglehytta+'" target="_blank">Konglehytta 小屋直接多住一晚</a>'+
               '（车也顺延一天），其次才是机场旁的 Clarion（最便宜的可退档、退到 10/5）或 '+
               '<a href="'+U.parkinn+'" target="_blank">Radisson（退到当天 18:00，€157/间）</a>；「每晚候选」那一节列了全部 5 个选项'},
    spend:{}, supply:'amber',
    hi:['🆕 **10/5 已经睡在奥斯陆了 → 10/6 是纯粹的「开 30 min + 还车 + 登机」**，这是这次改动最实在的收益',
        '若当天直飞北京，行程在这里结束'],
    watch:['🟠 等 Kevin 确认 Oslo→北京 是 10/6 还是 10/7（见 B2）—— 现在它只决定「要不要第 13 晚」，不再影响接驳风险']
  }
];

/* ---------- 逐晚汇总表（表格用；链接可点） ---------- */
const STAYTAB = [
  {st:'🆕 改推', d:'**9/24 → 9/25**',   place:'OSL 航站楼连廊（走 5 min）', name:'🆕🆕 Radisson Blu Airport ×2（Superior 大床 + Standard 双床）', url:U.rad24, type:'酒店', rb:'2 房 2 卫 · 含早', tot:'€605 +12% VAT',  room:'2,710', cxl:'✅ 可退到当天 18:00'},
  {st:'☑️ 已选定', d:'**9/25 → 9/26**',   place:'雷克雅未克',       name:'Aurora view 3BR 2BATH ★5.0',       url:U.aurora,    type:'Airbnb', rb:'3房/3床/2卫', tot:'€647→€447', room:'1,788', cxl:'✅ 24h / 9/18'},
  {st:'🆕 改档', d:'**9/26 → 9/27**',   place:'Hörgsland（Klaustur 东 10 km）', name:'Hörgsland Cottages · 3房整栋（🆕 买 €615 可退含早档）', url:U.horgsland, type:'酒店/木屋', rb:'3 卧 · 整栋 · 🔴 无双人床', tot:'€615 +税 ≈ €689', room:'2,756', cxl:'✅ 可退到 9/12 · 9/10 前不付钱'},
  {st:'☑️ 已选定', d:'**9/27 → 9/28**',   place:'Nesjahverfi（Höfn 西 10 km）',   name:'Guesthouse Birkifell · 2房整栋', url:U.birkifell, type:'酒店/整栋', rb:'2 卧 · 整栋', tot:'€565 含税', room:'2,260', cxl:'✅ 9/25 · 到店付'},
  {st:'☑️ 已选定', d:'**9/28 → 9/29**',   place:'Njarðvík（KEF 5 min）', name:'🆕 Hot tub & Sauna · Ocean Break ★5.0', url:U.njardvik3, type:'Airbnb', rb:'3房/3床/**1卫**', tot:'€531→€335', room:'1,340', cxl:'✅ 到 9/23'},
  {st:'🆕 改推', d:'**9/29 → 9/30**',   place:'OSL 航站楼连廊（走 5 min）', name:'🆕🆕 Radisson Blu Airport ×2（Superior 大床 + Standard 双床）', url:U.rad29, type:'酒店', rb:'2 房 2 卫 · 含早', tot:'€496 +12% VAT',  room:'2,225', cxl:'✅ 可退到当天 18:00'},
  {st:'✅ 已订', d:'**9/30 → 10/2**（2 晚）', place:'罗弗敦东侧 Lyngvær · Vågan', name:'🆕 Nordic Lodge Retreat ★4.92', url:U.lofnew,  type:'Airbnb', rb:'4房/8床/2卫', tot:'€898/2晚', room:'1,796', cxl:'✅ 24h / 9/23'},
  {st:'☑️ 已选定', d:'**10/2 → 10/5**（3 晚）', place:'特罗姆瑟',         name:'Tromsø 4房2卫（**3 晚，日期不用改了**）', url:U.tos4br3n,  type:'Airbnb', rb:'4房/4床/2卫', tot:'€1,526/3晚', room:'2,035', cxl:'✅ 到 10/1'},
  {st:'☑️ 已选定', d:'**10/5 → 10/6**',   place:'Stange / Mjøsli（OSL 30 min）', name:'🆕 Konglehytta 3 · Sauna ★4.98', url:U.konglehytta, type:'Airbnb', rb:'2房/3床/**1卫**', tot:'€306 可退', room:'1,224', cxl:'✅ 可退档只贵 €10'},
  {st:'⚪ 条件性', d:'**10/6 → 10/7**',   place:'（条件性）OSL 连廊',  name:'🅿️ 占位 🆕 Radisson Blu Airport ×2（10/6 明显便宜）',   url:U.rad1006,   type:'占位',   rb:'2 房 2 卫 · 含早',   tot:'€353 +VAT ≈ €395', room:'1,580', cxl:'✅ 可退到当天 18:00'}
];

/* ---------- 总览用：四台车一行一台 ---------- */
const CARTAB=[
  {u:U.dcars, chk:'✅ 已订 · Avis · 免费取消至 9/23 08:00', seg:'🇮🇸 冰岛', car:'Land Rover Defender 110 · Premium SUV · 自动', when:'KEF **9/25 08:00** → KEF **9/29 18:00**（5 天）',
   p:'$1,020.00', cny:'¥7,242',
   note:'✅ **已全额预付 $1,020**，取车时无剩余租金。押金 $330；不限里程。页面提示取车时需出示保险证明。'},
  {u:U.dcars, chk:'✅ 已订 · SIXT · 免费取消至 9/28 11:00', seg:'🇳🇴 车① 罗弗敦', car:'Ford Explorer 4WD · 纯电 · Full-size SUV', when:'EVE **9/30 11:00** → **Leknes(LKN) 10/2 14:30**（3 天）',
   p:'$646.14', cny:'¥4,588',
   note:'✅ 已付 $14.01，取车付 $632.13（租金 $309.70 + 异地还车费 $322.43）。押金 $1,170；不限里程。'},
  {u:U.dcars, chk:'✅ 已订 · SIXT · 免费取消至 9/30 17:00', seg:'🇳🇴 车② 特罗姆瑟', car:'Mercedes-Benz EQS 4WD · 纯电 · Special SUV', when:'TOS **10/2 17:00** → **10/5 17:00**（3 天）',
   p:'$455.59', cny:'¥3,235',
   note:'✅ 已付 $33.77，取车付 $421.82。押金 $1,500；不限里程；CDW 自付额 $2,150。取车在 TOS 航站楼内。'},
  {u:U.dcars, chk:'✅ 已订 · SIXT · 免费取消至 10/3 13:00', seg:'🇳🇴 车③ 奥斯陆', car:'Porsche Macan 4WD · 保证车型 · 纯电', when:'OSL **10/5 13:00** → **10/6 13:00**（1 天）',
   p:'$288.10', cny:'¥2,046',
   note:'✅ 已付 $26.45，取车付 $261.65。押金 $1,340；不限里程；CDW 自付额 $3,225。车型保证是这一单的关键。'}
];

/* ---------- 🆕 2026-09-04：航班 ↔ 取还车 对齐表 ----------
 * Steve 的两个要求：① 取车时间必须是「落地 + 30 min」，不要在机场干等；② 尽量把时间用满。
 * 关键实测结论（notes/_research/out_pickup/）：
 *   🟢 **取车钟点对价格是中性的** —— 冰岛 08:00/10:00/12:00/13:00/15:00/16:00 六个点
 *      全部同价（$326 那台 Peugeot 2008 4x4 自动，17 个报价，5 个计费日）；
 *      奥斯陆 10:45/13:00/14:00 全部 $85；特罗姆瑟 17:00 与 17:30 全部 $224。
 *      → **「落地 30 分钟后取车」不用付任何代价，直接照做。**
 *   🔴 花钱的是**还车**时间，不是取车时间（车① 的 48h 悬崖：$571 → $647）。
 * 航班时刻 = Google Flights 实抓（SAS/Norwegian 有供货），价格是 NOK / 4 人单程。
 */
const FLIGHTS = [
  {leg:'✈️ 9/25 OSL → KEF', st:'待订', who:'Kevin',
   best:'唯一直飞：**SAS 06:15 → 07:05**（2h50，NOK 19,392/4 人 ≈ ¥12,993，偏贵）',
   alt:'其余全是绕的：Air Baltic 13:55→23:55（RIX 停 6h35，NOK 10,452）· Finnair 12:50→16:30（HEL 停 35 min，NOK 23,836）· LOT 10:45→23:55（WAW 停 8h50）',
   car:'🇮🇸 冰岛那台：**取车 = 落地 + 30 min**',
   gap:'若坐 07:05 那班 → **07:35 取车**（原方案写的 17:00 会白等 10 小时）',
   note:'🟢 **取车钟点不影响价格**（08:00–16:00 六个点实测同价）→ 定了航班直接填「落地+30min」。'+
        '🎯 而且 07:05 落地等于**白得一整天**：D1 现在只排了「傍晚市中心」，完全可以把雷克雅内斯/蓝湖那半天挪到 9/25，'+
        '给 9/28 让出空间 —— 值得等 Kevin 的票定了再重排一次'},
  {leg:'✈️ 9/29 KEF → OSL', st:'待订', who:'Kevin',
   best:'最便宜的直飞：**Norwegian 20:05 → 00:45+1**（2h40，NOK 4,280/4 ≈ ¥2,868）',
   alt:'SAS 18:55→23:35（NOK 9,845）· SAS 11:15→15:55（NOK 14,372）· Icelandair 07:50→12:35（NOK 25,480）',
   car:'🇮🇸 冰岛那台：**还车 18:00**',
   gap:'18:00 还 → 20:05 起飞 = **缓冲 2h05**（国际线，合适）',
   note:'🔴 **这是全程最紧的一处接驳，但不是车的问题**：20:05 那班 **00:45 才落 OSL**，'+
        '而 9/30 飞 EVE 的最便宜那班是 **08:55** → 只能睡 5 小时。'+
        '两个解法：① 9/30 改坐 **13:20→15:00**（同价 NOK 4,196），代价是天快黑才进罗弗敦；'+
        '② 9/29 改坐 SAS 18:55→23:35（贵 NOK 5,565 ≈ ¥3,729），车提前到 17:00 还'},
  {leg:'✈️ 9/30 OSL → EVE', st:'✅ 时刻已核实', who:'Kevin 订票',
   best:'**Norwegian 08:55 → 10:35**（1h40 直飞，NOK 4,196/4 ≈ ¥2,811 —— 最便宜那档）',
   alt:'同价还有 13:20→15:00 和 15:05→16:45；SAS 15:00→16:40（NOK 5,596）',
   car:'🇳🇴 车①：**取车 11:00**（可填 10:45，同价）',
   gap:'10:35 落地 → 11:00 取车 = **等 25 分钟** ✅ 已经是你要的节奏',
   note:'🟢 计划里那个「10:35 落地」的假设**今天被实测确认了**，就是 Norwegian 这班。'+
        '10:45 取和 11:00 取同价（$647）→ 想留余量就填 10:45'},
  {leg:'✈️ 10/2 LKN → TOS', st:'✅ 航班已确认', who:'Steve 已查到（携程）',
   best:'**WF816 · 15:40 → 16:35**（Widerøe Dash-8，直飞 55 min）· ¥1,490/人含 23kg 托运 → 4 人 **¥5,960**',
   alt:'🔴 只剩 6 张票，我们要 4 张',
   car:'🇳🇴 车① **还车 14:30**（Leknes）· 车② **取车 17:00**',
   gap:'还车 14:30 → 起飞 15:40 = **缓冲 70 分钟**（够）· 落地 16:35 → 取车 17:00 = **等 25 分钟** ✅',
   note:'🆕 **车② 从 17:30 提前到 17:00** —— 17:00 和 17:30 实测同价（$224），'+
        '所以没有理由多等半小时。18:00 前后到住处，特罗姆瑟 10 月初 18:30 天黑 → 极光夜完整'},
  {leg:'✈️ 10/5 TOS → OSL', st:'待订', who:'Kevin',
   best:'🆕🥇 **Norwegian 10:45 → 12:40**（NOK 8,396/4 ≈ ¥5,620）—— **2026-09-05 按舒适口径从 08:20 换过来的**：08:20 要在跑完 Senja 的第二天 06:45 起床',
   alt:'08:20→10:15（NOK 6,396，早 2.5h 且便宜 NOK 2,000，但要 06:45 起床）· 06:20→08:15（同价，更早）· 13:00→14:55（7,596，白天只剩 2.5h）',
   car:'🇳🇴 车② **还车 10:00**（TOS 机场）· 车③ **取车 13:00**',
   gap:'🆕 还车 10:00 → 起飞 10:45 = **缓冲 45 分钟**（按 Steve 选的单子；国内小机场勉强够，别更晚）· 落地 12:40 → 取车 13:00 = **等 20 分钟** ✅',
   note:'🆕🆕 **2026-09-05 这一条按舒适口径翻过来了。**原来推 08:20 的两个理由（早到 2.5 小时、便宜 NOK 2,000）'+
        '在新口径下只剩前半个，而它的代价是**跑完 Senja 500 km 的第二天 06:45 起床** —— 那已经是全程第三个早起。'+
        '10:45 这班：睡到 08:30、吃完早饭退房、13:40 进小屋，**白天还剩约 5 小时**（18:45 天黑）+ 一整个傍晚泡私人桑拿。'+
        '多花约 ¥1,400。🟠 仍然想多要那 2 小时白天就用 08:20，车③ 改 10:45 取（同价）'}
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
  {id:'决定 2', q:'冰河湖那晚住哪？', a:'🆕 已改：Höfn 西的 Guesthouse Birkifell 整栋（Steve 自己找的，替掉我原来的 Árnanes）',
   why:'**Steve 找到的这个更好，所以推翻我自己的答案。** 同样在 Höfn 一带、离 Stokksnes ~25 min，'+
        '但它是**整栋房 + 自带厨房**（不是两间酒店房），而且**便宜 €61、免费退到 9/25、到店付**。'+
        '床型也更对：1 张 queen + 2 张单人 → 那对夫妻有双人床。',
   rows:[['🥇 Guesthouse Birkifell（新默认）','2 卧整栋 · €565 含税 · **¥2,260/房** · **只剩 1 套** · 免费退 9/25 · 到店付'],
         ['🥈 Árnanes（我原来的默认）','还有 4 间 · €626 含税 · ¥2,504/房 · 退到 9/20 · 酒店房含早'],
         ['备选 Fosshotel Vatnajökull','剩 2 间 · €776 · ¥3,104/房 · 退到 9/25'],
         ['⛔ Fosshotel Glacier Lagoon','只剩 1 间 · €1,194 · ¥4,776/房 超预算'],
         ['⛔ Stracta Apartments（Klaustur，住 2 晚那个方案）','€1,349/2 晚 —— 比 Hörgsland+Birkifell 贵 €281，且要放弃 Stokksnes']],
   plus:['整栋 + 厨房 → 极光可以「屋里等 · 出去看 · 再回屋」，不用在车里冻，这是极光夜真正值钱的东西',
         '🥇 Stokksnes / Vestrahorn 离住处 ~25 min，黑沙滩 + 尖角山当极光前景比冰河湖好',
         '冰河湖会看两次、两种光（9/27 往东 + 9/28 往西返）',
         '**免费退 + 到店付 = 零风险**，所以「只剩 1 套」不构成理由不订，反而是理由马上订'],
   keep:'🟠 关于「27 号住更东是不是更容易看到极光」：**不是**。极光强度（KP）跟经度无关，'+
        '决定成败的是**云量**，而 Vatnajökull 冰盖自己造云 —— 往东是抛硬币，不是升级。'+
        '往东真正买到的是「前景近 + 能反复进出屋」这两件事。⛔ 别为了极光去住 Vestmannaeyjar（岛上）：要赶渡轮，天气一变就走不掉。'}
];

/* ---------- 下单顺序（按会先没排，不按贵排） ---------- */
const URGENCY = [
  {rank:1, sev:'red',   what:'🆕 Guesthouse Birkifell 9/27 整栋 €504（+税 €565）',
   why:'**只剩 1 套**（页面写 "Only 1 left"），而它是这一晚最好的那个',
   deadline:'马上', how:'Booking —— **免费退到 9/25 + 到店付 = 零风险**，没有理由不先订下来'},
  {rank:2, sev:'red',   what:'✈️ Widerøe SVJ→TOS 10/2 直飞 ×4 人 + Svolvær 还车那台（$650）',
   why:'🔴 🆕 **Leknes 异地还车只有 5 个报价**（Evenes 22、特罗姆瑟 16）→ 库存薄、卖空就得改回自驾。🆕 **机票已经确认存在（WF816 LKN 15:40→TOS 16:35）但只剩 6 张，我们要 4 张** —— B1 从「不知道有没有」变成「快没票了」',
   deadline:'🔴 现在（票只剩 6 张）', how:'机票在携程上就能订（¥1,490 含托运那档）—— 不用去 wideroe.no；车走 DiscoverCars 免费取消'},
  {rank:3, sev:'red',   what:'🆕 特罗姆瑟 4房2卫 €1,526 / **3 晚（10/2–10/5，日期不用改了）**',
   why:'✅ 原来那个「10/5 没地方住」的窟窿已被 10/5 的奥斯陆小屋补掉 → **你给的原链接本来就是对的**。仍要早订的理由只剩「极光季开季，3 晚整套房不是随时都有」',
   deadline:'尽快，可退到 10/1', how:'Airbnb。🆕 **2026-09-05：船屋那条便宜 ¥5,600 的建议已撤销** —— 连住 3 晚 + 每晚零点从极光回来，不该睡船上'},
  {rank:4, sev:'done',  what:'✅ 罗弗敦 Nordic Lodge Retreat · Lyngvær（9/30 → 10/2）',
   why:'**已订，不用再管。** 4 卧 8 床 2 卫 · ★4.92 · 可退（24h 内免费 / 9/23 前部分退）',
   deadline:'—', how:'保留的动作只有一个：9/23 之前若行程有变，记得那天是部分退款的悬崖'},
  {rank:5, sev:'amber', what:'🆕🆕 Hörgsland Cottages 9/26 整栋 —— **改买 €615 那档（可退 + 含早）**',
   why:'"We have 3 left" → 不急。🆕 **2026-09-05 按舒适口径不再买 €497 不可退档**：多 €118 换「不被锁死 + 第二天不用自己做早饭」',
   deadline:'9/12 前（可退截止；9/10 前一分钱不付）',
   how:'Booking。🔴 **整栋没有一张双人床**（上下铺×2 + 两张单人）→ **订单备注里请他们把卧室 3 的两张单人床并起来**。'+
       '替代已实抓且更贵：Hotel Klaustur 能选 queen 但 €326 那档只剩 1 间（第二间 €674）→ 两间 €1,000；Fosshotel Núpar €519×2 = €1,038 —— **1.6–1.7 倍，且是两间酒店房而非整栋**'},
  {rank:6, sev:'amber', what:'雷市 9/25 €447（你和我选的是同一套）',
   why:'€647→€447 的折扣会过期；9/18 是部分退款悬崖',
   deadline:'9/18 前', how:'Airbnb —— 24h 内免费退'},
  {rank:7, sev:'amber', what:'另外三台车（冰岛 Peugeot 2008 $258 · 特罗姆瑟 **3 天 ~$240** · 🆕 **OSL 1 天 $79–86**）',
   why:'都可免费取消，而且只会越来越贵 → 先锁价。🆕 特罗姆瑟那台从 4 天缩到 3 天（省 $103）；OSL 那台是新加的 —— **10/5 的小屋写着 "A car is required"**，没车到不了',
   deadline:'现在', how:'DiscoverCars，零风险。OSL 那台记得订到 **10/6**（对上洲际航班），别只订 10/5 当天'},
  {rank:8, sev:'green', what:'🆕 Njarðvík 9/28 · Hot tub & Sauna ★5.0 €335',
   why:'供给充足（四个合格房源都有货），而且**这是全程最便宜的一晚**',
   deadline:'随时（可退到 9/23）', how:'Airbnb。🟠 它只有 1 个卫生间 —— 想要 2 卫就回到你第一个链接（Cozy home €445，贵 €110）'},
  {rank:9, sev:'red', what:'🆕🆕 **两个奥斯陆中转夜 → Radisson Blu Airport（连廊直通航站楼）**，各订 1 间 Superior 大床 + 1 间 Standard 双床',
   why:'🆕 **2026-09-05 舒适优先后，这条从「省钱建议」变成「最该先花的钱」。**两夜都是「落地→睡几小时→再起飞」'+
       '（9/24 21:30 落地 / 06:15 起飞；9/29 **00:45 落地**）。Radisson 是 OSL 唯一走连廊直通航站楼的 → '+
       '**四趟深夜打车全没了 · 两晚各多睡约 50 分钟 · 24h 前台**。9/24 €605 + 9/29 €496（+VAT ≈ ¥9,870），比原方案多约 ¥4,400',
   deadline:'现在就能订（**可退到当天 18:00**，全程最宽）', how:'Booking。🛏 Standard = 双床、Superior = queen、Superior Airport View = king → **夫妻订 Superior**'},
  {rank:10, sev:'done', what:'✅ ~~9/24 那一晚 Nannestad €260 不可退~~ → 已并入上面那条（Radisson）',
   why:'原来的约束是「不可退 → 必须等 Kevin 洲际票定」。换成可退到当天 18:00 的 Radisson 之后，**这个约束直接消失**',
   deadline:'—', how:'见 rank 9'}
];

/* ---------- 未决问题 ---------- */
const OPEN = [
  {sev:'red',   q:'✈️ 10/2 那天 Widerøe SVJ→TOS 直飞真的有班吗？票价多少？', why:'🔴 **只能人工上 wideroe.no 查** —— 官网有 Cloudflare 反爬，而 Widerøe 根本不给 Google Flights 供货（4 个不同日期试 SVJ/LKN 全零结果，同工具查 BOO→TOS 正常）。线索：每周约 8 班、周五历史上有 ~09:05 和 ~15:45。没有这班 → 退回 10/2 自驾 6h30', who:'Steve（5 分钟能查完）'},
  {sev:'green', q:'~~Kevin 的 9/29 KEF→OSL 起飞时间？~~ → 已不再是硬前提', why:'✅ 9/29 改成雷克雅内斯半岛轻档（开车 2h、16:00 前就能回 KEF）后，这个依赖消失了。只有想跑「斯奈山南半段」中档时才需要 18:00 之后的班', who:'—'},
  {sev:'amber', q:'Kevin 的 Oslo→北京 是 10/6 还是 10/7 起飞？（🆕 降级为 amber）', why:'10/7 → 10/6 在奥斯陆还要多一晚（第 13 晚，没计入总账，地图上按占位画出；最省事是把 Stange 小屋多住一晚 + 车顺延）。🆕 **它已不再影响接驳风险** —— 10/5 那个缓冲夜把「当天先飞 TOS→OSL 再接洲际」这个风险直接消掉了。另：Kevin 还要订 **10/5 TOS→OSL**，挑早一点的班', who:'Kevin'},
  {sev:'amber', q:'🆕 冰岛保险：**直接买零自付（zero-deductible）那档**，实价多少？', why:'🆕 **2026-09-05 舒适口径：不再只买最低的三样。**碎石路 + 10 月南岸沙尘暴是真实索赔项，'+
       '而「先垫 ISK 几十万再回来理赔」是最毁心情的事。$326 裸车 → 估约 $550–650。'+
       '⚠️ **要买供应商柜台那份零自付（当场免赔），不是 DiscoverCars 的 "Full Coverage"（第三方、先垫付再报销）**', who:'DiscoverCars 结账页 / 供应商'},
  {sev:'amber', q:'挪威 Vitara 的 $1,805 押金', why:'会冻结额度（不是扣款）→ 要确认有一张额度够的信用卡', who:'Steve'},
  {sev:'amber', q:'D3（9/27）蓝冰洞 → Katla 冰洞的决定', why:'天然蓝冰洞一般 11 月才开。换 Katla 后集合点在 Vík —— 住宿不受影响（Höfn 一带方案不动）', who:'Kevin 找票'},
  {sev:'green', q:'~~🔴 10/5 那一晚没地方住~~ → ✅ 已解决（而且比原来省钱）', why:'Steve 给了 10/5 的奥斯陆房源 → 行程改成「10/5 飞回奥斯陆睡缓冲夜」。特罗姆瑟回到 3 晚（−€453）、车② 缩到 3 天（−$103），加上小屋 +€306 和 OSL 那台车 +$86 → **净便宜约 ¥1,400**，还白得一个防延误的缓冲夜', who:'—'},
  {sev:'green', q:'~~🔴 10/5 要不要加租 OSL 那台车（B5）？~~ → 🆕 **已决定：租**', why:'🆕 **2026-09-05 舒适优先给了答案**：不租车就得把最后一晚从「整栋小木屋 + 私人桑拿 + ★4.98 + 湖景」换成机场连锁酒店，'+
       '只为省 ¥600–1,000 —— 新口径下不换。⚠️ 但**别点 $85 最便宜那档，那是 VW ID.4 电车**（1 天短租还要摸挪威充电桩）→ 选燃油自动四驱约 $120–150。'+
       '🔴 还车定 10/6 **09:00**（洲际时刻未定，先按至少留 3 小时排）', who:'✅ 已定'},
  {sev:'amber', q:'🟠 Senja 从 10/5 挪到 10/4（周日）—— 周日渡轮班次要重核', why:'我手上那张 Brensholmen–Botnhamn 时刻表只标了「12:45 周五停」，**没有单独核过周日**；北欧低季渡轮周日常减班。万一班少就走陆路 Finnsnes 大桥（多 1h）', who:'出发前一周核 Torghatten Nord / Entur'},
  {sev:'amber', q:'🟠 9/24 那一晚 —— 你的清单是 9/25 起的', why:'默认沿用我原来的 Nannestad 3房2卫 €260（不可退）。想和 9/29 用同一家 5 房那套也行，**但 9/24 的可订性我还没验**', who:'Steve 或我再验一次'},
  {sev:'amber', q:'🟠 Hörgsland 三个卧室都没有双人床，夫妻能接受吗？', why:'上下铺×2 + 单人床×2。不能接受就换 Klaustur 的 Fosshotel Núpar / Hótel Laki / Magma', who:'Steve 问一下'},
  {sev:'green', q:'挪威租车是否含 AutoPASS 标签，手续费怎么收？', why:'E10 + 特罗姆瑟这段收费站很少，金额很小', who:'租车公司'},
  {sev:'green', q:'Torghatten Nord 官网核 **10/4（周日）** Brensholmen–Botnhamn 确切班次', why:'低季会改点。已确认 2026 全年运营；🆕 但日期从周一挪到**周日**了，班表要重看', who:'出发前一周'}
];

/* ---------- 风险 ---------- */
const RISKS = [
  {r:'Airbnb 房源到下单时已被订走（搜索页有价 ≠ 能订）', imp:'要重新找，可能只剩更贵的', act:'🔴 已经踩过 4 次（见下方「踩过的坑」）→ 排名前 3 的今天就占住，都可免费退', sev:'red'},
  {r:'10/2 Widerøe SVJ→TOS 那班不存在 / 卖光', imp:'当天要么改回自驾 6h30，要么 SVJ→BOO→TOS 倒 2h50–4h+', act:'🔴 人工上 wideroe.no 核实后再订 Svolvær 还车那段（两件事要同时成立）；备选 Leknes(LKN)→TOS 每天 1 班，但要先往西开 1h15', sev:'red'},
  {r:'Svolvær 异地还车库存只有 6 个报价', imp:'卖空 = 飞的方案整体失效', act:'确认航班后立刻订；特罗姆瑟那台（24 个报价）不急', sev:'red'},
  {r:'~~D5 斯奈山赶飞机~~', imp:'—', act:'✅ 已消除：9/29 改雷克雅内斯轻档（2h 车程），不再赶 Kevin 的航班', sev:'done'},
  {r:'Nannestad 两晚不可退（€520 敞口）', imp:'机票一改就是白扔 ¥4,160', act:'放最后订；或换 Thon Gardermoen（退到 9/23）', sev:'amber'},
  {r:'冰岛保险包把车价从 $258 顶到 $480', imp:'总账 +¥1,576', act:'仍远低于 ¥2,000/天上限；线上先买比柜台便宜', sev:'amber'},
  {r:'挪威 $1,805 押金冻结', imp:'卡额度不够就提不到车', act:'出发前确认额度，别用接近满额的卡', sev:'amber'},
  {r:'秋季风暴封路（冰岛南岸 / 罗弗敦 E10 / 10/2 长途）', imp:'单日行程作废', act:'订可免费取消的房；存 road.is 和 vegvesen.no；东侧方案已把最长车程从 8h30 降到 6h30', sev:'amber'},
  {r:'~~10/2 Havila 舱位卖光 = 整段行程单点故障~~', imp:'—', act:'✅ 已消除：游轮整段 pass 掉，10/2 改自驾 + 并进船屋（还便宜了 ¥12,000）', sev:'done'},
  {r:'~~9/27 冰河湖那晚只有 Fosshotel 一个选择~~', imp:'—', act:'✅ 已消除：Fosshotel 只剩 1 间反而被排除；🆕 现在是 Höfn 西的 Guesthouse Birkifell 整栋（Árnanes 降为备选）', sev:'done'},
  {r:'罗弗敦异地还车贵 + 只有 6 个车源（**又回来了**）', imp:'为了 10/2 坐飞机必须还到 Svolvær → 车费 $762→$993', act:'这是「不开那 6h30」的明码价格，已在 D8 里算清；不接受就退回一台车自驾', sev:'amber'},
  {r:'~~中国驾照无 IDP，租车公司拒租~~', imp:'—', act:'✅ 已消除：用美国驾照，冰岛/挪威都直接认', sev:'done'},
  {r:'~~9 月底冰岛要不要冬胎~~', imp:'—', act:'✅ 已消除：11/1 起才强制', sev:'done'},
  {r:'Brensholmen 渡轮：🆕 Senja 那天从 10/5（周一）挪到 **10/4（周日）**', imp:'周日减班 → Senja 当天可能进不去', act:'季节性停开这件事已消除（2026 全年运营）；但**周日班表我没单独核过**，出发前一周核 Torghatten Nord / Entur。真班少就走陆路 Finnsnes 大桥（多 1h）', sev:'amber'}
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
  '🔴 <b>Airbnb 搜索卡片会撒谎，而且比想象的严重</b>：2026-09-02 又把 23 个候选逐个开了房源页，<b>10 个订不到 —— 5 个「Those dates are not available」+ 5 个 min-stay 2 晚</b>（换干净浏览器复现过，不是反爬）。加上前一轮的 4 个，<b>累计 9 个房源在搜索页有价、实际订不到</b>，其中 2 个原本是 🥇 首选。第 07 节的「实测」列就是为这件事存在的。',
  '🔴 <b>Booking 的房价行是「每间每晚」，不是「两间总价」</b>。我一开始记错了，导致所有酒店的 ¥/房 少算一半。三条独立证据：<code>no_rooms=1</code> 与 <code>no_rooms=2</code> 抓回的数字完全一样；截图里明写 "1 room / We have 1 left"；Árnanes 的 "Select Rooms" 下拉框写着 1→€276 / 2→€553。',
  '🔴 <b>冰岛酒店报价不含税</b>：页面小字写 "Excluded: 11 % VAT, ISK 800 / €6 City tax per night"。真实支出比标价高 11%+。',
  '🔴 <b>2026-09-02 新发现的自我修正：挪威酒店的 Booking 房价行也不含税</b> —— 每一行都写着 "Excluded: 12 % VAT"。我之前说过「挪威的价是含税的」，<b>那句只对 Airbnb 成立，对 Booking 上的挪威酒店是错的</b>。第 07 节所有挪威酒店/公寓的 ¥ 都已 ×1.12 重算（例：Thon Polar €153/间/晚 → 实际 ¥1,371/房而不是 ¥1,224）。Airbnb 仍然是全含（东侧那套明写 "Prices include all fees"）。',
  '<b>剩余间数要单独看</b>：一家酒店「有房」不等于「有 2 间」。Fosshotel Glacier Lagoon 和 Boutique Hotel Anna 都是 "We have 1 left" —— 凑第 2 间就跳到更贵的房型，直接顶破预算。',
  'Airbnb 不锁经纬度框就会把「Vík」搜成 2.5 小时外的 Selfoss，返回一堆看起来合格实际开不到的房源。',
  'DiscoverCars 首页表单点日历点不动（react-date-range），日期没生效 → 拿到的是默认 9/04–9/12 的价，看起来正常其实全错。<b>每次都要回读页面上的日期。</b>'
];

/* ================================================================
 * 需要人拍板的问题 —— 附出处 file:line
 * ================================================================ */
const BLOCKERS = [
  {id:'B1', kind:'block', sev:'green',
   q:'~~✈️ 10/2 那天 Widerøe 直飞有班吗？4 人票价多少？~~ → 🆕 **2026-09-04 已解除：WF816 Leknes 15:40 → 特罗姆瑟 16:35**',
   blocks:'（原来阻塞「10/2 坐飞机别开车」成不成立）→ 现在只剩一件事：**只剩 6 张票，我们要 4 张，得马上订**',
   detail:'🆕 <b>Steve 2026-09-04 在携程上查到了实班</b>（截图 <span class="mono">notes/shots/flight-WF816-lkn-tos-1002-ctrip.jpg</span>）：'+
     '<b>WF816 · LKN 15:40 → TOS 16:35 · 周五 10/2 · Widerøe Dash-8 · 直飞 55 min</b>。三档票价：'+
     '<b>¥1,274 不含托运也不含手提</b>（只给 1 件个人物品，13 天的箱子装不下）· '+
     '<b>¥1,490 含 1×23kg 托运 + 1 件手提</b>（👈 总账按这档算）· ¥2,065 免费退改。'+
     '4 人 = <b>¥5,960</b>（旧账按 ¥5,360 估，只多 ¥600）。'+
     '<b>关键差别：从 Leknes 起飞，不是 Svolvær；下午 15:40，不是早上 09:05</b> —— '+
     '所以车① 的还车点从 Svolvær 换成 Leknes、还车时间从 08:30 推到 14:30（3 个计费日，$647）；'+
     '车② 的取车从 10:30 推到 17:30（$224，比早取还便宜）。'+
     '<br><br>原来查不到是因为：wideroe.no 有 Cloudflare 反爬，而 <b>Widerøe 根本不给 Google Flights 供货</b>'+
     '（4 个不同日期查 SVJ/LKN 全零结果，同工具查 BOO→TOS 却正常）→ <b>"查不到"是没供货，不是没开售</b>。'+
     '这条教训值得留着：<b>OTA（携程/Expedia 这类）能看到 Google Flights 看不到的支线航空</b>。',
   ifUnknown:'已经不是「不知道」了。现在唯一的风险是<b>票卖光</b>：页面写着<b>剩 6 张</b>，我们要 4 张。'+
     '订不到这班 → 要么退回一台车连开 6 天（480 km / 6h30），要么查 SVJ→TOS 的班（Svolvær 离住处只要 26 min，异地费也差不多）。',
   who:'Steve / Kevin —— <b>现在就订，4 张 ¥1,490 那档（含 23kg 托运）</b>',
   days:['D6','D8'],
   src:[['notes/shots/flight-WF816-lkn-tos-1002-ctrip.jpg','携程截图（实班证据）'],
        ['notes/_research/out_lkn/','按这班重报的 4 组车价'],
        ['notes/_research/log_flyproxy.txt','当初 Google Flights 零结果的证据']],
   nowdo:'① <b>订机票 4 张（¥1,490 档）</b> —— 只剩 6 张。② 同时订车①（EVE→Leknes 3 天 $647，只有 5 个车源）。③ 车② 记得把取车时间改成 17:30。'},

  {id:'B1b', kind:'block', sev:'green',
   q:'~~Kevin 订的 KEF→OSL 9/29 航班是几点起飞？~~ → 已不再阻塞',
   blocks:'（原来阻塞 9/29 斯奈山做不做）',
   detail:'9/29 已按「丢一些景点别那么累」改成<b>雷克雅内斯半岛轻档</b>：纯开车约 2h，所有点都在 KEF 15–50 分钟圈内，08:30 出发、16:00 前就能回 KEF 还车。<b>于是原来那个"唯一硬前提"消失了</b> —— 傍晚 18:35 还是 20:05 都装得下。',
   ifUnknown:'只有想升级成"斯奈山南半段"中档（开车 ~5h、08:00→16:30）时，才需要 18:00 之后的班。草帽山 Kirkjufell 单程 4h/275 km，已经丢掉。',
   who:'—（想跑中档时再问 Kevin）',
   days:['D5'],
   src:[['notes/CHANGES-0929-1002.md','一、9/29 三档']],
   nowdo:'什么都不用等。轻档随便哪班都行。'},

  {id:'B2', kind:'block', sev:'red',
   q:'Kevin 的 Oslo→北京 是 10/6 还是 10/7 起飞？',
   blocks:'要不要第 13 晚（10/6 在奥斯陆）—— 本方案的总账只算了 12 晚',
   detail:'游轮 pass 掉之后，行程需要的是 <b>9/24 到 10/5 共 12 晚</b>。🆕 <b>10/5 那晚已经改成飞回奥斯陆、住 Stange 的森林小屋</b> —— 所以 10/6 上午是从 Stange 开 30 min 到 OSL 还车、直接接洲际，<b>不再有「当天先飞 TOS→OSL 再转」的接驳风险</b>（这也是 B2 从红降到黄的原因）。如果是 10/7 才飞，就要在奥斯陆一带多住一晚。',
   ifUnknown:'第 13 晚<b>最省事的做法是把 Stange 那套小屋多住一晚（+€306，可退）+ OSL 那台车顺延一天（+$79）</b>；不想留在森林里就换 Thon/Clarion Gardermoen（可退）。<b>地图上 D12 已经按「占位」画出来了，钱没计入总账。</b>反过来说：如果 Kevin 定的是 <b>10/7</b>，那 10/5 这个缓冲夜就多余了 —— 那时候<b>特罗姆瑟住回 4 晚（多一个极光夜）反而更好</b>，值得重新比一次。',
   who:'Kevin',
   days:['D12'],
   src:[['notes/PLAN-final.md','233（§七 第 2 条）'],
        ['notes/PLAN-final.md','220（§六 第 8 项：Nannestad 等机票确认后再订）']],
   nowdo:'先把 D12 当占位（Thon Gardermoen 可退到 9/23）。Kevin 一回信，要么删掉、要么点一下就订。'},

  {id:'B3', kind:'block', sev:'amber',
   q:'冰岛租车的保险包（SCDW + 砂石 + 火山沙尘 + 2026 道路税）实际多少钱？',
   blocks:'总账里唯一还会往上顶的一项：$258 → 约 $400–480',
   detail:'$258 是<b>裸车价</b>。冰岛这三个附加险不是推销：1 号环岛碎石路段多、10 月南岸沙尘暴是真实索赔项，而信用卡自带的 CDW 基本把这两项写进排除条款，还要先自己垫付再报销。',
   ifUnknown:'按最坏 $480 算，折 <b>¥3,408（¥682/天）</b> —— 仍然远低于你 ¥2,000/天 的上限，所以<b>它不会改变任何决定</b>，只影响总数约 ±¥1,600。',
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
   nowdo:'现在看一眼卡的可用额度就行。不够就换卡，或者订价格接近、押金更低的一家。'},

  {id:'B5', kind:'block', sev:'red',
   q:'🆕 10/5 那套小屋在 Stange 森林里 —— 要加租 OSL 一天的车，还是换机场旁的酒店？',
   blocks:'10/5 那一晚到底怎么落地：租第四台车（+$79–86），还是把住宿换成机场酒店（€193）',
   detail:'你给的 10/5 链接（Konglehytta 3）<b>搜索时输的是 "Oslo Gardermoen Airport OSL"，但房子并不在机场旁</b> —— 房源页自己写着 <b>"A car is required — Konglehytta 3 is located in Mjøsli, about 30 minutes from Gardermoen and 1 hour from Oslo"</b>，最近的超市 Kiwi Minnesund 也要开 15 分钟。而挪威那台车② 是 <b>10/5 在特罗姆瑟机场还掉</b>的，落地奥斯陆时手上没车。我实抓了 OSL 10/5 15:00 → 10/6 10:00 的报价：<b>23 个车源，自动挡 $79 起、自动四驱 $86 ≈ ¥611</b>。',
   ifUnknown:'两条路都能走通，差别是钱和舒适度：<b>A 租车</b> = 小屋 €306 + 车 $86 ≈ ¥2,448+¥611 = <b>¥3,059</b>，换来整栋小屋 + 私人桑拿 + ★4.98，代价是<b>只有 1 个卫生间</b>，而且第二天要赶洲际航班；<b>B 换酒店</b> = Clarion Oslo Airport <b>€193（2 间）≈ ¥1,544</b>，<b>更便宜、2 个卫生间、走去航站楼不用车</b>，但就是个机场酒店。⚠️ Clarion 那个价我只在 10/6 的窗口验过，10/5 要重查。',
   who:'Steve 决定（我不替你挑）',
   days:['D11','D12'],
   src:[['notes/_research/out_steve4/konglehytta.json','房源页原文 "A car is required"'],
        ['notes/_research/out_dc4/osl-1day.json','OSL 一天车 23 个实抓报价']],
   nowdo:'先决定 A 还是 B。选 A 就把小屋和 OSL 那台车一起订（小屋选可退那档，只贵 €10）；选 B 就先去 Booking 核 10/5 的 Clarion 实价。'}
];

/* 只影响某一项的细节 —— 不定也能先订（都可免费取消） */
const DETAILS = [
  {q:'Hörgsland 的三个卧室都没有双人床（上下铺×2 + 单人×2），那对夫妻能接受吗？', why:'不能接受就换 Klaustur 的 Fosshotel Núpar / Hótel Laki / Magma；或改回我原来的 Hotel Hvolsvöllur（Double 房）',
   who:'下单时备注', src:[['notes/PLAN-final.md','124–126']]},
  {q:'D3（9/27）蓝冰洞换不换成 Katla 冰洞？', why:'天然蓝冰洞一般 11 月才开。<b>换了也不动住宿</b>（Höfn 方案不受影响）—— 这条已经从「卡住行程」降级成「细节」',
   who:'Kevin 找票', src:[['notes/PLAN-final.md','233 附近'],['viz/data.js','D3.watch']]},
  {q:'冰岛第二驾驶员免不免费？', why:'长途开车日多（9/28 是 6h30），能换人开更安全。各家政策差很多',
   who:'租车官网', src:[['notes/OPTIONS-cars.md','182–183']]},
  {q:'挪威租车是否含 AutoPASS 标签，手续费怎么收？', why:'E10 + 特罗姆瑟这段收费站很少，金额很小 —— 知道就行，不影响选择',
   who:'租车公司', src:[['notes/OPTIONS-cars.md','184 + 116']]},
  {q:'特罗姆瑟那套 4 房的自助 check-in 流程 + 停车位', why:'10/2 中午就到（已改飞），但钥匙怎么拿、车停哪还是要问',
   who:'订完后给房东留言', src:[['notes/PLAN-final.md','60–65']]},
  {q:'Torghatten Nord 官网核 10/5 Brensholmen–Botnhamn 确切班次', why:'低季会改点。已确认 2026 全年运营、10/5 周一不受「周五停」影响',
   who:'出发前一周', src:[['notes/PLAN-final.md','202–206']]},
  {q:'Hörgsland 木屋有没有热水浴缸 / 需不需要预约', why:'纯舒适度（这一带的木屋多半有）。备选 Hotel Hvolsvöllur 页面明写含早 + hot tub',
   who:'到店问', src:[['notes/PLAN-final.md','246（截图 03b）']]}
];

/* 已经拍板 / 已经查实 —— 别再重新讨论一遍 */
const SETTLED = [
  {q:'游轮那段坐不坐？', a:'<b>整段 pass 掉</b>（Steve 定的）。10/2 先改自驾、再按「10/2 坐飞机别开车」改成 SVJ→TOS 飞 50 min，那一晚并进特罗姆瑟。<b>顺带消掉了整个行程唯一的单点故障</b>（Havila 的价拿不到、舱位可能卖光），还省下约 ¥12,000。',
   src:[['notes/PLAN-final.md','60–63'],['notes/OPTIONS-cruise.md','整份文档已作废']]},
  {q:'住 Airbnb 还是酒店？', a:'<b>非常 prefer Airbnb</b>（Steve 明确说的）。已执行：12 晚里 <b>10 晚是 Airbnb 整套房</b>，只有 9/26、9/27 两晚因为冰岛乡下确实没有可订的整套 Airbnb（Klaustur–Höfn 一带搜索返回 0，2 卫和 1 卫都试过），才走 Booking 上的<b>整栋木屋 / guesthouse</b> —— 它们也是整栋带厨房，不是酒店房。',
   src:[['notes/PLAN-final.md','39–40'],['notes/OPTIONS-stay.md','98–101（南岸 4 个 Airbnb 全部订不到）']]},
  {q:'罗弗敦东侧还是西侧？', a:'<b>东侧（Svolvær / Vågan）</b> —— 交给我决定的，答案在上面「两个决定」那一节。核心理由是 10/2 车程 6h30 vs 8h30，其次是可退，省钱只是附带。',
   src:[['notes/PLAN-final.md','72–108']]},
  {q:'冰河湖那晚住哪？', a:'🆕 <b>Höfn 西的 Guesthouse Birkifell 整栋</b>（Steve 自己找的，已替掉我原来的 Árnanes —— 便宜 €61、整栋带厨房、有双人床、免费退 + 到店付）。冰河湖旁的 Fosshotel 只剩 1 间房，凑 2 间 ¥4,776/房超预算，<b>是被算术排除的</b>。',
   src:[['notes/PLAN-final.md','110–138']]},
  {q:'几个人、怎么分房、¥/房怎么算？', a:'<b>4 人 = 两男 + 一对夫妻。</b>¥/房 = 总价 ÷ <b>实际用的房间数</b>。本页一律<b>保守按 ÷2</b> 算；3 房那几晚如果两个男生各住一间（÷3），数字还要再低三分之一。',
   src:[['notes/PLAN-final.md','10 + 54']]},
  {q:'预算够不够？', a:'<b>够，而且 2026-09-02 深夜那两个链接之后又便宜了。</b>你这套方案折 <b>¥1,711/房/晚</b>（上两版 ¥1,876 → ¥1,790），仍在 ¥2,000–4,000 区间的下沿（我原来那套 ¥1,326 —— 两套都在预算内）。四台车（冰岛 · 挪威① · 挪威② · 🆕 OSL 1 天）折下来 ¥609–682/天，都远低于 ¥2,000/天的上限。',
   src:[['notes/PLAN-final.md','20–26']]},
  {q:'免费取消 vs 更便宜的不可退？', a:'<b>全部买可免费取消</b>。9 项里 <b>7 项零风险</b>，唯一例外是 Nannestad 两晚（€520），已给可退替代（Thon Gardermoen）。',
   src:[['notes/PLAN-final.md','222–224']]},
  {q:'挪威租车拆两段还是一台车连开？', a:'🆕 <b>2026-09-02 下午改成拆两段</b> —— 不是为了省钱（拆开其实<b>更贵</b>），而是因为 Steve 要「10/2 坐飞机别开车」。车① EVE 9/30→Svolvær 10/2 08:30（2 天 $650）+ 车② 特罗姆瑟 10/2→10/6（4 天 $343）= <b>$993</b>，vs 一台车连开 6 天 <b>$762</b> → <b>多付 $231</b> 换掉那 480 km / 6h30。代价还包括两次柜台、两次押金冻结，以及 Svolvær 还车<b>只有 6 个车源</b>。<br>（在<b>没有</b>飞这个前提时，结论仍然是一台车连开：早先算过的「拆开省 $107」是<b>拿电车比燃油车</b>算错了，同档对齐后拆开<b>贵 $28</b>。）',
   src:[['notes/CHANGES-0929-1002.md','二'],['notes/OPTIONS-cars-split.md','同档对齐表']]},
  {q:'驾照国别 / 要不要国际驾照 IDP？', a:'<b>美国驾照，冰岛和挪威都直接认，不需要 IDP。</b>',
   src:[['notes/PLAN-final.md','185']]},
  {q:'9 月底冰岛要不要冬胎？', a:'<b>不需要</b> —— 法律 11/1 起才强制。',
   src:[['notes/OPTIONS-cars.md','189']]}
];


/* ================================================================
 * 租车决策的证据表 —— 2026-09-02 实价，全部「4x4 + 自动挡 + 可免费取消 + 不限里程 + 美国驾照 + 35 岁」
 * 🔴 关键方法：同一行里只比**同一档动力**（燃油/混动 vs 纯电分开列），
 *    否则会拿电车的价去比燃油车的价 —— 这正是之前「拆开省 $107」算错的原因。
 * 原始 JSON: notes/_research/out_split/ + out_verify/ · job: jobs_split.json + jobs_verify.json
 * ================================================================ */

/* 冰岛：Steve 提的「同地 4 天 + 最后 1 天异地」到底划不划算 */
const EVID_IS = [
  {id:'A', route:'KEF → KEF', when:'9/25 14:00 → 9/29 18:00', days:'5', fuel:323, n:17,
   verdict:'', note:'14:00 取 → 跨进第 5 个计费日'},
  {id:'V1', route:'KEF → KEF', when:'9/25 <b>17:00</b> → 9/29 18:00', days:'4', fuel:258, n:15,
   verdict:'best', note:'🥇 <b>采纳这个</b>。同样是落地就取，只因为晚 3 小时取车就少一个计费日'},
  {id:'E', route:'KEF → KEF', when:'9/26 09:00 → 9/29 18:00', days:'4', fuel:253, n:16,
   verdict:'', note:'原方案。车价最低，但 9/25 要坐大巴进城、9/26 再坐回来（4 人 ×2 程 ≈ ¥1,360）'},
  {id:'B1', route:'雷市市区 → 雷市市区', when:'9/25 16:00 → 9/28 18:00', days:'4', fuel:251, n:15,
   verdict:'bad', note:'Steve 方案第 1 步'},
  {id:'B2', route:'雷市市区 → <b>KEF</b>', when:'9/29 08:00 → 9/29 18:00', days:'1', fuel:175, n:24,
   verdict:'bad', note:'Steve 方案第 2 步。单租 1 天 $175，而连续租的边际第 5 天只要 $70'},
  {id:'C', route:'雷市市区 → KEF', when:'9/26 09:00 → 9/29 18:00', days:'4', fuel:359, n:22,
   verdict:'', note:'单租约、市区取 + KEF 还'},
  {id:'D', route:'雷市市区 → KEF', when:'9/25 16:00 → 9/29 18:00', days:'5', fuel:437, n:21,
   verdict:'', note:'最贵的组合'}
];

/* 挪威：一台车连开 6 天 vs 拆两段（同档动力对齐后重算）
 * 🆕 2026-09-02 下午：Steve 要 10/2 坐飞机 → F1+F3 这一组成为采纳方案 */
const EVID_NO = [
  {id:'F1', route:'EVE → <b>Svolvær(SVJ)</b>', when:'9/30 11:00 → <b>10/2 09:00</b>', days:'2', fuel:650, ev:null, n:6,
   verdict:'best', note:'🥇 <b>飞的方案 · 车①</b>（Toyota Yaris Cross 4WD）。09:00 前还车才算 2 天。⚠️ 只有 6 个车源'},
  {id:'F2', route:'EVE → Svolvær(SVJ)', when:'9/30 11:00 → 10/2 <b>14:30</b>', days:'3', fuel:763, ev:645, n:6,
   verdict:'', note:'下午班（~15:45 起飞）→ 跨进第 3 个计费日，白贵 $113'},
  {id:'F3', route:'TOS → TOS', when:'10/2 10:30 → **10/5 10:00**', days:'3', fuel:240, ev:null, n:16,
   verdict:'best', note:'🥇 <b>飞的方案 · 车②</b>（自动四驱）。🆕 <b>2026-09-02 深夜从 4 天缩到 3 天</b>（10/5 就飞奥斯陆了）→ $343 → 约 <b>$240</b>，省 $103。实抓 16 个报价，最便宜的自动四驱 $236–243'},
  {id:'F5', route:'OSL → OSL', when:'🆕 10/5 15:00 → 10/6 10:00', days:'1', fuel:79, ev:84, n:23,
   verdict:'best', note:'🆕 <b>新加的车③</b> —— 10/5 那个小屋在 Stange，房源页写着 "A car is required"（离 OSL 30 min）。自动挡 <b>$79</b> 起、自动四驱 $86。<b>不租车就换机场旁的 Clarion（€193，还更便宜、2 个卫生间）</b>'},
  {id:'F4', route:'EVE → EVE（同地）', when:'9/30 11:00 → 10/2 09:00', days:'2', fuel:254, ev:null, n:23,
   verdict:'bad', note:'车费最香（+F3 只 $597，比连开 6 天还省 $165）但<b>没航班</b>：EVE→TOS 直飞每月仅 4 班，Google 上全经奥斯陆倒 1,200 km / 4–6h / NOK 7,768 起'},
  {id:'V2', route:'EVE → TOS', when:'9/30 11:00 → 10/6 10:00', days:'6', fuel:762, ev:569, n:24,
   verdict:'', note:'⬅️ <b>基线：一台车连开 6 天</b>（Suzuki Vitara 燃油 4WD 自动）。不飞就用这个 —— F1+F3 = $993，比它贵 $231'},
  {id:'V3', route:'EVE → TOS', when:'9/30 11:00 → 10/2 20:00', days:'3', fuel:568, ev:440, n:24,
   verdict:'', note:'拆开的第 1 段'},
  {id:'V4', route:'TOS → TOS', when:'10/4 09:00 → 10/6 09:00', days:'2', fuel:222, ev:172, n:24,
   verdict:'', note:'拆开的第 2 段（而且 10/3 那天没车）'},
  {id:'—', route:'EVE → <b>Svolvær</b>', when:'9/30 11:00 → 10/2 17:00', days:'3', fuel:941, ev:644, n:6,
   verdict:'bad', note:'⛔ 原方案（走游轮时）。<b>只有 6 个车源</b>，含 ~$320 异地费'},
  {id:'—', route:'EVE → EVE（同地）', when:'9/30 11:00 → 10/2 17:00', days:'3', fuel:null, ev:167, n:23,
   verdict:'', note:'同地还最便宜，但把车还回 EVE 就离特罗姆瑟 ~480 km 没车了 —— 几何上不成立'}
];

/* 两条被实测推翻的旧说法 */
const CARFIX = [
  {was:'冰岛「雷市取 / KEF 还」异地费 <b>~€50</b>（grounded search，写在 OPTIONS-cars.md:191）',
   now:'实测 <b>$106–114（约 €100）</b>，偏低了一半。C−E=+$106、D−A=+$114',
   why:'即便如此 $110 还是<b>比拆一次租约便宜</b>：单租 1 天 $175 vs 连续租边际 1 天 $70 → 拆开花 $105 省 $110，净省 $5，不值得'},
  {was:'挪威「拆两段省 <b>$107</b>」（EVE→TOS 3 天 $440 + 特罗姆瑟 3 天 $215 = $655 vs $762）',
   now:'❌ <b>算错了 —— 那是拿纯电的价去比燃油车的价。</b>同档（燃油 4WD 自动）重算：<b>$568 + $222 = $790 vs 一台车 $762 → 拆开反而贵 $28</b>',
   why:'结论没变（不拆），但理由更强：拆开<b>既更贵又更麻烦</b>，而且中间 10/3 那天没车。原来的「省 $107 但不值」其实根本没省'}
];

/* ================================================================
 *  每晚候选池 —— 「一起选」用的那张表
 *  2026-09-02 全部重抓：23 个 Airbnb 房源页 + 10 家 Booking 物业页。
 *
 *  v（实测状态）三档，这是全表最重要的一列：
 *    'ok'     房源页/房型页已核 —— 用我们的真实日期打开过，确认能订
 *    'search' 只有搜索页/旧抓的价 —— 能不能订**没验证过**
 *    'dead'   已验证订不到（留着是为了别再回头看）
 *
 *  cny  = 这个住宿块（整段晚数）的 4 人总价，¥，**税费已按国别补齐**
 *  room = ¥/房/晚。整套房源一律按保守的 ÷2 房；酒店 = 每间每晚 × 2 间。
 *  🔴 挪威 Booking 房型行写着 "Excluded: 12 % VAT" → 本表挪威酒店价**已 ×1.12**。
 *     冰岛是 11% VAT + €6/间/晚城市税，也已加。Airbnb 全含（页面明写含所有费用）。
 * ================================================================ */
const A = (id,ci,co) => `https://www.airbnb.com/rooms/${id}?check_in=${ci}&check_out=${co}&adults=4&currency=EUR`;
const B = (slug,ci,co,rooms) => `https://www.booking.com/hotel/${slug}.html?checkin=${ci}&checkout=${co}&group_adults=4&no_rooms=${rooms||2}&selected_currency=EUR`;

const CANDS = [
{ g:'G1', d:'9/24 → 9/25（周四入住）', n:1, place:'Oslo Gardermoen（落地就睡）', note:'当晚 21:30 落地，只求近 + 有 2 卫。三个 3–4 房的 Airbnb 全部实测 min-stay 2 晚 → 订不了。',
  opts:[
  {t:'pick', n:'Modern. Quiet area. Large space. · Nannestad', u:A('1616864516592253636','2026-09-24','2026-09-25'), loc:'Nannestad，OSL 车程 20 min', rb:'3房/5床/2卫', p:'€260 / 1晚', cny:2080, room:1040, r:'—', cxl:'⛔ 不可退', v:'ok', why:'唯一能只订 1 晚的 3房2卫，价格碾压。代价是不可退（€260 敞口）'},
  {t:'alt',  n:'Thon Hotel Gardermoen ×2 间', u:B('no/thon-gardermoen','2026-09-24','2026-09-25'), loc:'机场旁，有班车', rb:'2房/2卫', p:'€86–140/间（+12% VAT）', cny:1541, room:771, r:'—', cxl:'✅ 退到 9/23', v:'search', why:'最便宜的**可退**方案，也是「机票没定就别买不可退」的解。¥ 按下沿 €86 算，实际会在 771–1,254 之间'},
  {t:'alt',  n:'Clarion Hotel Oslo Airport ×2 间', u:B('no/clarion-oslo-airport','2026-09-24','2026-09-25'), loc:'机场旁', rb:'2房/2卫', p:'€108–126/间（+12% VAT）', cny:1935, room:968, r:'—', cxl:'✅ 退到 9/23', v:'search', why:'比 Thon 贵一点，房间新一些；同样可退'},
  {t:'dead', n:'A cozy house near Gardermoen · Eidsvoll', u:A('1517311976763731826','2026-09-24','2026-09-25'), loc:'Eidsvoll', rb:'3房/4床/2卫', p:'€426 / 2晚', cny:0, room:0, r:'5.0', cxl:'—', v:'dead', why:'⛔ 房源页明写 **Minimum stay is 2 nights** → 我们只住 1 晚'},
  {t:'dead', n:'Central Jessheim - 10 min from OSL', u:A('1739223395983398156','2026-09-24','2026-09-25'), loc:'Ullensaker', rb:'4房/5床/2卫', p:'€759 / 2晚', cny:0, room:0, r:'5.0', cxl:'—', v:'dead', why:'⛔ 同样 min-stay 2 晚'},
  {t:'dead', n:'Semi-detached house · Gjerdrum', u:A('955510432915478016','2026-09-24','2026-09-25'), loc:'Gjerdrum', rb:'2房/2床/2卫', p:'€503 / 2晚', cny:0, room:0, r:'5.0', cxl:'—', v:'dead', why:'⛔ 同样 min-stay 2 晚'}]},

{ g:'G2', d:'9/25 → 9/26（周五入住）', n:1, place:'雷克雅未克', note:'🔴 这一晚是本轮最大的修正：之前列在候选池里的两个（Huge Apartment ★4.87、Tower Sóley ★4.9）**打开房源页发现都订不到**。',
  opts:[
  {t:'pick', n:'Aurora view 3BR 2BATH Luxury down town', u:A('1729852848905770040','2026-09-25','2026-09-26'), loc:'雷市市中心，走路吃饭', rb:'3房/3床/2卫', p:'€647→€447 / 1晚', cny:3576, room:1788, r:'5.0', cxl:'✅ 24h 内免费 · 9/18 前部分退', v:'ok', why:'€647 打到 €447，★5.0，市中心。抓到的最大折扣之一'},
  {t:'alt',  n:'3BR 2BA · Garðabær', u:A('1329176066208833432','2026-09-25','2026-09-26'), loc:'Garðabær，市区南 15 min', rb:'3房/2卫', p:'€337 / 1晚', cny:2696, room:1348, r:'—', cxl:'—', v:'search', why:'**最便宜**，但只有搜索页的价 —— 这一晚已经有两个搜索页骗过我们，订前必须先开房源页'},
  {t:'alt',  n:'Mani Apartments - Four Bedroom', u:A('639631862185278229','2026-09-25','2026-09-26'), loc:'雷市', rb:'4房/9床/3卫', p:'€962 flex / €961 非退', cny:7696, room:3848, r:'4.51', cxl:'✅ 24h 内免费', v:'ok', why:'实测能订、**3 个卫生间 + 9 张床**，但 ¥3,848/房已到预算上沿，评分也只有 4.51'},
  {t:'dead', n:'Huge Apartment - Best Location', u:A('1164355089969462702','2026-09-25','2026-09-26'), loc:'雷市市中心', rb:'4房/6床/2卫', p:'€535（搜索页）', cny:0, room:0, r:'4.87', cxl:'—', v:'dead', why:'⛔ **2026-09-02 实测：Those dates are not available。** 搜索页仍在报 €535 —— 这就是不能照搜索卡片下单的原因'},
  {t:'dead', n:'Tower Apartments - Sóley', u:A('35826875','2026-09-25','2026-09-26'), loc:'雷市', rb:'2房/3床/2卫', p:'€677（搜索页）', cny:0, room:0, r:'4.9', cxl:'—', v:'dead', why:'⛔ 同样 **日期不可用**（本轮新发现）'}]},

{ g:'G3', d:'9/26 → 9/27（周六入住）', n:1, place:'Klaustur 东 / 南岸', note:'全程供给最紧的一晚。**Airbnb 在 Klaustur–Höfn 一带 2房2卫、1房也算，全部返回 0** → 这一晚只有酒店/木屋。🆕 默认已换成 Steve 找的 Hörgsland（住处往东挪，把 9/27 从 390 km 压到 200 km）。',
  opts:[
  {t:'pick', n:'🆕 Hörgsland Cottages · Three-Bedroom Vacation Home（整栋）', u:B('is/horgsland-cottages','2026-09-26','2026-09-27',1), loc:'Klaustur 东 10 km · 往东挪 → 9/27 省 190 km', rb:'3 卧 · 整栋 · 私厨私卫', p:'€448 + 11% 税 = €503', cny:4024, room:2012, r:'—', cxl:'⛔ 不可退（€489→€549 档可退到 9/12）', v:'ok', why:'**Steve 自己选的，已设为默认。** 整栋 538 ft²、私人厨房、含车位、"We have 5 left"。🟠 床型是上下铺×2 + 单人床×2 —— **没有双人床**，夫妻要注意'},
  {t:'alt',  n:'Stracta Apartments Kirkjubæjarklaustur（住 2 晚那个方案）', u:B('is/stracta-apartments','2026-09-26','2026-09-28',1), loc:'Klaustur 镇上 · 9/26+9/27 都住这儿', rb:'公寓', p:'€1,349 / 2 晚含税', cny:10792, room:2698, r:'—', cxl:'—', v:'ok', why:'「两晚不搬箱子」的那个方案。比 Hörgsland+Birkifell 贵 **€281 ≈ ¥2,250**，而且要放弃 Stokksnes（从 Klaustur 单程 215 km）'},
  {t:'alt',  n:'Hotel Hvolsvöllur ×2 Double/Twin（我原来的默认）', u:B('is/hvolvollur','2026-09-26','2026-09-27'), loc:'Hvolsvöllur，正在两个瀑布中间', rb:'2房/2卫', p:'€326 + 税 = €374', cny:2992, room:1496, r:'—', cxl:'✅ 退到 9/24 · **到店付**', v:'ok', why:'便宜 €129、可退、到店付、含早 + hot tub。代价：位置偏西 → **9/27 变成 390 km / 4h30 的硬仗**'},
  {t:'alt',  n:'Hotel Katla ×2 间（Vík 镇内）', u:'https://www.booking.com/searchresults.html?ss=Hotel+Katla+Vik&checkin=2026-09-26&checkout=2026-09-27&group_adults=4&no_rooms=2&selected_currency=EUR', loc:'Vík 镇内，省次日 1h15 回头路', rb:'2房/2卫', p:'€615–683/间 + 税', cny:11016, room:5508, r:'—', cxl:'—', v:'search', why:'🔴 **超预算 ¥5,508/房**。唯一价值是「住在 Vík 就不用第二天往东多开 1h15」—— 为了这 1h15 多花 ¥8,000，我不建议'},
  {t:'dead', n:'Hlíðarból Guest House', u:A('1554437248972293986','2026-09-26','2026-09-27'), loc:'Hvolsvöllur', rb:'5房/2卫', p:'€750（搜索页）', cny:0, room:0, r:'4.64', cxl:'—', v:'dead', why:'⛔ 房源页 **日期不可用**（截图 x2）。原本是这一晚的 🥇'},
  {t:'dead', n:'4BR/2BA · Hvolsvöllur', u:A('1081195144537663933','2026-09-26','2026-09-27'), loc:'Hvolsvöllur', rb:'4房/4床/2卫', p:'€2,089 / 2晚', cny:0, room:0, r:'4.8', cxl:'—', v:'dead', why:'⛔ 实测 **min-stay 2 晚**，而且 ¥4,178/房本来就超预算'},
  {t:'dead', n:'Boutique Hotel Anna（Holt）', u:'https://www.booking.com/searchresults.html?ss=Boutique+Hotel+Anna+Iceland&checkin=2026-09-26&checkout=2026-09-27&group_adults=4&no_rooms=2&selected_currency=EUR', loc:'Holt', rb:'4 人套房', p:'€664', cny:0, room:0, r:'—', cxl:'—', v:'dead', why:'⛔ Double/Twin 只剩 1 间；4 人套房便宜但**只有 1 个卫生间**（等于两个男生睡客厅）'}]},

{ g:'G4', d:'9/27 → 9/28（周日入住）', n:1, place:'冰河湖一带（Höfn）', note:'Airbnb 在 Höfn–Jökulsárlón–Skaftafell 一带返回 **0 个**（2卫和1卫都试过）→ 这一晚只有酒店/整栋 guesthouse。🆕 默认已换成 Steve 找的 Birkifell。',
  opts:[
  {t:'pick', n:'🆕 Guesthouse Birkifell · Two-Bedroom House（整栋）', u:B('is/guesthouse-birkifell','2026-09-27','2026-09-28',1), loc:'Nesjahverfi · Höfn 西 10 km · Stokksnes ~25 min', rb:'2 卧 · 整栋 · 厨房 + 私卫', p:'€504 + 11% 税 = €565', cny:4520, room:2260, r:'—', cxl:'✅ 免费退到 9/25 · **到店付**', v:'ok', why:'**Steve 自己选的，已设为默认，而且确实比我原来的 Árnanes 好**：便宜 €61、整栋带厨房（极光可以屋里等）、床型 1 queen + 2 单人（夫妻有双人床）、免费退 + 到店付。🔴 **只剩 1 套 → 排下单第 1 位**（零风险）'},
  {t:'alt',  n:'Árnanes Sveitagisting ×2 Double/Twin 私卫（我原来的默认）', u:B('is/arnanes-sveitagisting','2026-09-27','2026-09-28'), loc:'Höfn 西，离冰河湖 ~45 min', rb:'2房/2卫', p:'€553 + 税 = €626', cny:5008, room:2504, r:'—', cxl:'✅ 退到 9/20 · 9/18 前不付钱', v:'ok', why:'还有 4 间、含早、页面明写**可要相连的两间**。贵 €61 且是两间酒店房（没厨房）'},
  {t:'alt',  n:'Árnanes ×2 Triple 私卫', u:B('is/arnanes-sveitagisting','2026-09-27','2026-09-28'), loc:'同上', rb:'2房/2卫（3 人房）', p:'€770 + 税 ≈ €867', cny:6936, room:3468, r:'—', cxl:'✅ 退到 9/20', v:'ok', why:'同一家的大房型 —— 只有「想睡宽一点」才值得多 ¥1,900'},
  {t:'alt',  n:'Fosshotel Vatnajökull ×2 Mountain View', u:B('is/vatnajokull','2026-09-27','2026-09-28'), loc:'Höfn 镇，离冰河湖 ~55 min', rb:'2房/2卫', p:'€776 含税', cny:6208, room:3104, r:'—', cxl:'✅ 退到 **9/25**', v:'ok', why:'想住「正规连锁」而不是乡村 guesthouse 就选这个。退改期还更晚，只剩 2 间'},
  {t:'dead', n:'Fosshotel Glacier Lagoon（离湖 10 min）', u:'https://www.booking.com/searchresults.html?ss=Fosshotel+Glacier+Lagoon&checkin=2026-09-27&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR', loc:'冰河湖旁 10 min', rb:'需 2 间', p:'凑 2 间 €1,194 含税', cny:0, room:0, r:'—', cxl:'—', v:'dead', why:'⛔ Standard **只剩 1 间**（截图 x3），凑 2 间 = **¥4,776/房超预算**。是被算术排除的，不是被口味排除的'},
  {t:'dead', n:'Hótel Klaustur / Magma / Laki', u:'https://www.booking.com/searchresults.html?ss=Kirkjubaejarklaustur&checkin=2026-09-27&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR', loc:'Kirkjubæjarklaustur，更远', rb:'—', p:'€713–1,264', cny:0, room:0, r:'—', cxl:'—', v:'dead', why:'⛔ 多数只剩 1 间，而且离冰河湖更远'}]},

{ g:'G5', d:'9/28 → 9/29（周一入住）', n:1, place:'Reykjanesbær / Njarðvík（KEF 旁）', note:'✅ 这一晚**四个都实测能订**，是全程最没风险的一晚 —— 可以最后再订。🆕 默认已换成 Steve 第二次给的那套（更便宜、床型更好，但**只有 1 卫**）。',
  opts:[
  {t:'pick', n:'🆕 Holiday Home with Hot tub & Sauna · Ocean Break', u:A('1139944377459145061','2026-09-28','2026-09-29'), loc:'Njarðvík，**离 KEF 只 5 min**', rb:'3房/3床/**1卫**', p:'€531 → **€335**', cny:2680, room:1340, r:'5.0', cxl:'✅ 免费退到 9/23', v:'ok', why:'**Steve 自己选的，已设为默认。** 全程**最便宜的一晚**：★5.0、hot tub + 桑拿、床型正好（卧1 king 给夫妻，卧2/卧3 各一张单人）→ 一人一间。🟠 代价是**只有 1 个卫生间**，而次日要出发跑 Reykjanes'},
  {t:'alt',  n:'Cozy home in Njarðvík（Steve 的第一个链接）', u:A('1468029290775302593','2026-09-28','2026-09-29'), loc:'同区', rb:'4房/4床/2卫', p:'€445 flex（非退 €444，几乎不省）', cny:3560, room:1780, r:'4.54', cxl:'✅ 24h 内免费', v:'ok', why:'**用 €110 换回第 2 个卫生间**，4 卧一人一间。评分 4.54 是这一晚最低的'},
  {t:'alt',  n:'3BR/2BA ★4.92 · Reykjanesbær（我原来的默认）', u:A('1231709933827491677','2026-09-28','2026-09-29'), loc:'KEF 旁', rb:'3房/4床/2卫', p:'€424 / 1晚', cny:3392, room:1696, r:'4.92', cxl:'✅ 24h 内免费', v:'ok', why:'便宜 €21 且**评分 4.92 高得多**。这一晚两个都实测能订、都很稳 —— 看哪个房型顺眼即可'},
  {t:'alt',  n:'3BR/2BA ★4.91 · Reykjanesbær', u:A('1302095139759149342','2026-09-28','2026-09-29'), loc:'同区', rb:'3房/3床/2卫', p:'€498 / 1晚', cny:3984, room:1992, r:'4.91', cxl:'✅ 24h 内免费', v:'ok', why:'实测能订。比 🥇 贵 €74、床还少一张 —— 纯备胎'},
  ]},

{ g:'G6', d:'9/29 → 9/30（周二入住）', n:1, place:'Oslo Gardermoen（冰岛飞回来）', note:'和 9/24 同一批。唯一那个 2 晚起的 Airbnb 也实测 min-stay 2 → 灭。',
  opts:[
  {t:'pick', n:'🆕 Nannestad 5 房 / 5 床 / 1.5 卫', u:A('1461656866395092330','2026-09-29','2026-09-30'), loc:'Nannestad（OSL 旁）', rb:'5房/5床/**1.5卫**', p:'€292 / 1晚', cny:2336, room:1168, r:'—', cxl:'✅ 免费退到 9/28', v:'ok', why:'**Steve 自己选的，已设为默认。** 贵 €32 但**可以退**，而 9/29 这晚依赖 Kevin 的 KEF→OSL 航班 → 用 ¥256 买掉这个风险，值。🟠 代价：只有 1.5 卫'},
  {t:'alt',  n:'同 9/24 那套 · Nannestad 3房/2卫（我原来的默认）', u:A('1616864516592253636','2026-09-29','2026-09-30'), loc:'Nannestad', rb:'3房/5床/2卫', p:'€260 / 1晚', cny:2080, room:1040, r:'—', cxl:'⛔ 不可退', v:'ok', why:'便宜 €32 且是**真 2 卫**。代价：完全不可退，而这一晚正好是最需要弹性的一晚'},
  {t:'alt',  n:'Thon Hotel Gardermoen ×2 间', u:B('no/thon-gardermoen','2026-09-29','2026-09-30'), loc:'机场旁', rb:'2房/2卫', p:'€86–140/间（+12% VAT）', cny:1541, room:771, r:'—', cxl:'✅ 退到 9/28', v:'search', why:'可退，而且**可能比 Airbnb 还便宜**。9/29 是飞机日，住机场旁本身也更合理'},
  {t:'alt',  n:'Scandic Oslo Airport ×2 间', u:B('no/scandic-oslo-airport','2026-09-29','2026-09-30'), loc:'机场旁', rb:'2房/2卫', p:'€141–188/间（+12% VAT）', cny:2526, room:1263, r:'—', cxl:'✅ 退到 9/28', v:'search', why:'34 个房型行有货 = 最不会卖光的兜底'},
  {t:'dead', n:'4BR/2BA · Ullensaker', u:A('1204471771405405295','2026-09-29','2026-09-30'), loc:'Ullensaker', rb:'4房/4床/2卫', p:'€541 / 2晚', cny:0, room:0, r:'4.97', cxl:'—', v:'dead', why:'⛔ 实测 **min-stay 2 晚**'}]},

{ g:'G7', d:'9/30 → 10/2（2 晚）', n:2, place:'罗弗敦东侧（Vågan / Svolvær）', note:'✅ **这一晚已订**（Nordic Lodge Retreat）。所以下面这一整串**已经全部是 backup plan** —— 它们的用途只有一个：🔴 **9/23 是那张单子的部分退款悬崖**，要换必须在 9/23 之前决定。三个带「备用 A/B/C」标签的是我按用途排的（同款替身 / 最省钱 / 房子最好），其余按价格排。（3 个「实测订不到」列在最后。）东侧 = 10/2 只开 6h30；西侧 = 8h30。',
  opts:[
  {t:'pick', n:'✅ Nordic Lodge Retreat · Lyngvær ★4.92（Steve 已订）', u:A('1303545546783105490','2026-09-30','2026-10-02'), loc:'🟢 东侧 Lyngvær / Vågan · 10/2→飞', rb:'4房/8床/2卫', p:'€898 / 2晚（搜索页快照）', cny:7184, room:1796, r:'4.92', cxl:'✅ 24h 内免费 · 9/23 前部分退', v:'ok', why:'**已下单，这一段结束了。** 2025-01 新建 · 98 m² · 4 卧 8 床 **2 卫** · 按摩浴缸 + 桑拿 · Superhost · 38 评（房东 Svein Magnus）。⚠️ €898 是搜索页快照价，请以订单实付为准。🆕 **2026-09-03 复核：房源页现在对 9/30→10/2 显示 "Those dates are not available"** —— 这正是「已经被订走」该有的样子（我们自己订的），**不是**房源出问题。所以 9/2 那次判「订不到」是同一个现象，不用再追'},
  {t:'alt',  n:'🅰 备用 A · 同款替身 —— 🆕 Lyngvær Arctic Pearl Lodge ★5.0（Steve 9/3 给的）', u:A('1683936522638301457','2026-09-30','2026-10-02'), loc:'🟢 东侧 Lyngvær / Vågan · Svolvær 与机场 20 min · Henningsvær 12 min', rb:'3房/**页面只写 1 bed**/2卫 · 最多 7 人', p:'€1,223 / 2晚（房源页实价）', cny:9784, room:2446, r:'5.0', cxl:'✅ 24h 内免费 · 9/23 前部分退', v:'ok', why:'**和已订那套是同一条路上的邻居**（Lyngvær 的 lodge no. 17，房东 Oliver，Superhost 9 年）：103 m² 新 lodge · **私人桑拿 + jacuzzi** + 全屋地暖 + EV 充电 + 180° 海景 · Guest favorite ★5.0（6 评）· 路的尽头、最私密的一栋。**退改政策和已订那套一字不差**，所以真要换，换它最不折腾。代价两条：① 贵 **€325 ≈ ¥2,600**（¥2,446 vs ¥1,796 / 房 / 晚）；② 🔴 **房源页床位写的是「1 bed」、上限 7 人** —— 评论里明写 "three bedrooms and two separate bathrooms so our party of six had room"，所以床是有的、只是房东没填全，**但那对夫妻要双人床这件事必须订前问房东**。2026-09-03 用房源页实测：可订、有价、无 min-stay'},
  {t:'alt',  n:'🅱 备用 B · 最省钱 —— Waterfront Nordic house, Vågan ★4.93', u:A('1362321193877972891','2026-09-30','2026-10-02'), loc:'🟢 东侧 Vågan · EVE→2h30 · 10/2→6h30', rb:'5房/8床/2卫', p:'€602→€553 / 2晚', cny:4424, room:1106, r:'4.93', cxl:'✅ 24h 内免费 · 9/23 前部分退', v:'ok', why:'Guest favorite + Superhost + 页面明写含所有费用。**最便宜 + 能退 + 在东侧**，三样都占 —— 比已订那套便宜约 ¥2,760（€345）。它是我原来的默认，现在的角色是「万一要退，还能省钱的那个」'},
  {t:'alt',  n:'Vågan 3 房 / 5 床 / 2 卫（9/2 那一版的默认）', u:A('1258848712541940268','2026-09-30','2026-10-02'), loc:'🟢 东侧 Vågan', rb:'3房/5床/2卫', p:'€1,136 / 2晚', cny:9088, room:2272, r:'—', cxl:'⛔ 不可退', v:'ok', why:'9/2 那一版的默认，现在只是备用池里的一条。已被已订那套全面取代：贵 ¥1,904、少一间房、没有评分、而且**不可退** —— 一个不可退的备用意义不大'},
    {t:'alt',  n:'The heart of Ramberg ★4.76', u:A('1170849828585814519','2026-09-30','2026-10-02'), loc:'🟠 西侧 Ramberg · EVE→4h（黑天）· 10/2→8h30', rb:'4房/2.5卫', p:'€647 / 2晚', cny:5176, room:1294, r:'4.76', cxl:'⛔ **完全不可退**', v:'ok', why:'想睡在明信片那一侧就选它。代价：贵 €94 + 不可退 + 10/2 要开 8h30（E10 风暴封路很常见 → 最西头 + 不可退是最差组合）'},
  {t:'alt',  n:'Secluded house · Private swimming pool', u:A('1441200146734024595','2026-09-30','2026-10-02'), loc:'🟡 中部 Vestvågøy', rb:'5房/6床/2卫', p:'€896 / 2晚（非退 €895）', cny:7168, room:1792, r:'4.6', cxl:'✅ 24h 内免费', v:'ok', why:'**有私人泳池** —— 极光季泡池子是很硬的体验。评分 4.6 偏低、位置在中部（东西都要开）'},
  {t:'alt',  n:'Villa - Havgapet ★5.0', u:A('1259549145786305745','2026-09-30','2026-10-02'), loc:'🟡 中部 Vestvågøy', rb:'7房/7床/2卫', p:'€958 / 2晚（非退 €957）', cny:7664, room:1916, r:'5.0', cxl:'✅ 24h 内免费', v:'ok', why:'★5.0 · 7 间房 —— 4 个人住这个非常空。位置在中部'},
  {t:'alt',  n:'🅲 备用 C · 房子最好 —— Functional architecture close to nature ★5.0', u:A('574286379531171221','2026-09-30','2026-10-02'), loc:'🟢 东侧 Vågan', rb:'4房/4床/2.5卫', p:'€1,041 / 2晚', cny:8328, room:2084, r:'5.0', cxl:'✅ 24h 内免费', v:'ok', why:'★5.0 + **2.5 卫** + 在东侧 + 4 房 —— 「要好房子又要东侧」的答案，而且是唯一比备用 A **便宜**（€182）又不掉配置的。比已订那套贵约 ¥1,144（€143）'},
  {t:'alt',  n:'Valen house in famous Reine ★4.25', u:A('1314514220654606262','2026-09-30','2026-10-02'), loc:'🔴 最西 Moskenes/Reine', rb:'4房/5床/2卫', p:'€1,113 / 2晚', cny:8904, room:2226, r:'4.25', cxl:'✅ 24h 内免费', v:'ok', why:'**就在 Reine**（那张明信片本身）。但评分只有 4.25、最贵那档、10/2 车程最长'},
  {t:'alt',  n:'Unique group stay next to golf and beach ★5.0', u:A('45665373','2026-09-30','2026-10-02'), loc:'🟢 东侧 Vågan', rb:'7房/8床/2.5卫', p:'€1,797→€1,634 / 2晚', cny:13072, room:3268, r:'5.0', cxl:'✅ 24h 内免费', v:'ok', why:'最贵，但仍在预算内。4 个人订 7 间房的农场没什么必要 —— 除非想请客'},
  {t:'alt',  n:'Nusfjord Arctic Resort · Village Cabin Suite Plus', u:B('no/nusfjord-as','2026-09-30','2026-10-02',1), loc:'🟠 西侧 Nusfjord（离 Ramberg 15 min）', rb:'**2 卫（页面明写）· 卧室数未写**', p:'€743 flex（+12% VAT）', cny:6656, room:1664, r:'—', cxl:'✅ 退到 9/16', v:'search', why:'唯一在 Booking 页面上**明写 2 bathrooms** 的罗弗敦房源。🔴 但 "Suite" 不等于 2 卧 —— **订前必须问卧室数**'},
  {t:'alt',  n:'Hattvika Lodge · Nordbua #2（3 卧）', u:B('no/hattvika-lodge','2026-09-30','2026-10-02',1), loc:'🟡 Ballstad（中西部）', rb:'3 卧 · **卫生间数未写**', p:'€715 flex（+12% VAT）', cny:6408, room:1602, r:'—', cxl:'✅ 退到 **9/16**', v:'search', why:'真 rorbu 体验、3 卧。🔴 Booking 页面没写几个卫生间 → 「一定要 2 卫」这条它答不上来'},
  {t:'dead', n:'House with 5 bedrooms overlooking Svolværgeita', u:A('1382960789125435389','2026-09-30','2026-10-02'), loc:'东侧 Vågan', rb:'5房/2卫', p:'€674（搜索页）', cny:0, room:0, r:'4.78', cxl:'—', v:'dead', why:'⛔ 原本的东侧 🥇。房源页 **Those dates are not available**，换干净浏览器复现过（截图 x1）'},
  {t:'dead', n:"Seafront fisherman's cabin in Lofoten ★4.98", u:A('35072091','2026-09-30','2026-10-02'), loc:'中部 Vestvågøy', rb:'3房/5床/2卫', p:'€900（搜索页）', cny:0, room:0, r:'4.98', cxl:'—', v:'dead', why:'⛔ **2026-09-02 新发现：日期不可用。** ★4.98 的真 rorbu，很可惜'},
  {t:'dead', n:'where the ocean meets land · Flakstad ★4.93', u:A('43494853','2026-09-30','2026-10-02'), loc:'西侧 Flakstad', rb:'2房/4床/2卫', p:'€740（搜索页）', cny:0, room:0, r:'4.93', cxl:'—', v:'dead', why:'⛔ **本轮新发现：日期不可用。** 顺带一条：即便能订，房东自己住在同一栋房子的另一半（有连通门）'}]},

{ g:'G8', d:'10/2 → 10/5（3 晚）', n:3, place:'特罗姆瑟', note:'✅ 🆕 **2026-09-02 傍晚回到 3 晚（10/2–10/5）** —— Steve 又给了 10/5 的奥斯陆房源，说明 10/5 就飞回奥斯陆。所以他原来那个 10/2→10/5 的链接本来就是对的，**不用改日期，还省下 €453**。⚠️ 下表其余各行的价是按 **4 晚窗口** 抓的（那时以为要住到 10/6），换回 3 晚窗口后价会降、而且**有两个当时判死的房源在 3 晚下其实是活的** —— 想换的话要重抓。挪威酒店/公寓行**已 ×1.12 补 VAT**。',
  opts:[
  {t:'pick', n:'🆕 Tromsø 4 房 / 4 床 / 2 卫（3 晚）', u:A('825162133059470411','2026-10-02','2026-10-05'), loc:'特罗姆瑟', rb:'4房/4床/2卫', p:'**€1,526 / 3 晚**', cny:12208, room:2035, r:'—', cxl:'✅ 免费退到 10/1', v:'ok', why:'**Steve 自己选的，已设为默认，日期不用改。** 4 卧一人一间、可退到 10/1。🟠 我原来的船屋（3房**3卫** ★5.0）3 晚是 **€825**，仍便宜约 **€700 ≈ ¥5,600** —— 这一段的差价仍是全程最大的一笔'},
  {t:'alt',  n:'Houseboat "Grosso" ★5.0（住船上，我原来的默认）', u:A('1607078897559083655','2026-10-02','2026-10-05'), loc:'特罗姆瑟市区水上', rb:'3房/7床/**3卫**', p:'€825 / 3晚（4 晚是 €1,033）', cny:6600, room:1100, r:'5.0', cxl:'✅ 24h 内免费', v:'search', why:'**全程单价最低**（¥1,100/房/晚），卫生间比人多（3 卫 / 4 人），★5.0，可退。比新默认便宜约 **¥5,600** —— 唯一的取舍是「愿不愿意睡在船上」。⚠️ €825 是把 4 晚价按晚数折的估数，3 晚窗口要重抓'},
  {t:'alt',  n:'TA Vervet · Two-Bedroom Apartment', u:B('no/ta-vervet-apartment','2026-10-02','2026-10-06',1), loc:'Vervet 新区，走路到市中心', rb:'2 卧 · **卫生间数未写**', p:'€199/晚 flex（+VAT）= €891', cny:7128, room:891, r:'—', cxl:'✅ 退到 9/18', v:'ok', why:'**唯一比船屋更便宜的**（¥891/房/晚）。🔴 但 Enter/Vervet 的 Two-Bedroom 多为 **1 卫** —— 要 2 卫就得先问'},
  {t:'alt',  n:'3BR/2BA Tromsø ★4.86', u:A('805864934151694916','2026-10-02','2026-10-06'), loc:'特罗姆瑟', rb:'3房/3床/2卫', p:'€1,645→€1,398 / 4晚（不可退）', cny:11184, room:1398, r:'4.86', cxl:'⛔ 不可退', v:'ok', why:'实测能订。比船屋贵 ¥2,900 且不可退 —— 除非不想住船上'},
  {t:'alt',  n:'Cozy house on Tomasjord ★5.0', u:A('938536829410600780','2026-10-02','2026-10-06'), loc:'Tomasjord（跨桥，市区 10 min）', rb:'3房/4床/2卫', p:'€1,660→€1,524 / 4晚', cny:12192, room:1524, r:'5.0', cxl:'✅ 24h 内免费 · 9/25 前部分退', v:'ok', why:'★5.0 的独栋 + 可退。要「住陆地上的正常房子」就是这个'},
  {t:'alt',  n:'5BR/2.5BA Tromsø', u:A('1763946111917505608','2026-10-02','2026-10-06'), loc:'特罗姆瑟', rb:'5房/5床/2.5卫', p:'€1,924→€1,539 / 4晚', cny:12312, room:1539, r:'新房源', cxl:'✅ 24h 内免费 · 9/25 前部分退', v:'ok', why:'房间最多 + 2.5 卫 + 可退。**没有评价**（新房源）是唯一的不确定'},
  {t:'alt',  n:'Thon Hotel Polar ×2 Standard Double', u:B('no/thon-polar','2026-10-02','2026-10-06'), loc:'市中心', rb:'2房/2卫', p:'€153/间/晚 flex（+VAT）= €1,371', cny:10968, room:1371, r:'—', cxl:'✅ 退到 10/1 · 9/29 前不付钱', v:'ok', why:'最省心的酒店兜底：含早、市中心、退到 10/1。非退档 €133/间/晚 = ¥1,192/房'},
  {t:'alt',  n:'Scandic Ishavshotel ×2 Twin', u:B('no/scandic-ishavshotel','2026-10-02','2026-10-06'), loc:'港口边（那栋帆船造型的）', rb:'2房/2卫', p:'€183/间/晚 flex（+VAT）= €1,640', cny:13120, room:1640, r:'—', cxl:'✅ 退到 10/1', v:'ok', why:'位置和早餐是特罗姆瑟最好的一档，54 个房型行有货 = 最不会卖光'},
  {t:'alt',  n:'Enter Viking · Three-Bedroom Apartment', u:B('no/enter-viking-apartments','2026-10-02','2026-10-06',1), loc:'市中心', rb:'3 卧 · 卫生间数未写', p:'€402/晚（+VAT）= €1,802', cny:14416, room:1802, r:'—', cxl:'⛔ 不可退', v:'ok', why:'3 卧整套公寓，但**不可退 + 贵 ¥6,150**。只在别的都没了才考虑'},
  {t:'dead', n:'Gorgeous views, close to downtown ★4.95', u:A('880420426360588834','2026-10-02','2026-10-06'), loc:'特罗姆瑟', rb:'4房/4床/2卫', p:'€1,600 / 3晚（搜索页）', cny:0, room:0, r:'4.95', cxl:'—', v:'dead', why:'⛔ **本轮新发现：换成 4 晚窗口（10/2–10/6）后日期不可用。** 3 晚时它是能订的 —— 多住 10/2 那一晚的代价之一'},
  {t:'alt',  n:'The Loft I 4BR/2 Bath ★5.0', u:A('1480974381910568232','2026-10-02','2026-10-06'), loc:'市中心', rb:'4房/5床/2.5卫', p:'€4,405→€2,252 / 4晚', cny:18016, room:2252, r:'5.0', cxl:'✅ 24h 内免费', v:'ok', why:'能订，但 ¥2,252/房 —— 是 🥇 的 2.2 倍。列在这里只为封住「有没有更好的市中心大房子」这个问题'},
  {t:'dead', n:'Enter Amalie · Three-Bedroom Loft', u:B('no/enter-amalie-apartments','2026-10-02','2026-10-06',1), loc:'市中心', rb:'3 卧', p:'原 €925 / 3晚', cny:0, room:0, r:'—', cxl:'—', v:'dead', why:'⛔ **已没了** —— 10/2–10/6 整个物业只剩 One-Bedroom（€785/4晚）。它曾是 3 晚方案的 🥇'},
  {t:'dead', n:'Enter St Elisabeth · Suite ×2 间', u:B('no/enter-st-elisabeth-suites','2026-10-02','2026-10-06'), loc:'市中心，带 spa', rb:'2 套房', p:'€358/间/晚（+VAT）', cny:0, room:0, r:'—', cxl:'—', v:'dead', why:'⛔ **¥3,208/房超预算**。带 spa，但不值这个价'}]},

{ g:'G8b', d:'10/5 → 10/6', n:1, place:'🆕 奥斯陆一带（10/5 从特罗姆瑟飞回来）', note:'🆕 **这一组是 2026-09-02 傍晚新增的** —— Steve 给了 10/5 的房源，等于把行程改成「10/5 飞回奥斯陆睡一晚缓冲，10/6 从容飞北京」。🔴 他选的那个**不在机场旁**，在 Stange 的 Mjøsli 森林里，房源页自己写着「A car is required」→ 要在 OSL 机场加租 1 天车（$79 起）。',
  opts:[
  {t:'pick', n:'🆕 Konglehytta 3 · Star View · Sauna（整栋小木屋）', u:A('648419631702172808','2026-10-05','2026-10-06'), loc:'Mjøsli · Stange（Innlandet）· **离 OSL 30 min 车程**', rb:'2房/3床/**1卫**', p:'可退 **€306**（不可退 €296）', cny:2448, room:1224, r:'4.98', cxl:'✅ 可退档只贵 €10 → 买可退', v:'ok', why:'**Steve 自己选的，已设为默认。** ★4.98、**私人桑拿** + Mjøsa 湖景 + 星空；床型好（卧1 两张双人 + 卧2 一张双人）。🔴 两条代价：① **必须加租一台 OSL 的车（+$86）**，房源页明写 "A car is required"；② 只有 1 个卫生间，而次日要赶洲际航班'},
  {t:'alt',  n:'Clarion Hotel Oslo Airport ×2 Standard Double', u:B('no/clarion-oslo-airport','2026-10-05','2026-10-06'), loc:'**走廊直通航站楼**', rb:'2房/2卫', p:'约 €86/间 flex（+12% VAT）≈ €193', cny:1544, room:772, r:'—', cxl:'✅ 可退', v:'search', why:'**不用租车、不用开夜路、2 个卫生间，而且比小屋便宜** —— 纯从「第二天要飞北京」的角度这个更稳。代价：没有桑拿、没有星空、是个机场酒店。⚠️ 价是按 10/6 那晚抓的，10/5 要再核一次'},
  {t:'alt',  n:'同 9/29 那套 Airbnb · Nannestad 5房1.5卫', u:A('1461656866395092330','2026-10-05','2026-10-06'), loc:'Nannestad（OSL 旁）', rb:'5房/5床/1.5卫', p:'约 €292 / 1晚', cny:2336, room:1168, r:'—', cxl:'—', v:'search', why:'和 9/29 同一套 → 路线和门锁都熟，5 个卧室。⚠️ **10/5 的可订性没核过**，而且它也在机场外（但比 Stange 近很多）'},
  ]},

{ g:'G9', d:'10/6 → 10/7', n:1, place:'（条件性）奥斯陆机场 —— 只在 Kevin 的回程是 10/7 时才需要', note:'🔴 这一晚**没计入总账**，因为它取决于 Kevin 的 Oslo→北京 是 10/6 还是 10/7 起飞。四家全部实测有货，选的这个可以退到 10/5 —— 等回信也不亏。',
  opts:[
  {t:'pick', n:'Clarion Hotel Oslo Airport ×2 Standard Double', u:B('no/clarion-oslo-airport','2026-10-06','2026-10-07'), loc:'机场旁', rb:'2房/2卫', p:'€86/间 flex（+VAT）= €193', cny:1544, room:772, r:'—', cxl:'✅ 退到 **10/5**', v:'ok', why:'**四家里最便宜的可退档**，而且退到 10/5 —— 正好晚于「Kevin 该回信」的时间。占位就用它'},
  {t:'alt',  n:'Scandic Oslo Airport ×2 Standard Twin', u:B('no/scandic-oslo-airport','2026-10-06','2026-10-07'), loc:'机场旁', rb:'2房/2卫', p:'€96/间 flex = €215 · 非退 €73/间 = €164', cny:1720, room:860, r:'—', cxl:'✅ 退到 10/5', v:'ok', why:'非退档 ¥656/房 是**全程最便宜的一晚** —— 但只有等 Kevin 确认了才敢买不可退'},
  {t:'alt',  n:'Thon Hotel Gardermoen ×2 Standard Twin', u:B('no/thon-gardermoen','2026-10-06','2026-10-07'), loc:'机场旁', rb:'2房/2卫', p:'€109/间 flex（+VAT）= €244', cny:1953, room:977, r:'—', cxl:'✅ 退到 10/5', v:'ok', why:'和 9/24 同一家，行李和路线都熟。贵一点'},
  {t:'alt',  n:'Radisson Hotel & Conference Centre ×2 Standard', u:B('no/park-inn-oslo-airport','2026-10-06','2026-10-07'), loc:'机场旁', rb:'2房/2卫', p:'€157/间（+VAT）= €351', cny:2806, room:1403, r:'—', cxl:'✅ 退到 **当天 18:00**', v:'ok', why:'唯一能**退到当天傍晚**的 —— 如果 Kevin 到最后一刻还没定，这个最保险。19 个房型行有货'},
  {t:'alt',  n:'同 9/24 那套 Airbnb · Nannestad', u:A('1616864516592253636','2026-10-06','2026-10-07'), loc:'Nannestad', rb:'3房/5床/2卫', p:'€260 / 1晚', cny:2080, room:1040, r:'—', cxl:'⛔ 不可退', v:'search', why:'一间整套房，但**不可退**，而且 10/6 这个日期我**没有复核过**。条件性的一晚买不可退没道理'}]}
];

/* ---------- 每天一个颜色（地图圆点 / 路线 / 左侧列表 / 详情卡 共用同一套） ----------
 * 选色原则：① 深底上都够亮 ② 相邻两天色相差得远（不然连着的两天分不开）
 * ③ 不靠红绿区分相邻天（红绿色盲友好）④ 与「🛏 住宿 / 🚗 取还车」图钉的固定色不撞
 */
const DAYCOL = [
  '#7dd3fc', /* D0  天蓝   奥斯陆中转 */
  '#34d399', /* D1  翠绿   雷市 */
  '#fbbf24', /* D2  琥珀   南岸 */
  '#f472b6', /* D3  粉     冰河湖 */
  '#a78bfa', /* D4  紫罗兰 黄金圈 */
  '#fb7185', /* D5  玫红   斯奈山（最紧的一天）*/
  '#22d3ee', /* D6  青     进罗弗敦 */
  '#a3e635', /* D7  柠绿   罗弗敦西行 */
  '#fdba74', /* D8  橙     开去特罗姆瑟 */
  '#c084fc', /* D9  紫     特罗姆瑟市区 */
  '#4ade80', /* D10 绿     自由日 */
  '#60a5fa', /* D11 蓝     Senja */
  '#f0abfc', /* D12 洋红   回程 */
  '#facc15'  /* 备用 */
];
const dayColor = (i) => DAYCOL[i % DAYCOL.length];
