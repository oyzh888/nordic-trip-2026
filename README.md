# 北欧 2026 · 13 天行程规划

## 🌐 官网：**<https://nordic.airacle.com>**

四页，一套统一的设计（暖黑 + 象牙白 + 极光青）：
**[首页](https://nordic.airacle.com/)** · **[逐日](https://nordic.airacle.com/days/)** ·
**[最终方案](https://nordic.airacle.com/plan/)**（甘特图 + 自动体检 + 账单）·
**[四台车](https://nordic.airacle.com/cars/)**

源码在 `site/`，数据层 `site/data.js` **自动生成**（`python3 notes/_research/build_site.py`）——
它把三处真相合并成一份：`viz/timeline.js`（时刻/已订/待办）· `styles/data.js`（文案/风光图）·
`notes/_research/out_cars_imgs.json`（四台车的 CC 授权照片）。**别手改 `site/data.js`。**
部署：`wrangler deploy`（配置见 `wrangler.jsonc`）。

**2026-09-24 → 10-06 · 4 人（两男 + 一对夫妻）· 奥斯陆 → 冰岛 → 罗弗敦 → 特罗姆瑟/Senja → 奥斯陆**

12 晚住宿 + 4 台租车，**全部有实价、全部实测可订**。
**合计 ≈ ¥71,400 · 人均 ¥17,850**（不含跨国机票 / 餐饮 / 门票·tour）。
**四段租车已于 2026-09-06 全部下单**；9/30–10/2 罗弗敦住宿已订；9/24 洲际 · 9/25 SK4787 · 9/29 DY1171 **三段机票已出票**。

> ## 🥇 要下单就看 [`BUY.md`](BUY.md)
> 那是一份**可执行的采购清单**（给操作浏览器的 agent 用）：买什么 · 在哪买 ·
> 怎么在页面上认出正确的那一个 · 期望价 · 退改条件 · **什么情况下不许买**。
> 租车是重点（四条已验证的 DiscoverCars 深链，点开就是我们的日期地点）。

> ## 🔴 口径：**不省钱，要舒服、要顺**（2026-09-05 Steve 明确）
> 「合理就可以花。」所有原来靠「便宜多少」挑出来的选择都已按舒适重排（7 处翻转，
> 每条都写清「多花多少 / 换到了什么」），见 [`notes/PLAN-final.md`](notes/PLAN-final.md) 开头那张表。
> 总账因此从 ¥57,851 → ¥65,700，副产品是**全程「不可退」项归零**。

> **这个 repo 的价格不是估的。** 每一个数字都是 2026-09-01 → 09-06 用 Playwright 打开
> Booking / Airbnb / DiscoverCars / Google Flights 的**真实页面、按我们真实日期**
> 抓下来的，原始 JSON 和截图都在 `notes/_research/`（见那里的 [`INDEX.md`](notes/_research/INDEX.md)）。
>
> **汇率全项目固定**：`€1 = ¥8.0` · `$1 = ¥7.1` · `NOK 1 = ¥0.67`。改汇率会让所有文档互相矛盾。
>
> 🔒 **这是公开仓库 —— 预订号（PNR）、同行人姓名、账号、付款信息一律不写进来。**

---

## 先看哪个 —— 四个网页版（都已发布，公网可开）

| 版本 | 干什么用 | 链接 |
|---|---|---|
| 🥇 **计划总览** | **要 confirm 就看这个。** 分 Part I 总览 / Part II 参考；候选可点选、总账当场重算 | <https://reports.aitist.ai/nordic-trip-2026/plan/> |
| 🆕 ⏱ **时间线（甘特图）** | 按时间从上往下看，住宿/车/航班画成覆盖时间范围的横条；**页面自己体检**「每一夜有没有地方睡 / 落地到取车等多久 / 还车到起飞够不够 / 要移动时有没有车」，并列出还要填的 22 项 | <https://reports.aitist.ai/nordic-trip-2026/timeline/> |
| 🗺️ **行程地图** | 逐日路线 + 里程 | <https://reports.aitist.ai/nordic-trip-2026/trip-map/> |
| 🎬 **故事页** | 电影感长卷，真实房源照 + 风光图（给同行的人看） | <https://reports.aitist.ai/nordic-trip-2026/journey-north/> |
| 🎨 **四个风格版** | 故事页的四种排版，挑一个 | <https://reports.aitist.ai/nordic-trip-2026/styles/> |

重新发布：`report publish viz --namespace nordic-trip-2026 --slug plan --update`

---

## 目录结构

```
BUY.md     ← 🥇 采购清单（下单指令，给 agent 用）
viz/       ← 计划总览页（index.html + data.js）+ 🆕 时间线甘特图（timeline.html + timeline.js）
story/     ← 故事页（电影感长卷）
styles/    ← 故事页的四个风格变体 + 共用 core.js
notes/     ← 所有 Markdown 文档（结论）
  shots/       ← 14 张精选截图，PLAN-final §八 逐一引用
  _research/   ← 🔬 全部原始证据，916 个文件：306 张截图 + 459 JSON + 46 抓取脚本（见 INDEX.md）
```

### `notes/` 里 10 份文档各自的定位

| 文档 | 是什么 | 什么时候读 |
|---|---|---|
| 🥇 [`../BUY.md`](BUY.md) | **采购清单** —— 唯一的「下单」文档，其余都是推导 | **真的要付钱时** |
| 🥇 [`PLAN-final.md`](notes/PLAN-final.md) | **最终方案**（总/分两层，§一·二·五 看完就够） | **默认入口** |
| [`CANDIDATES.md`](notes/CANDIDATES.md) | 每晚 3–10 个候选 · ⚠️ **自动生成，别手改**（`node notes/_research/gen_candidates.js`） | 想换住哪 |
| [`PLAN-booking.md`](notes/PLAN-booking.md) | **下单顺序**，按「谁会先卖光」排 | 准备真的付钱 |
| [`ICELAND-oneway.md`](notes/ICELAND-oneway.md) | 冰岛能不能「不回头」—— 3 个方案实价对比 | 觉得冰岛在走回头路 |
| [`SOLO-after-oslo.md`](notes/SOLO-after-oslo.md) | **Steve 一个人的后半段**：10/6 奥斯陆分手 → 尼斯/伦敦 → 回 SFO。⚠️ 单人 USD 口径 | 大家回北京、他不回 |
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

---

## 🌐 官网是怎么部署的（nordic.airacle.com）

**Worker + 静态资源，不是 Cloudflare Pages。**
原因：这个账号的 **Pages 项目数已经到上限**（建新项目直接报 `code 8000027`），
而删掉别的站点来腾位置不可接受。Worker 带静态资源是官方现在推荐的静态站做法，
配额独立（该账号 40 个 worker，有余量），能力也够用 —— 目录直出、
自动把 `/plan/` 映射到 `/plan/index.html`、自带 CDN 与边缘证书。

```bash
python3 notes/_research/build_site.py     # 重新生成 site/data.js
wrangler deploy                            # 部署（wrangler.jsonc 里已绑好自定义域名）
```

`routes` 里写了 `{"pattern":"nordic.airacle.com","custom_domain":true}`，
所以 **DNS 记录和证书都是 wrangler 自动建的**，不用手工加 CNAME。

### 图片版权
- **风光图（271 张）+ 四台车**：Wikimedia Commons，**CC BY / CC BY-SA**，页面上逐张署名（作者 + 许可 + 原页链接）。
  车图是 `notes/_research/wm_cars.py` 用 MediaWiki API 抓的，脚本**会主动丢掉非自由许可**的图。
  ⚠️ 车图是**同款车型示意，不是我们那台的实车照**，页面上已注明。
- **住宿照**：Airbnb / Booking 房源页（热链）。这些是版权图，仅作行前参考。

### ⚠️ 文案覆盖层（别删）
`styles/data.js` 的逐日文案写于 9-02，之后行程改过两轮（9-04 蓝湖/半岛挪到 9/25；
9-05 两个奥斯陆中转夜改机场连廊酒店）。`build_site.py` 里有一个 `OVERRIDE_DAYS` / `OVERRIDE_ACTS`
把 **6 处旧描写**改掉了 —— 否则官网会出现「页面说往西开十五分钟到农舍、账单写着机场酒店」这种自相矛盾。
覆盖表里的日期若和上游对不上，脚本会**直接报错退出**，不会静默漏改。
