/* 后半段行程：时间 + 空间的唯一数据源（10/6 → 10/17，方案 B：周六 10/17 经卡尔加里回）
 *
 * 所有时刻都是**当地时间**，每一天标出自己所在的时区（法国/挪威 UTC+2，葡萄牙/英国 UTC+1）。
 * 工作和例会不是手写的 —— 由 PT 时刻按时区算出来（trip/index.html 里的 workFor / meetFor），
 * 这样改了时区或日期，冲突检查会跟着变。
 *
 * 块的类型：sleep 睡觉 · work 上班 · meet 例会 · fly 航班 · move 城内/去机场的交通 · act 当天唯一的锚点 · opt 可选
 */
const TRIP_TZ = { osl: 2, nice: 2, lis: 1, lon: 1 };
const PT = -7;   // 10 月还是夏令时 PDT
/* 请了假的日子：不生成上班 / 例会块（Steve 9/25：10/6 周二 Adobe 全天请假） */
const PTO = ['10/6'];

/* 锚点坐标（WGS84）。住处坐标由 stays.js 里每城首选提供 */
const POI = {
  osl:  { name: '奥斯陆机场 OSL', ll: [60.1976, 11.1004] },
  nce:  { name: '尼斯机场 NCE', ll: [43.6584, 7.2159] },
  lis_ap: { name: '里斯本机场 LIS', ll: [38.7742, -9.1342] },
  stn:  { name: '斯坦斯特德机场 STN', ll: [51.8860, 0.2389] },
  lhr:  { name: '希思罗机场 LHR', ll: [51.4700, -0.4543] },
  yyc:  { name: '卡尔加里 YYC（转机）', ll: [51.1215, -114.0076] },
  sfo:  { name: '旧金山 SFO', ll: [37.6213, -122.3790] },

  nice_beach: { name: '海滨大道 + 沙滩躺椅', ll: [43.6952, 7.2701] },
  villefranche: { name: 'Villefranche-sur-Mer 小渔村', ll: [43.7040, 7.3110] },
  matisse: { name: '马蒂斯美术馆 + Cimiez 公园', ll: [43.7196, 7.2759] },

  ribeira: { name: 'Ribeira das Naus 河边台阶', ll: [38.7068, -9.1403] },
  timeout: { name: 'Time Out Market', ll: [38.7070, -9.1459] },
  tram28: { name: '28 路电车（Martim Moniz 起点）', ll: [38.7162, -9.1359] },
  alfama: { name: 'Alfama · Santa Luzia 观景台', ll: [38.7118, -9.1300] },
  belem: { name: 'Belém 修道院 + 原版蛋挞', ll: [38.6979, -9.2068] },
  lxf: { name: 'LX Factory', ll: [38.7033, -9.1786] },

  hyde: { name: 'Hyde Park / Kensington Gardens', ll: [51.5096, -0.1757] },
  bm: { name: '大英博物馆', ll: [51.5194, -0.1270] },
  wpier: { name: '威斯敏斯特码头 → 格林威治游船', ll: [51.5016, -0.1234] },
  portobello: { name: 'Portobello 周六市集', ll: [51.5152, -0.2050] },
};

/* 城市之间的四段飞行（地图总览用） */
const LEGS = [
  { from: 'osl', to: 'nce', t: '10/6 二 17:20 → 20:15 · 挪威航空 · 直飞 2h55' },
  { from: 'nce', to: 'lis_ap', t: '10/10 六 12:15 → 14:00 · 葡萄牙航空 · 直飞 2h45' },
  { from: 'lis_ap', to: 'stn', t: '10/14 三 09:40 → 12:25 · 瑞安航空 · 直飞 2h45' },
  { from: 'lhr', to: 'yyc', t: '10/17 六 14:10 起飞 · 西捷航空 · 卡尔加里转机 3h55' },
  { from: 'yyc', to: 'sfo', t: '当地 21:55 落地旧金山（美国入境在卡尔加里就办完）' },
];

