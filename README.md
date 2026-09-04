# 北欧 2026 · 13 天行程规划

**2026-09-24 → 10-06 · 4 人（两男 + 一对夫妻）· 奥斯陆 → 冰岛 → 罗弗敦 → 特罗姆瑟/Senja → 奥斯陆**

12 晚住宿 + 4 台租车，**全部有实价、全部实测可订**：
住宿 **€5,132 ≈ ¥41,055**（¥1,711/房/晚）· 车 **¥10,338** → **合计 ≈ ¥57,059，人均 ¥14,265**
（不含跨国机票 / 餐饮 / 门票·tour）。9/30–10/2 罗弗敦那一段 **Steve 已下单**。

> **这个 repo 的价格不是估的。** 每一个数字都是 2026-09-01/02 用 Playwright 打开
> Booking / Airbnb / DiscoverCars / Google Flights / Hurtigruten 的**真实页面、按我们真实日期**
> 抓下来的，原始 JSON 和截图都在 `notes/_research/`（见那里的 [`INDEX.md`](notes/_research/INDEX.md)）。
>
> **汇率全项目固定**：`€1 = ¥8.0` · `$1 = ¥7.1` · `NOK 1 = ¥0.67`。改汇率会让所有文档互相矛盾。

---

## 先看哪个 —— 四个网页版（都已发布，公网可开）

| 版本 | 干什么用 | 链接 |
|---|---|---|
| 🥇 **计划总览** | **要 confirm 就看这个。** 分 Part I 总览 / Part II 参考；候选可点选、总账当场重算 | <https://reports.aitist.ai/nordic-trip-2026/plan/> |
| 🗺️ **行程地图** | 逐日路线 + 里程 | <https://reports.aitist.ai/nordic-trip-2026/trip-map/> |
| 🎬 **故事页** | 电影感长卷，真实房源照 + 风光图（给同行的人看） | <https://reports.aitist.ai/nordic-trip-2026/journey-north/> |
| 🎨 **四个风格版** | 故事页的四种排版，挑一个 | <https://reports.aitist.ai/nordic-trip-2026/styles/> |

重新发布：`report publish viz --namespace nordic-trip-2026 --slug plan --update`

---

## 目录结构

```
viz/       ← 🥇 计划总览页（index.html + data.js）—— 唯一的「决策页面」
story/     ← 故事页（电影感长卷）
styles/    ← 故事页的四个风格变体 + 共用 core.js
notes/     ← 所有 Markdown 文档（结论）
  shots/       ← 14 张精选截图，PLAN-final §八 逐一引用
  _research/   ← 🔬 全部原始证据，763 个文件：261 张截图 + 378 JSON + 40 抓取脚本（见 INDEX.md）
```

### `notes/` 里 9 份文档各自的定位

| 文档 | 是什么 | 什么时候读 |
|---|---|---|
| 🥇 [`PLAN-final.md`](notes/PLAN-final.md) | **最终方案**（总/分两层，§一·二·五 看完就够） | **默认入口** |
| [`CANDIDATES.md`](notes/CANDIDATES.md) | 每晚 3–10 个候选 · ⚠️ **自动生成，别手改**（`node notes/_research/gen_candidates.js`） | 想换住哪 |
| [`PLAN-booking.md`](notes/PLAN-booking.md) | **下单顺序**，按「谁会先卖光」排 | 准备真的付钱 |
| [`ICELAND-oneway.md`](notes/ICELAND-oneway.md) | 冰岛能不能「不回头」—— 3 个方案实价对比 | 觉得冰岛在走回头路 |
| [`OPTIONS-cars.md`](notes/OPTIONS-cars.md) | 三段自驾的实时报价池 | 想换车/换档位 |
| [`OPTIONS-cars-split.md`](notes/OPTIONS-cars-split.md) | 「同地租 N 天 + 最后 1 天异地」到底划不划算 | 想省异地还车费 |
| [`OPTIONS-stay.md`](notes/OPTIONS-stay.md) | 住宿候选池（⚠️ 开头列了 3 处已修正的错） | 追查某晚为什么这么选 |
| [`OPTIONS-cruise.md`](notes/OPTIONS-cruise.md) | Svolvær→Tromsø 邮轮舱位（**最稀缺**，卖光整段断掉） | 邮轮那一段 |
| [`CHANGES-0929-1002.md`](notes/CHANGES-0929-1002.md) | 9/29 减负 + 10/2 改飞的改动记录 | 想知道为什么改过 |

**结论在 `notes/*.md`，证据在 `notes/_research/`。** 两者都要在 repo 里 ——
2026 年 9 月这些报价过了出发日就再也抓不回来，删掉证据文档就从「实抓」退化成「据说」。

---

## ⚠️ 已知的一处结构隐患

`viz/data.js`（946 行）· `story/data.js`（1,219 行）· `styles/data.js`（1,451 行）
是**三份各自独立的数据层**，内容不同、没有共享来源。
→ **改一个预订，要改三个文件**；漏改一个就会出现三个页面说法不一致。

`story/` 和 `styles/` 的那两份是 `notes/_research/build_story.py` / `build_styles.py` **生成的**，
`viz/data.js` 是手写的。**出发前不动它**（21 天内重构风险大于收益）；
真要统一，方向是把 `viz/data.js` 提成唯一真相、另两份都由脚本生成。

---

## 重跑任何一次抓取

```bash
cd notes/_research
python3 bk_prop.py    jobs_west.json    out_west/       # Booking 房型行
python3 dc_direct.py  jobs_oneway.json  out_oneway/     # DiscoverCars 报价
python3 flights_isdom.py jobs_...       out_isdom/      # Google Flights
```

需要 Playwright + Chromium 且能出网。哪个脚本配哪组 job、每组在回答什么问题，
全部写在 [`notes/_research/INDEX.md`](notes/_research/INDEX.md)。
