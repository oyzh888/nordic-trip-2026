/* 后半段行程：时间 + 空间的唯一数据源（10/6 → 10/17）
 *
 * 🆕 2026-09-25 方案 C：尼斯 4 晚 → 伦敦 3 晚（正好是周末）→ 里斯本 4 晚 → 10/17 周六里斯本直飞 SFO。
 *   为什么换顺序：加拿大转机那条对 Steve 不可行；周六能直飞回湾区的只有里斯本（葡萄牙航空 12h25）。
 *   顺带的好处：伦敦赶上周末（西区夜场、见朋友都回来了），里斯本变成工作日、Airbnb 便宜将近一半。
 *
 * 所有时刻都是**当地时间**（法国/挪威 UTC+2，英国/葡萄牙 UTC+1 —— 伦敦和里斯本同一个时区）。
 * 上班和例会不是手写的 —— 由 PT 时刻按时区算（trip/index.html 里），PTO 里的日子跳过。
 *
 * 块的类型：sleep 睡觉 · move 城内/去机场 · fly 航班 · act 当天唯一的锚点 · opt 可选
 */
const TRIP_TZ = { osl: 2, nice: 2, lon: 1, lis: 1 };
const PT = -7;   // 10 月还是夏令时 PDT
/* 请了假的日子：不生成上班 / 例会块（Steve 9/25：10/6 周二 Adobe 全天请假） */
const PTO = ['10/6'];

/* 锚点坐标（WGS84）。住处坐标由 stays.js 里每城首选提供 */
const POI = {
  osl:  { name: '奥斯陆机场 OSL', ll: [60.1976, 11.1004] },
  nce:  { name: '尼斯机场 NCE', ll: [43.6584, 7.2159] },
  lhr:  { name: '希思罗机场 LHR', ll: [51.4700, -0.4543] },
  ltn:  { name: '卢顿机场 LTN', ll: [51.8747, -0.3683] },
  lis_ap: { name: '里斯本机场 LIS', ll: [38.7742, -9.1342] },
  sfo:  { name: '旧金山 SFO', ll: [37.6213, -122.3790] },

  nice_beach: { name: '海滨大道 + 沙滩躺椅', ll: [43.6952, 7.2701] },
  villefranche: { name: 'Villefranche-sur-Mer 小渔村', ll: [43.7040, 7.3110] },
  matisse: { name: '马蒂斯美术馆 + Cimiez 公园', ll: [43.7196, 7.2759] },

  westend: { name: '西区看戏（Leicester Square 一带）', ll: [51.5103, -0.1300] },
  portobello: { name: 'Portobello 周六市集', ll: [51.5152, -0.2050] },
  wpier: { name: '威斯敏斯特码头 → 格林威治游船', ll: [51.5016, -0.1234] },
  bm: { name: '大英博物馆', ll: [51.5194, -0.1270] },

  ribeira: { name: 'Ribeira das Naus 河边台阶', ll: [38.7068, -9.1403] },
  tram28: { name: '28 路电车（Martim Moniz 起点）→ Alfama', ll: [38.7162, -9.1359] },
  belem: { name: 'Belém 修道院 + 原版蛋挞', ll: [38.6979, -9.2068] },
  lxf: { name: 'LX Factory', ll: [38.7033, -9.1786] },
};

/* 城市之间的四段飞行（地图总览用）。toSfo = 往地图外画箭头 */
const LEGS = [
  { from: 'osl', to: 'nce', t: '10/6 二 17:20 → 20:15 · 挪威航空 · 直飞 2h55' },
  { from: 'nce', to: 'lhr', t: '10/10 六 11:35 → 12:50 · 英国航空 · 直飞 2h15' },
  { from: 'ltn', to: 'lis_ap', t: '10/13 二 12:15 → 15:10 · 卢顿出发 · 直飞 2h55' },
  { from: 'lis_ap', to: 'sfo', toSfo: true, t: '10/17 六 13:10 → 17:35 · 葡萄牙航空 · 直飞 12h25' },
];
const STOPS = [['osl', '奥斯陆'], ['nce', '尼斯 4 晚'], ['lhr', '伦敦 3 晚（周末）'], ['lis_ap', '里斯本 4 晚']];

