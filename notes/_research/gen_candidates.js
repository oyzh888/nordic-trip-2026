/* 从 viz/data.js 的 CANDS 生成 notes/CANDIDATES.md（单一真相：data.js）
 * 用法：node notes/_research/gen_candidates.js > notes/CANDIDATES.md
 */
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '../..');
const src = fs.readFileSync(path.join(root, 'viz/data.js'), 'utf8');
const { CANDS, DAYS, STAYTAB } = new Function(src + '; return {CANDS,DAYS,STAYTAB};')();

const fmt = n => n.toLocaleString('en-US');
const V = { ok: '✅ 房源页已核', search: '🟠 仅搜索页', dead: '⛔ 已验证订不到' };
const out = [];
const w = s => out.push(s);

const totStay = DAYS.reduce((a, d) => a + (d.spend && d.spend.stay || 0), 0);
const nights = 12;

w(`# 每晚候选清单 —— 一起选（表格版）

> 🔴 **这份是 [\`viz/index.html\`](../viz/index.html) 第 07 节「候选池」的 Markdown 镜像**，
> 两边同一份数据（\`viz/data.js\` 的 \`CANDS\`）。**网页版能点选并当场重算总账**，
> 这份只是为了能在 git 里 review / 在手机上看。改数字请改 \`data.js\`，
> 然后 \`node notes/_research/gen_candidates.js > notes/CANDIDATES.md\` 重新生成 —— 别手改这个文件。
>
> 🆕 **2026-09-02 傍晚：Steve 自己找的那一套（9/25 → 10/6）已设为默认（🥇），我原来挑的全部降级为备选**（都保留、都标了差价）。
> 8 个链接（6 Airbnb + 2 Booking）2026-09-02 逐个开真实页面验过，全部可订。
>
> **每行都是实价**，2026-09-01 / 09-02 用 Playwright 按我们的真实日期抓的。
> 汇率固定 **€1 = ¥8.0 · NOK 1 = ¥0.67**。
>
> **「实测」列是本文最重要的一列** —— Airbnb 搜索卡片会撒谎：逐个打开房源页后，
> **有 10 个订不到**（「Those dates are not available」或 min-stay 2 晚）。
> \`✅ 房源页已核\` = 打开过房源页、日期真的放房；\`🟠 仅搜索页\` = 只在搜索/列表页见过价，**下单前要自己再点一次**。
>
> **黑话**：**¥/房/晚**（= 整段总价 ÷ 2 房 ÷ 晚数，一律按保守的 ÷2 算；3 房那几晚实际会更低）·
> **min-stay**（房东设的最少入住晚数）· **non-ref**（不可退）· **free-cxl**（免费取消截止日）·
> **VAT**（增值税 —— 🔴 冰岛酒店报价不含 11% + 城市税，**挪威酒店也不含 12%**，下表的 ¥ 都已加过）。

## ✅ 10/5 那个窟窿已经补掉了（2026-09-02 深夜你给的两个链接）

10/5 你给了**奥斯陆一带**的房源（Konglehytta 3，在 Stange）→ 行程改成「10/5 飞回奥斯陆睡缓冲夜」，
于是 **特罗姆瑟按你链接上的 3 晚订、日期一个字都不用改**（省 +€453），车② 从 4 天缩到 3 天（−$103），
9/28 也换成 ★5.0 那套（−€110）。加上小屋 +€306、OSL 一天车 +$86 → **净便宜约 ¥1,400**，
还白得一个防延误的缓冲夜。代价：**极光夜 4 → 3**，且 9/28 与 10/5 **都只有 1 个卫生间**。

## 🔴 还剩一个窟窿 + 一个要你拍板的

| 缺什么 / 要定什么 | 怎么补 |
|---|---|
| **9/24 那一晚** —— 你的清单从 9/25 起 | 沿用我原来的 Nannestad 3房2卫 €260（⛔ 不可退）；想和 9/29 用同一家 5 房那套也行，**但 9/24 的可订性还没验** |
| 🔴 **10/5 那套小屋在 Stange 森林里，不在机场旁** | 房源页写着 "A car is required"（离 OSL 30 min）→ 要么**加租 OSL 一天车（$79–86 ≈ ¥611）**，要么换机场旁 Clarion（€193，2 卫，还更便宜） |
| 🟠 **Senja 从 10/5 挪到 10/4 = 周日** | 我手上时刻表只标了「12:45 周五停」，**周日没单独核过** → 出发前一周核 Torghatten Nord；班少就走陆路 Finnsnes 大桥（+1h） |

## 🟠 两笔差价大到值得再看一眼

| 哪一段 | 你的（默认） | 我原来的（备选） | 差 |
|---|---|---|---:|
| 10/2 → 10/5 特罗姆瑟（3 晚） | Tromsø 4房2卫 €1,526 · 可退到 10/1 | Houseboat "Grosso" ★5.0 · 3房**3卫** · €825 · 可退 | **约 ¥5,600** |
| 9/30 → 10/2 罗弗敦（2 晚） | Vågan 3房5床2卫 €1,136 · ⛔ 不可退 | Waterfront Nordic house ★4.93 · 5房8床2卫 · €553 · 可退 | **¥4,664** |

## 默认组合的总账（网页版的默认选中项）

| | |
|---|---:|
| 住宿合计（${nights} 晚 · 4 人） | **¥${fmt(totStay)}** |
| 折算 | **¥${fmt(Math.round(totStay / nights / 2))} / 房 / 晚** |
| 你的预算 | ¥2,000–4,000 / 房 |
| 结论 | ✅ 仍在区间下沿内（我原来那套是 ¥1,326，便宜约 ¥1.1 万 —— 两套都在预算内） |
| 条件性的 10/6 那一晚（未计入，等 Kevin 机票） | ¥1,544 |

---`);

for (const g of CANDS) {
  w(`\n## ${g.d} · ${g.place}${g.n > 1 && !g.d.includes('晚') ? `（${g.n} 晚）` : ''}\n`);
  if (g.note) w(`> ${g.note}\n`);
  w('| | 住哪 | 房/卫 | 报价 | **¥/房/晚** | 评分 | 退改 | 实测 | 位置 |');
  w('|---|---|---|---|---:|---|---|---|---|');
  for (const o of g.opts) {
    const mark = o.t === 'pick' ? '🥇' : o.t === 'dead' ? '⛔' : '';
    const name = o.t === 'dead' ? `~~${o.n}~~` : `[${o.n}](${o.u})`;
    const room = o.t === 'dead' ? '—' : `**¥${fmt(o.room)}**`;
    w(`| ${mark} | ${name} | ${o.rb} | ${o.p} | ${room} | ${o.r || '—'} | ${o.cxl || '—'} | ${V[o.v] || o.v} | ${o.loc} |`);
  }
  w('');
  for (const o of g.opts) w(`- **${o.n}** — ${o.why}`);
}

w(`\n---\n\n*本文件由 \`notes/_research/gen_candidates.js\` 从 \`viz/data.js\` 生成 —— 不要手改。*`);
console.log(out.join('\n'));
