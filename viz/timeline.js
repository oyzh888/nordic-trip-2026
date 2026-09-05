/* 北欧 2026 · 时间线（甘特图）数据层 —— 唯一权威时刻表
 *
 * 为什么单独一份而不复用 viz/data.js：那里的时间是写给人读的散文
 * （'🆕 10/5 10:45（跟着 08:20 那班）'），机器没法拿来算「有没有覆盖」。
 * 这里每条都是**可计算的 ISO 时刻**，页面上的自动体检（夜里有没有住的、
 * 落地到取车等多久、还车到起飞够不够）全部由这份数据算出来，不是手写的。
 *
 * st（状态）三档，样式不同：
 *   booked = 已付钱（实心 + ✅）
 *   ok     = 已选定、链接和价都核过，但还没下单（实心浅色）
 *   tbd    = 还没定／要人填（虚线斜纹）—— 页面底部会自动列出来
 *
 * 口径与出处：notes/PLAN-final.md（住宿+租车最终方案）· 航班时刻见 §五「航班↔取还车对齐」
 * 车价 = DiscoverCars 实抓（notes/_research/out_lkn · out_pickup）
 * 车程 = OSRM 真实路网实测，不是估的
 */

const DAY0 = '2026-09-24';
const DAYN = 14;                     // 9/24 → 10/7（含条件性的第 13 晚）