/* 一天 = 城市 + 一组块。h 用小数小时（13.5 = 13:30）。act.poi 指向 POI，act.mode 是从住处过去的方式。 */
const TDAYS = [
  { d: '10/6', wd: '二', city: 'osl→nice', tz: 2, title: '奥斯陆道别 → 飞尼斯（请假日）',
    blocks: [
      { k: 'sleep', a: 0, b: 7.5 },
      { k: 'act', a: 11.5, b: 13, t: '和大家在奥斯陆机场还车 → 道别', poi: 'osl' },
      { k: 'fly', a: 17.33, b: 20.25, t: 'OSL → NCE 挪威航空' },
      { k: 'move', a: 20.25, b: 21.25, t: '机场 → 住处（2 号线电车 25 分钟 / 打车 20 分钟）' },
    ] },
  { d: '10/7', wd: '三', city: 'nice', tz: 2, title: '🏖 海边躺平日',
    blocks: [
      { k: 'sleep', a: 1.5, b: 9.5 },
      { k: 'act', a: 11, b: 16.5, t: '海滨大道走一段 → 沙滩躺椅（海水 20–21°C）', poi: 'nice_beach', mode: '步行' },
    ] },
  { d: '10/8', wd: '四', city: 'nice', tz: 2, title: '🚂 Villefranche 小渔村',
    blocks: [
      { k: 'sleep', a: 1.5, b: 9.5 },
      { k: 'act', a: 11, b: 16, t: '火车 7 分钟 → 彩色老街 + 沙滩，在那吃午饭', poi: 'villefranche', mode: 'TER 火车 7 分钟' },
    ] },
  { d: '10/9', wd: '五', city: 'nice', tz: 2, title: '🎨 马蒂斯美术馆 · 最轻的一天',
    blocks: [
      { k: 'sleep', a: 1.5, b: 8.5 },
      { k: 'act', a: 12, b: 15, t: '马蒂斯美术馆（1 小时）+ 橄榄树公园长椅', poi: 'matisse', mode: '公交 15 分钟' },
    ] },
  { d: '10/10', wd: '六', city: 'nice→lon', tz: 1, title: '✈️ 飞伦敦 · 周六晚看西区',
    note: '这天中途换时区：出发按法国时间，落地后按英国时间（慢 1 小时）。下面统一按英国时间画。',
    blocks: [
      { k: 'sleep', a: 0.5, b: 7.5 },
      { k: 'move', a: 8.25, b: 9, t: '住处 → 尼斯机场（2 号线电车，法国时间 09:15 出门）' },
      { k: 'fly', a: 10.58, b: 12.83, t: 'NCE → LHR 英国航空（法国 11:35 起飞）' },
      { k: 'move', a: 12.83, b: 14, t: '希思罗 → Paddington（Heathrow Express 15 分钟 + 出机场）' },
      { k: 'opt', a: 15, b: 17, t: '可选：Portobello 周六市集（周六是它一周最热闹的一天）' },
      { k: 'act', a: 19.5, b: 22, t: '🎭 西区看戏（周六夜场）', poi: 'westend', mode: '地铁 15 分钟' },
    ] },
  { d: '10/11', wd: '日', city: 'lon', tz: 1, title: '⛴ 泰晤士河游船 + 见朋友',
    blocks: [
      { k: 'sleep', a: 0, b: 9 },
      { k: 'act', a: 11, b: 14.5, t: '威斯敏斯特 → 格林威治，坐着看完半个伦敦', poi: 'wpier', mode: '地铁 20 分钟' },
      { k: 'opt', a: 17, b: 20, t: '可选：和朋友吃晚饭（21:30 有会，之前回来）' },
    ] },
  { d: '10/12', wd: '一', city: 'lon', tz: 1, title: '🏛 只去一个博物馆',
    blocks: [
      { k: 'sleep', a: 0, b: 8.5 },
      { k: 'act', a: 11, b: 13.5, t: '大英博物馆（或 V&A），2 小时就走', poi: 'bm', mode: '地铁 20 分钟' },
    ] },
  { d: '10/13', wd: '二', city: 'lon→lis', tz: 1, title: '✈️ 开完会飞里斯本',
    note: '伦敦和里斯本同一个时区，这天不用换表。',
    blocks: [
      { k: 'sleep', a: 0.5, b: 7.5 },
      { k: 'move', a: 10.25, b: 11.25, t: '住处 → 卢顿机场（火车 + 接驳巴士约 1 小时）' },
      { k: 'fly', a: 12.25, b: 15.17, t: 'LTN → LIS 直飞' },
      { k: 'move', a: 15.17, b: 16, t: '里斯本机场 → 住处（打车 20 分钟）' },
    ] },
  { d: '10/14', wd: '三', city: 'lis', tz: 1, title: '🚋 28 路电车 + Alfama',
    blocks: [
      { k: 'sleep', a: 0.5, b: 8.5 },
      { k: 'act', a: 10.5, b: 15, t: '28 路电车坐一圈 → Alfama 随便走', poi: 'tram28', mode: '步行 / 电车' },
    ] },
  { d: '10/15', wd: '四', city: 'lis', tz: 1, title: '⛪ Belém 半天',
    blocks: [
      { k: 'sleep', a: 0.5, b: 8.5 },
      { k: 'act', a: 10, b: 14, t: '热罗尼莫斯修道院 + 原版蛋挞（全是平地）', poi: 'belem', mode: '15 号电车 25 分钟' },
    ] },
  { d: '10/16', wd: '五', city: 'lis', tz: 1, title: '☕ LX Factory · 最轻的一天',
    blocks: [
      { k: 'sleep', a: 0.5, b: 7.5 },
      { k: 'act', a: 10.5, b: 13, t: '院子里的咖啡馆 + 那家书店', poi: 'lxf', mode: '打车 10 分钟' },
    ] },
  { d: '10/17', wd: '六', city: 'lis→home', tz: 1, title: '🪑 河边早午饭 → 直飞回家',
    blocks: [
      { k: 'sleep', a: 0.5, b: 8.5 },
      { k: 'act', a: 9.25, b: 10.75, t: 'Ribeira das Naus 河边台阶 + 早午饭', poi: 'ribeira', mode: '步行' },
      { k: 'move', a: 11, b: 11.5, t: '住处 → 里斯本机场（打车 20 分钟）' },
      { k: 'fly', a: 13.17, b: 24, t: 'LIS → SFO 葡萄牙航空直飞（旧金山当地 17:35 落地）' },
    ] },
];

/* 体检发现的问题配「怎么解」—— 只写核实过的选项 */
const FIXES = {};