/* 一天 = 城市 + 一组块。h 用小数小时（13.5 = 13:30），跨午夜的块写到 24 为止，
 * 次日凌晨那段由下一天的 sleep 接上。act.poi 指向 POI，act.mode 是从住处过去的方式。 */
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
  { d: '10/10', wd: '六', city: 'nice→lis', tz: 1, title: '✈️ 飞里斯本 · 周六晚完全自由',
    note: '这天中途换时区：出发按法国时间，落地后按葡萄牙时间（慢 1 小时）。下面统一按葡萄牙时间画。',
    blocks: [
      { k: 'sleep', a: 0.5, b: 8.5 },
      { k: 'move', a: 9.25, b: 10, t: '住处 → 尼斯机场（2 号线电车，法国时间 10:15 出门）' },
      { k: 'fly', a: 11.25, b: 14, t: 'NCE → LIS 葡萄牙航空（法国 12:15 起飞）' },
      { k: 'move', a: 14, b: 15, t: '机场 → 住处（打车 20 分钟 / 地铁 25 分钟）' },
      { k: 'act', a: 16.5, b: 21, t: '河边台阶看落日 → Time Out Market 晚饭', poi: 'ribeira', mode: '步行' },
    ] },
  { d: '10/11', wd: '日', city: 'lis', tz: 1, title: '🚋 28 路电车 + Alfama',
    blocks: [
      { k: 'sleep', a: 1, b: 9 },
      { k: 'act', a: 10.5, b: 15, t: '28 路电车坐一圈 → Alfama 随便走', poi: 'tram28', mode: '步行 / 电车' },
    ] },
  { d: '10/12', wd: '一', city: 'lis', tz: 1, title: '⛪ Belém 半天',
    blocks: [
      { k: 'sleep', a: 0, b: 8.5 },
      { k: 'act', a: 10, b: 14, t: '热罗尼莫斯修道院 + 原版蛋挞（全是平地）', poi: 'belem', mode: '15 号电车 25 分钟' },
    ] },
  { d: '10/13', wd: '二', city: 'lis', tz: 1, title: '☕ LX Factory · 最轻的一天',
    blocks: [
      { k: 'sleep', a: 0.5, b: 7.5 },
      { k: 'act', a: 10.5, b: 13, t: '院子里的咖啡馆 + 那家书店', poi: 'lxf', mode: '打车 10 分钟' },
    ] },
  { d: '10/14', wd: '三', city: 'lis→lon', tz: 1, title: '✈️ 飞伦敦',
    blocks: [
      { k: 'sleep', a: 0.5, b: 7 },
      { k: 'move', a: 7.5, b: 8, t: '住处 → 里斯本机场（打车 20 分钟）' },
      { k: 'fly', a: 9.67, b: 12.42, t: 'LIS → 伦敦 瑞安航空' },
      { k: 'move', a: 12.42, b: 14.25, t: '斯坦斯特德 → 市区（Stansted Express 47 分钟 + 出机场）' },
      { k: 'act', a: 15, b: 17, t: 'Hyde Park / Kensington Gardens 散步', poi: 'hyde', mode: '步行' },
    ] },
  { d: '10/15', wd: '四', city: 'lon', tz: 1, title: '🏛 只去一个博物馆',
    blocks: [
      { k: 'sleep', a: 0.5, b: 8.5 },
      { k: 'act', a: 11, b: 13.5, t: '大英博物馆（或 V&A），2 小时就走', poi: 'bm', mode: '地铁 20 分钟' },
      { k: 'opt', a: 14.5, b: 17, t: '可选：西区日场戏（周四有 14:30 场）或约朋友午饭' },
    ] },
  { d: '10/16', wd: '五', city: 'lon', tz: 1, title: '⛴ 泰晤士河游船',
    blocks: [
      { k: 'sleep', a: 0.5, b: 7.5 },
      { k: 'act', a: 11, b: 14.5, t: '威斯敏斯特 → 格林威治，坐着看完半个伦敦', poi: 'wpier', mode: '地铁 20 分钟' },
    ] },
  { d: '10/17', wd: '六', city: 'lon→home', tz: 1, title: '🛍 Portobello 市集 → 回家',
    blocks: [
      { k: 'sleep', a: 0.5, b: 8 },
      { k: 'act', a: 9, b: 11, t: 'Portobello 周六市集（一周最热闹的一天）', poi: 'portobello', mode: '地铁 10 分钟' },
      { k: 'move', a: 11.5, b: 12.25, t: 'Paddington → 希思罗（Heathrow Express 15 分钟）' },
      { k: 'fly', a: 14.17, b: 24, t: 'LHR → 卡尔加里 → SFO（旧金山当地 21:55 落地）' },
    ] },
];

/* 体检发现的问题，每条配一个「怎么解」—— 只写已经核实过的选项，决定留给 Steve */
const FIXES = {
  '10/14': '<b>10/14 早班机只睡 6.5 小时</b>：前一晚上班到 24:00，07:30 要出门去机场。飞机上 2h45 可以补觉；'
    + '或者换 <b>13:00 起飞的 easyJet</b>（$97，15:40 落地），但到住处就 17:15 了，离 18:00 开工只剩 45 分钟 —— 我倾向保留早班。',
};