/* ---------- 事件表：lane = stay / car / fly / act ---------- */
const EV = [
/* ===== 9/24 四 · 落地奥斯陆 ===== */
 {lane:'fly', s:'2026-09-24T21:30', e:'2026-09-24T22:10', t:'✈ 北京首都 T2 → 奥斯陆（9h25，已出票）',
  st:'ok', who:'预订号 JP1Y15', note:'✅ <b>2026-09-04 已出票</b>（携程截图）。🟠 <b>还差两件事</b>：① <b>落地钟点</b> —— 截图上被裁掉了，时间线里 21:30 还是占位值；② 那一段<b>只显示 1 位出行人（LIU/HANGTAO）</b>，要确认 4 个人是不是同一班（三段的出行人名字两两不同：9/25 是 ZHANG/MINXUAN+WU/QIN…、9/29 是 OUYANG/ZHIHAO+LIU/HA… → 分了几个订单，<b>要逐段点开确认 4 个人齐</b>）'},
 {lane:'act', s:'2026-09-24T22:10', e:'2026-09-24T22:40', t:'OSL → Nannestad 约 20 min',
  st:'tbd', note:'🔴 <b>怎么过去要填</b>：这一段<b>没有车</b>（冰岛那台在 KEF 取）。打车约 NOK 500–700 ≈ ¥335–470，或问房东能不能接。<b>这是全程唯一「没车又要移动」的两段之一</b>'},
 {lane:'stay', s:'2026-09-24T22:40', e:'2026-09-25T04:30', t:'🆕 建议改：Thon Hotel Gardermoen ×2 间（原 Nannestad Airbnb）',
  st:'tbd', price:'€107/间 ×2 = €214 ≈ ¥1,712（可退到 9/23）· 原 Airbnb €260 ≈ ¥2,080 不可退',
  link:'https://www.booking.com/hotel/no/thon-gardermoen.html?checkin=2026-09-24&checkout=2026-09-25&group_adults=4&no_rooms=2&selected_currency=EUR',
  note:'🆕🆕 <b>2026-09-04 强烈建议改成机场酒店</b>（实价已抓）。理由是算出来的，不是偏好：这一夜本质是<b>「落地→睡几小时→再起飞」的中转</b>，而 Nannestad 那套在 <b>20 分钟车程外、我们又没有车</b>。换成机场酒店同时省三样：<b>省两趟深夜打车（NOK 500–700/趟）· 多睡 40–50 分钟 · 24h 前台（不用赌能不能深夜自助入住）</b>。'+
    '🔴 <b>这一夜尤其极端：21:30 落地，而 SK4787 是 06:15 起飞 → 04:30 就得走，只能睡 6 小时。</b>'+
    '钱也是赢的：Thon 2 间 <b>€214 可退</b>（含免费机场班车）vs Airbnb <b>€260 不可退</b> + 两趟打车 ¥670–940 '+
    '→ <b>省约 ¥1,040–1,310</b>。Clarion 这一晚要 €276（贵一点，但走过去不用班车）。'+
    '⚠️ Booking 的挪威价通常已含 12% VAT；若不含则是 €214→€240'},

/* ===== 9/25 五 · 飞冰岛 ===== */
 {lane:'fly', s:'2026-09-25T06:15', e:'2026-09-25T07:05', t:'✈ <b>SK4787</b> OSL 06:15 → KEF 07:05（已出票）',
  st:'booked', who:'北欧航空 SAS · 已出票', note:'✅ <b>2026-09-04 已出票。</b>正好是我算出来的那班（当天唯一的直飞，2h50）。🎯 <b>两个直接结果</b>：① <b>冰岛取车钟点定了 = 08:00</b>（落地 07:05 + 摆渡车约 45 min）；② <b>9/25 白得一整天</b> —— 原来只排了「傍晚市中心」，现在已按这个重排（见下面 📍 那两条）'},
 {lane:'car', s:'2026-09-25T08:00', e:'2026-09-29T18:00', t:'🇮🇸 冰岛 · Peugeot 2008 4x4 自动 · <b>08:00 取</b>（5 个计费日）',
  st:'ok', price:'$326 裸车 ≈ ¥2,315（+必买三险 → $451–526）',
  link:'https://www.discovercars.com/search/e85517b5-c5d1-40ac-8683-ac2002667b9d?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoxNzg3LCJEcm9wT2ZmTG9jYXRpb25JZCI6MTc4NywiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTA5LTI1IDA4OjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0wOS0yOSAxODowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ',
  note:'✅ <b>钟点已定：08:00</b>（SK4787 07:05 落地 + 摆渡车约 45 min —— 这台<b>不在航站楼里</b>，要坐摆渡车去取，所以不能按 30 分钟算）。实测 08:00 有 17 个报价，且 08:00–16:00 <b>全部同价</b> → 早取不花钱。🔴 一天涨 26%（9/3 $258 → 9/4 $326）→ 早订。⚠️ 订的时候<b>填航班号 SK4787</b>，柜台会跟航班，晚点也留车'},
 {lane:'act', s:'2026-09-25T09:00', e:'2026-09-25T12:00', t:'🆕 蓝湖泡汤（KEF 开车 20 min）',
  st:'tbd', note:'🆕 <b>2026-09-04 新排的：从 9/28 那个 520 km 的巨无霸日子里挪过来。</b>蓝湖离 KEF 只有 20 分钟，而我们 07:05 就落地了 —— 刚下飞机泡温泉是这一天最合理的用法。🔴 <b>蓝湖必须提前订时段票</b>（不是随到随进），这是新增的一项要填'},
 {lane:'act', s:'2026-09-25T12:15', e:'2026-09-25T15:30', t:'🆕 雷克雅内斯半岛小环线（全在 KEF 15–50 min 圈内）',
  st:'ok', note:'🆕 <b>从 9/29 挪过来的</b>：两块大陆之间的小桥 · Gunnuhver 泥浆池 · Brimketill 石头浴缸 · Krýsuvík 地热。全都在机场附近，不用绕路'},
 {lane:'act', s:'2026-09-25T15:30', e:'2026-09-25T16:20', t:'雷克雅内斯 → 雷克雅未克 约 50 min',
  st:'ok', note:'落地就取车 = 省掉 4 人 ×2 程机场大巴 ≈ ¥1,360'},
 {lane:'act', s:'2026-09-25T17:00', e:'2026-09-25T20:00', t:'雷市：Hallgrímskirkja · 老港 · Sun Voyager',
  st:'ok', note:'🎯 <b>这一天从「傍晚市中心」变成完整一天</b>，就是因为 SK4787 07:05 落地。代价：06:15 的飞机要 04:00 起'},
 {lane:'stay', s:'2026-09-25T15:00', e:'2026-09-26T10:00', t:'雷克雅未克 · Aurora view 3BR 2BATH（3房/3床/2卫）',
  st:'ok', price:'€647→€447 ≈ ¥1,788', link:'https://www.airbnb.com/rooms/1729852848905770040?check_in=2026-09-25&check_out=2026-09-26&adults=4&currency=EUR',
  note:'✅ 24h 内免费退，9/18 前部分退'},

/* ===== 9/26 六 · 南岸 ===== */
 {lane:'act', s:'2026-09-26T09:00', e:'2026-09-26T17:30', t:'南岸 300 km / 3h45：Seljalandsfoss · Skógafoss · Dyrhólaey · Reynisfjara',
  st:'ok', note:'第一道瀑布能从背后绕过去；第二道 60 m 宽'},
 {lane:'stay', s:'2026-09-26T17:30', e:'2026-09-27T10:00', t:'Hörgsland Cottages · 3 卧整栋（Klaustur 东 10 km）',
  st:'ok', price:'€448 +税 = €503 ≈ ¥2,012', link:'https://www.booking.com/hotel/is/horgsland-cottages.html?checkin=2026-09-26&checkout=2026-09-27&group_adults=4&no_rooms=2&selected_currency=EUR',
  note:'⛔ <b>不可退</b>（€549 档可退到 9/12 → 9/12 前要决定买不买可退档）。🟠 三个卧室都没有双人床（上下铺×2 + 单人×2）—— 那对夫妻要注意'},

/* ===== 9/27 日 · 冰河湖 ===== */
 {lane:'act', s:'2026-09-27T09:00', e:'2026-09-27T17:00', t:'冰河湖 200 km / 2h30：Jökulsárlón · 钻石沙滩 · Fjallsárlón',
  st:'ok', note:'🎯 住处往东挪的红利：这天从 390 km 降到 200 km，从「最长」变最轻松'},
 {lane:'act', s:'2026-09-27T20:30', e:'2026-09-27T23:30', t:'夜：开去 Stokksnes 等极光',
  st:'ok', note:'成败看云量，不看经度 —— 往东住不会让极光更好'},
 {lane:'stay', s:'2026-09-27T17:00', e:'2026-09-28T10:00', t:'Guesthouse Birkifell · 2 卧整栋（Höfn 西 10 km）',
  st:'ok', price:'€504 +税 = €565 ≈ ¥2,260', link:'https://www.booking.com/hotel/is/guesthouse-birkifell.html?checkin=2026-09-27&checkout=2026-09-28&group_adults=4&no_rooms=2&selected_currency=EUR',
  note:'✅ <b>免费退到 9/25 + 到店付 → 零风险，最该先订的一个</b>。只剩 1 套'},

/* ===== 9/28 一 · 黄金圈（全程最长） ===== */
 {lane:'act', s:'2026-09-28T08:30', e:'2026-09-28T17:30', t:'🆕 黄金圈（蓝湖已挪走）约 400 km / 5h：Þingvellir · Geysir · Gullfoss',
  st:'ok', note:'🆕 <b>已减负</b>：蓝湖挪到 9/25 之后，这天从 <b>520 km / 6h30 → 约 400 km / 5h</b>，而且不用赶在关门前泡汤。晚上仍住 Njarðvík 那套带热浴桶+桑拿的（泡汤不缺）'},
 {lane:'stay', s:'2026-09-28T19:30', e:'2026-09-29T10:00', t:'Njarðvík · Hot tub & Sauna · Ocean Break（3房/3床/<b>1卫</b>）',
  st:'ok', price:'€531→€335 ≈ ¥1,340', link:'https://www.airbnb.com/rooms/1139944377459145061?check_in=2026-09-28&check_out=2026-09-29&adults=4&currency=EUR',
  note:'✅ 免费退到 9/23。🟠 <b>只有 1 个卫生间</b>（4 个人）—— 但带热浴桶+桑拿，跑完 6h30 那天正需要。KEF 只 5 分钟'},

/* ===== 9/29 二 · 减负日 + 飞回奥斯陆 ===== */
 {lane:'act', s:'2026-09-29T10:00', e:'2026-09-29T17:00', t:'🆕 真正的休息日：睡到自然醒 + 雷市城里（雷克雅内斯已挪到 9/25）',
  st:'ok', note:'🆕 <b>这一天现在是空的</b>（雷克雅内斯挪到了 9/25）。🎯 <b>这是好事，不是浪费</b>：今晚 DY1171 20:05 起飞、<b>00:45 才落奥斯陆</b>，明早还要飞 EVE —— 今天越轻越好。想加东西的话：雷市的 Sky Lagoon（市区里，比蓝湖近）或者纯逛街'},
 {lane:'fly', s:'2026-09-29T20:05', e:'2026-09-30T00:45', t:'✈ <b>DY1171</b> KEF 20:05 → OSL 00:45+1（出票中）',
  st:'booked', who:'挪威穿梭 Norwegian · 出票中', note:'✅ <b>2026-09-04 已订</b>（出票中）。也正好是我算出来的那班（当天最便宜的直飞，2h40）。<b>冰岛还车 18:00 就是按它配的 —— 缓冲 2h05，合适。</b>🔴 但它带来一个真问题：<b>00:45 落地，明早 08:55 又要飞 EVE</b> → 见下面那一夜'},
 {lane:'act', s:'2026-09-30T00:45', e:'2026-09-30T01:30', t:'OSL → Nannestad 深夜 20 min',
  st:'tbd', note:'🔴 <b>没有车的第二段</b>（挪威那台在 EVE 才取）→ 深夜打车。而且要确认 Airbnb 能不能 <b>01:30 自助入住</b>'},
 {lane:'stay', s:'2026-09-30T01:10', e:'2026-09-30T07:45', t:'🆕 建议改：Clarion Hotel Oslo Airport ×2 间（原 Nannestad Airbnb）',
  st:'tbd', price:'€95/间 ×2 = €190 ≈ ¥1,520（可退到 9/28）· 原 Airbnb €292 ≈ ¥1,168 可退',
  link:'https://www.booking.com/hotel/no/clarion-oslo-airport.html?checkin=2026-09-29&checkout=2026-09-30&group_adults=4&no_rooms=2&selected_currency=EUR',
  note:'🆕🆕 <b>2026-09-04 强烈建议改成机场酒店</b>（实价已抓）。理由是算出来的，不是偏好：这一夜本质是<b>「落地→睡几小时→再起飞」的中转</b>，而 Nannestad 那套在 <b>20 分钟车程外、我们又没有车</b>。换成机场酒店同时省三样：<b>省两趟深夜打车（NOK 500–700/趟）· 多睡 40–50 分钟 · 24h 前台（不用赌能不能深夜自助入住）</b>。'+
    '🔴🔴 <b>这是全程最紧的一夜，而且 DY1171 已经出票了 —— 00:45 落地是确定的事实，不再是假设。</b>'+
    '住机场：01:10 就能进房、07:45 再走（<b>约 6.5 小时</b>）；住 Nannestad 要 01:30 才到、07:30 就得走（<b>6 小时</b>），'+
    '还要赌房东让不让 01:30 自助入住。钱：Clarion 2 间 <b>€190 ≈ ¥1,520 可退</b> vs Airbnb <b>¥1,168 + 两趟打车 ¥670–940 = ¥1,838–2,108</b> '+
    '→ <b>换酒店反而便宜 ¥320–590</b>。<br>🟠 <b>另一条独立的解法</b>（可叠加）：如果 9/30 那班 EVE 是同价的 '+
    '<b>13:20→15:00</b>，这一夜能睡到 10 小时以上 —— 代价是天快黑才进罗弗敦。<b>先去确认那班到底几点。</b>'},

/* ===== 9/30 三 · 进罗弗敦 ===== */
 {lane:'fly', s:'2026-09-30T08:55', e:'2026-09-30T10:35', t:'✈ OSL → EVE 埃沃内斯（Norwegian 08:55→10:35）',
  st:'ok', who:'Kevin · 截图里已有这一段', note:'✅ 携程截图最下面已经有「9月30日 前往 埃沃内斯」这一段，<b>但时刻被裁掉了</b> —— 时间线按最便宜也最合理的 Norwegian 08:55→10:35 画（NOK 4,196/4 人）。🔴 <b>要确认它到底是几点</b>：如果真是 08:55，那前一夜只能睡 5 小时（见上一条）；同价的 <b>13:20→15:00</b> 能把那一夜补到 10 小时，代价是天快黑才进罗弗敦'},
 {lane:'car', s:'2026-09-30T11:00', e:'2026-10-02T14:30', t:'🇳🇴 车① · Ford Explorer 4WD（EVE 取 → <b>Leknes 还</b>，3 个计费日）',
  st:'ok', price:'$647 ≈ ¥4,594',
  link:'https://www.discovercars.com/search/f7152183-113a-482a-b4c9-d8b4ba64dbf5?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoyMDg4LCJEcm9wT2ZmTG9jYXRpb25JZCI6MjA5MSwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTA5LTMwIDExOjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wMiAxNDozMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ',
  note:'✅ 航站楼内取车 → 落地 10:35、取车 11:00 = <b>等 25 分钟</b>。🔴 <b>Leknes 异地还车只有 5 个报价</b>（Evenes 22 / 特罗姆瑟 16）→ 四台里<b>最早订这台</b>。🟠 48h 悬崖：10/2 11:00 前还 = 2 天 $571，14:30 还 = 3 天 $647（多 $76 买下最后 3.5 小时）。⚠️ 押金冻结曾报到 $1,805 → 要额度够的信用卡'},
 {lane:'act', s:'2026-09-30T11:15', e:'2026-09-30T15:30', t:'EVE → Lyngvær 175 km / <b>3h02</b>（OSRM 实测）',
  st:'ok', note:'⚠️ 文档里旧的「165 km / 2h30」偏乐观，OSRM 真实路网是 3h02。加上拍照停车，到住处约 15:30–16:30'},
 {lane:'stay', s:'2026-09-30T16:00', e:'2026-10-02T10:00', t:'✅ Nordic Lodge Retreat · Lyngvær（4房/8床/2卫 · 桑拿+按摩浴缸）',
  st:'booked', price:'€898 / 2 晚 ≈ ¥1,796/晚', link:'https://www.airbnb.com/rooms/1303545546783105490?check_in=2026-09-30&check_out=2026-10-02&adults=4&currency=EUR',
  note:'✅ <b>已付钱，这一段结束了。</b>★4.92 · 98 m² · 2025-01 新建 · 自助入住。🔴 <b>9/23 是部分退款悬崖</b> —— 要换必须在那之前（备用 🅰🅱🅲 在计划页）'},

/* ===== 10/1 四 · 明信片那一侧 ===== */
 {lane:'act', s:'2026-10-01T09:00', e:'2026-10-01T17:00', t:'西行往返约 4h：Hamnøy 红屋 · Sakrisøy · Reine（Reinebringen 阶梯 1.5–2h）',
  st:'ok', note:'当天回，不搬箱子 —— 这就是「住东侧」换来的'},
 {lane:'act', s:'2026-10-01T20:00', e:'2026-10-01T23:30', t:'夜：极光（罗弗敦已开季）',
  st:'ok', note:'🟠 E10 风暴封路在 9 月末–10 月很常见 → 也是「东侧 + 可退」优于「西侧 + 不可退」的原因'},

/* ===== 10/2 五 · 飞特罗姆瑟 ===== */
 {lane:'act', s:'2026-10-02T09:00', e:'2026-10-02T13:00', t:'🎯 上午白得：Henningsvær（28 min）或西侧沙滩（Ramberg→Leknes 35 min）',
  st:'ok', note:'🎯 <b>这是「时间用满」拿到的一块。</b>直接去 Leknes 只要 1h16 → 13:00 出发就够；加 Henningsvær 10:30 走；跑西侧沙滩 09:00 走'},
 {lane:'act', s:'2026-10-02T13:00', e:'2026-10-02T14:15', t:'Lyngvær → Leknes 机场 63.6 km / 1h16（OSRM）',
  st:'ok'},
 {lane:'fly', s:'2026-10-02T15:40', e:'2026-10-02T16:35', t:'✈ <b>WF816 Leknes → 特罗姆瑟</b>（Widerøe Dash-8，直飞 55 min）',
  st:'ok', who:'Steve/Kevin 订票',
  note:'✅ <b>航班已确认</b>（携程截图留档）。🔴🔴 <b>只剩 6 张票，我们要 4 张 → 这是现在最急的一件事。</b>⚠️ 最便宜 ¥1,274 那档<b>不含托运也不含手提</b>（只 1 件个人物品）→ 要买 <b>¥1,490 含 1×23kg 托运</b> 那档，4 人 = ¥5,960'},
 {lane:'car', s:'2026-10-02T17:00', e:'2026-10-05T07:30', t:'🇳🇴 车② · 自动四驱（TOS 取还，3 个计费日）',
  st:'ok', price:'$224 ≈ ¥1,590',
  link:'https://www.discovercars.com/search/b91eeeb9-adb0-466d-bd01-8056e7146c32?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoyMTk1LCJEcm9wT2ZmTG9jYXRpb25JZCI6MjE5NSwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTEwLTAyIDE3OjAwIiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wNSAxMDowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ',
  note:'✅ 航站楼内取车 → 落地 16:35、取车 17:00 = <b>等 25 分钟</b>（17:00 与 17:30 同价，所以取早的）。Senja 那 500 km 走这台，挪威租车基本不限里程'},
 {lane:'stay', s:'2026-10-02T18:00', e:'2026-10-05T07:00', t:'特罗姆瑟 4 房 · 4 床 · 2 卫（连住 3 晚）',
  st:'ok', price:'€1,526 / 3 晚 ≈ ¥2,035/晚', link:'https://www.airbnb.com/rooms/825162133059470411?check_in=2026-10-02&check_out=2026-10-05&adults=4&currency=EUR',
  note:'✅ 免费退到 10/1。🟠 <b>全程最大的一笔差价</b>：船屋 Houseboat "Grosso" 3 晚只 €825（3 卫、★5.0）—— 差约 ¥5,600，订之前值得再比一次'},
 {lane:'act', s:'2026-10-02T19:30', e:'2026-10-02T23:30', t:'夜：第一场极光（18:30 就天黑了，所以下午到不吃亏）',
  st:'ok'},

/* ===== 10/3 六 ===== */
 {lane:'act', s:'2026-10-03T10:00', e:'2026-10-03T17:00', t:'市区：北极大教堂 · Fjellheisen 缆车上 Storsteinen',
  st:'ok'},
 {lane:'act', s:'2026-10-03T19:30', e:'2026-10-03T23:59', t:'夜：往内陆开，躲云追极光',
  st:'ok'},

/* ===== 10/4 日 · Senja ===== */
 {lane:'act', s:'2026-10-04T06:30', e:'2026-10-04T19:30', t:'Senja 往返约 500 km / 路上 5–6h：Tungeneset · Bergsbotn · Ersfjord',
  st:'tbd', note:'🔴 <b>渡轮班表要填</b>：Senja 从 10/5 挪到了 <b>10/4 = 周日</b>，周日班次通常更少（Torghatten Nord / Entur 要重核）。渡轮 NOK 456 往返 ≈ ¥306'},

/* ===== 10/5 一 · 飞回奥斯陆，住森林 ===== */
 {lane:'fly', s:'2026-10-05T08:20', e:'2026-10-05T10:15', t:'✈ 特罗姆瑟 → OSL（建议 Norwegian 08:20→10:15）',
  st:'tbd', who:'Kevin',
  note:'🔴 <b>要填。</b>🥇 建议 08:20 那班：<b>比 10:45 那班早 2.5 小时、还便宜 NOK 2,000</b>（6,396 vs 8,396）。🎯 收益 = 11:30 就进小屋，比坐 13:00 那班多 <b>4 小时白天</b>（那一带 18:45 天黑）。代价：跑完 Senja 之后要 06:45 起床 —— 不想早起就退回 10:45→12:40，车③ 改 13:10 取（同价）'},
 {lane:'car', s:'2026-10-05T10:45', e:'2026-10-06T10:00', t:'🇳🇴 车③ · 自动四驱（OSL 取还，1 个计费日）',
  st:'tbd', price:'$85 ≈ ¥604',
  link:'https://www.discovercars.com/search/ce93a27c-2442-4101-8ddd-f11bc2f6463d?sq=eyJQaWNrdXBMb2NhdGlvbklkIjoxNzEwLCJEcm9wT2ZmTG9jYXRpb25JZCI6MTcxMCwiUGlja3VwRGF0ZVRpbWUiOiIyMDI2LTEwLTA1IDEwOjQ1IiwiRHJvcE9mZkRhdGVUaW1lIjoiMjAyNi0xMC0wNiAxMDowMCIsIlJlc2lkZW5jZUNvdW50cnkiOiJVUyIsIkRyaXZlckFnZSI6MzUsIkhhc2giOiIifQ',
  note:'🔴 <b>要不要租这台是个决定（B5）</b>：Stange 小屋房源页写着 "A car is required"。不租就换机场旁的 Clarion（€193、2 卫，反而更便宜）。✅ 航站楼内取车，10:45/13:00/14:00 三个点实测同价 → 跟着航班填就行。⚠️ 最便宜那档是 VW ID.4 <b>电车</b>，1 天短租要留意充电'},
 {lane:'act', s:'2026-10-05T11:00', e:'2026-10-05T18:45', t:'OSL → Stange/Mjøsli 30–40 min，Mjøsa 湖畔（18:45 天黑）',
  st:'ok', note:'🎯 坐 08:20 那班能拿到约 <b>7 小时白天</b>；坐 13:00 那班只剩 2.5 小时'},
 {lane:'stay', s:'2026-10-05T12:00', e:'2026-10-06T10:00', t:'Konglehytta 3 · Star View · 私人桑拿（2房/3床/<b>1卫</b>）',
  st:'ok', price:'€306 可退档 ≈ ¥1,224', link:'https://www.airbnb.com/rooms/648419631702172808?check_in=2026-10-05&check_out=2026-10-06&adults=4&currency=EUR',
  note:'★4.98 整栋小木屋。✅ 可退档只比不可退贵 €10 → 直接选可退。🟠 只有 1 个卫生间。<b>先定要不要车③ 再下单</b>'},

/* ===== 10/6 二 · 回家 ===== */
 {lane:'act', s:'2026-10-06T09:00', e:'2026-10-06T10:00', t:'退房 → 开 30 min 回 OSL 还车',
  st:'ok', note:'🟢 10/5 这个缓冲夜的价值：10/6 不用「当天先飞 TOS→OSL 再转洲际」'},
 {lane:'fly', s:'2026-10-06T12:00', e:'2026-10-06T14:00', t:'✈ OSL → 北京（10/6 还是 10/7 未定）',
  st:'tbd', who:'Kevin', note:'🔴 <b>要填。</b>若是 <b>10/7</b> 起飞 → 要加第 13 晚（最省事：Stange 小屋多住一晚 +€306 + 车③ 顺延 +$79）。反过来若确定 10/7，那 10/5 这个缓冲夜就多余了 —— <b>特罗姆瑟住回 4 晚（多一个极光夜）反而更好</b>，值得重比'},
 {lane:'stay', s:'2026-10-06T15:00', e:'2026-10-07T10:00', t:'🅿️ 占位：第 13 晚（只在 10/7 起飞时才需要）',
  st:'tbd', price:'Clarion €193 含税 ≈ ¥772', link:'https://www.booking.com/hotel/no/clarion-oslo-airport.html?checkin=2026-10-06&checkout=2026-10-07&group_adults=4&no_rooms=2&selected_currency=EUR',
  note:'🔴 <b>条件性 —— 钱没计入总账。</b>等 Kevin 的回程日期'},
];

/* ---------- 还要填的东西（页面底部那张表；顺序 = 紧急程度） ---------- */
const TOFILL = [
 {p:'✅ 已解决', what:'~~9/25 OSL→KEF 航班~~ → <b>SK4787 06:15→07:05 已出票</b>', who:'—',
  why:'正好是我算出来的那班 → <b>冰岛取车钟点定了 = 08:00</b>，而且 <b>9/25 白得一整天</b>（已重排）', ev:'携程截图 2026-09-04'},
 {p:'✅ 已解决', what:'~~9/29 KEF→OSL 航班~~ → <b>DY1171 20:05→00:45+1 已订</b>', who:'—',
  why:'也是我算出来的那班 → <b>冰岛还车 18:00 确认合适</b>（缓冲 2h05）。但 00:45 落地这件事从假设变成事实', ev:'携程截图 2026-09-04'},
 {p:'🔴🔴 现在', what:'10/2 WF816 机票 ×4 张（¥1,490 含托运那档）', who:'Steve / Kevin',
  why:'页面写着<b>只剩 6 张</b>，我们要 4 张。卖光 → 整个 10/2 的方案（含车①的还车点）要重排', ev:'携程截图已留档'},
 {p:'🔴🔴 现在', what:'车① EVE→Leknes 3 天 $647', who:'Steve',
  why:'<b>Leknes 异地还车只有 5 个报价</b>（Evenes 22 / 特罗姆瑟 16）—— 四台车里唯一会真的订不着的', ev:'免费取消 → 先锁价零风险'},
 {p:'🔴 这两天', what:'9/27 Guesthouse Birkifell（€504+税）', who:'Steve',
  why:'<b>只剩 1 套</b>，而且它是那一晚最好的', ev:'✅ 免费退到 9/25 + 到店付 = 零风险'},
 {p:'🔴 这两天', what:'冰岛那台车（$326，还在涨）', who:'Steve',
  why:'同一台 Peugeot 2008 4x4 自动 9/3 是 $258、9/4 已 $326（<b>+26%</b>）', ev:'免费取消。⚠️ 取车钟点要等 9/25 航班定'},
 {p:'🟠 等航班', what:'9/25 OSL→KEF 航班时刻', who:'Kevin',
  why:'<b>冰岛取车填几点全看它</b>。唯一直飞 SAS 06:15→07:05 → 取车填 08:00', ev:'Google Flights 实抓'},
 {p:'🟠 等航班', what:'9/29 KEF→OSL 航班', who:'Kevin',
  why:'决定冰岛<b>还车</b>钟点，也决定那晚几点到 Nannestad。最便宜那班 00:45 才落地 → 只睡 5 小时', ev:'两个解法已写在时间线里'},
 {p:'🟠 等航班', what:'10/5 TOS→OSL 航班（建议 Norwegian 08:20）', who:'Kevin',
  why:'车② 还车和车③ 取车都挂在它上面。08:20 那班<b>又早又便宜</b>', ev:'NOK 6,396 vs 10:45 那班 8,396'},
 {p:'🟠 决定', what:'10/5 要不要租车③（$85 / 1 天）', who:'Steve（B5）',
  why:'Stange 小屋房源页写 "A car is required"；不租就换机场旁 Clarion（€193，反而便宜、2 卫）', ev:'两条都可退，不急一小时'},
 {p:'🟠 决定', what:'9/24 那一晚（Nannestad €260，<b>不可退</b>）', who:'Steve',
  why:'不可退 → 等 Kevin 洲际票定了再下单。要弹性换 Thon Gardermoen（退到 9/23）', ev:'房源页已核'},
 {p:'🟠 决定', what:'10/6 还是 10/7 回北京', who:'Kevin',
  why:'决定要不要第 13 晚；<b>若是 10/7，特罗姆瑟住回 4 晚反而更好</b>（多一个极光夜）', ev:'占位已画在时间线最后'},
 {p:'🔴 这两天', what:'🆕 <b>两个奥斯陆中转夜换成机场酒店？</b>（9/24 Thon €214 · 9/29 Clarion €190，都可退）', who:'Steve',
  why:'两夜本质都是「落地→睡几小时→再起飞」，而 Nannestad 在 20 分钟车程外、我们<b>没有车</b>。'+
      '换机场酒店同时省三样：<b>4 趟深夜打车（约 ¥1,340–1,876）· 多睡 40–50 分钟 · 24h 前台不用赌深夜自助入住</b>。'+
      '两晚合计 €404 ≈ ¥3,232（都可退）替掉 Airbnb €552 ≈ ¥4,416（9/24 那套还不可退）+ 打车 → <b>净省约 ¥2,500–3,000</b>',
  ev:'2026-09-04 Booking 物业页实抓：Thon 9/24 €107/间可退到 9/23 · Clarion 9/29 €95/间可退到 9/28 · Clarion 9/24 要 €138/间'},
 {p:'🔴 这两天', what:'🆕 <b>蓝湖时段票 ×4</b>（9/25 上午，KEF 开车 20 min）', who:'Steve',
  why:'SK4787 07:05 落地让 9/25 白得一整天，我把蓝湖从 9/28 那个 520 km 的日子挪到了 9/25 → '+
      '9/28 因此从 6h30 降到约 5h。🔴 但<b>蓝湖是预约时段制，不是随到随进</b>，要单独订', ev:'新排的，还没订'},
 {p:'🟠 确认', what:'🆕 <b>9/30 OSL→EVE 那班到底几点</b>（截图里被裁掉了）', who:'Kevin',
  why:'如果是 08:55 → 前一夜只能睡 6 小时；如果换成同价的 <b>13:20→15:00</b> → 那一夜能睡到 10 小时以上，'+
      '代价是天快黑才进罗弗敦。<b>这一条同时决定车① 的取车钟点</b>（现在按 11:00 排）', ev:'Norwegian 三班同价 NOK 4,196/4 人'},
 {p:'🟠 确认', what:'🆕 <b>三段机票是不是每段都 4 个人齐</b>', who:'Steve',
  why:'截图里三段的出行人名字两两不同（9/24 只显示 LIU/HANGTAO；9/25 是 ZHANG/MINXUAN+WU/QIN…；'+
      '9/29 是 OUYANG/ZHIHAO+LIU/HA…）→ 分了几个订单。<b>任何一段少一个人，车和住的人数都要重算</b>', ev:'逐段点开「订单详情」看出行人'},
 {p:'🟡 出发前', what:'9/24 洲际的<b>落地钟点</b>（截图被裁）', who:'Kevin',
  why:'时间线里 21:30 还是占位值。只影响当晚几点进房 —— 但 SK4787 06:15 起飞意味着 <b>04:30 就得走</b>', ev:'预订号 JP1Y15，9h25'},
 {p:'🟡 出发前', what:'10/4（<b>周日</b>）Senja 渡轮班表', who:'Steve',
  why:'Senja 从 10/5 挪到 10/4，周日班次通常更少', ev:'Torghatten Nord / Entur'},
 {p:'🟡 结账时', what:'冰岛必买三险（SCDW + 砂石 + 火山沙尘）', who:'Steve',
  why:'不在裸车价里，要在结账页加：$451–526 ≈ ¥3,202–3,735（已按最坏计入总账）', ev:'冰岛碎石路 + 10 月南岸沙尘暴是真实索赔项'},
 {p:'🟢 可选', what:'9/25 若 07:05 落地 → 把行程重排一次', who:'我（等票定）',
  why:'白得一整天 → 可以把雷克雅内斯/蓝湖挪到 9/25，给 9/28（520 km / 6h30，全程最长）让位', ev:'需要 Kevin 的票先定'},
];
