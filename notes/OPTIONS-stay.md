# 住宿候选清单 —— 3房2卫（最优）/ 2房2卫（次优）

> # 🔴🔴 这是**候选池**，不是方案。最终方案看 [`PLAN-final.md`](PLAN-final.md)
>
> 本文有 **3 处已确认的错误**，2026-09-01 复核后修正如下 —— 引用本文任何数字前先读这三条：
>
> **① 酒店那些 `€`/`$` 是「每间每晚」，不是「两间总价」。**
> 所以本文所有酒店行的 `¥/room` **都要 ×2 重读**（例：D3 的 "€508 = ¥2,032/room"
> 实际是 **¥4,064/room**，已超预算）。三条证据：`no_rooms=1` 与 `no_rooms=2` 抓回的数字完全一样；
> 截图里明写 "1 room / We have 1 left / 住 2 人"；Árnanes 的 Select Rooms 下拉框写着
> **1 → €276、2 → €553**。
>
> **② 冰岛酒店报价不含税** —— 页面写 "Excluded: 11 % VAT, ISK 800 / €6 City tax per night"。
> 真实支出比表里高约 **11%+**。
>
> **③ 两个 🥇 首选其实订不到**（搜索页有价、房源页不可用，已截图存证）：
> D2 的 **Hlíðarból €750** 和 D6–D7 东侧的 **Vågan 5BR €674** 都是
> "Those dates are not available"。**已找到更好的替代，见 `PLAN-final.md`。**
> 教训：Airbnb 搜索卡片不可信，必须逐个打开房源页复核（`_research/abnb_detail.py`）。

> **数据来源**：2026-09-01 用 Playwright 实时抓的 **Airbnb**（已在 URL 里强制
> `min_bedrooms≥2 & min_bathrooms≥2 & 整套房源`，并用**经纬度框**锁死地理范围，
> 避免 Airbnb 把「Vík」搜成 2.5 小时外的 Selfoss）+ **Booking.com 房型页**（酒店/rorbu 的真实房价行）。
> 汇率按 **€1 = ¥8.0**。4 人 = 两男 + 一对夫妻 → 表里「¥/room」= 整套总价 ÷ 2。
>
> **黑话**：**rorbu**（罗弗敦传统红色渔屋改的自炊小屋）· **min-stay**（房东设的最少入住晚数，
> 比你要住的天数长就订不了）· **free-cxl**（可免费取消的截止日期）。

---

## ⚠️ 先说三条会改变决策的发现

### 1. 冰河湖那一晚（9/27）**Airbnb 里 0 个** 符合 2房2卫的整套房源
搜索范围覆盖 Höfn–Jökulsárlón–Skaftafell 一带，返回 **0 张卡**。
→ **这一晚只能是「酒店 + 2 间房」**（2 间房自动 = 2 个卫生间）。这是全程唯一没有 Airbnb 方案的一晚，
也是最该今天就下单的一晚。

### 2. Borgarnes（西部，为斯奈山半岛做跳板）**1 晚订不到**
Borgarnes 一带 8 个 2房2卫房源里，**全部 min-stay ≥ 2 晚**。
→ 「D4 改住 Borgarnes 省 1.5 小时车程」这个方案 **在 Airbnb 上不可执行**（除非白买一晚）。
**所以 9/28 实际只能住 Keflavík 一带** → 斯奈山必须靠**早出发**解决，见下面第 3 条。

### 3. 关于你问的「那天早点出发是不是时间就够了」→ **够，但有一个前提**

从 **Keflavík 05:30 出发**跑斯奈山半岛（不含 Stykkishólmur）：

| 段 | 车程 |
|---|---|
| Keflavík → Ytri-Tunga 海豹滩 | 2h45 |
| 半岛环线（Arnarstapi / Djúpalónssandur / Kirkjufell 草帽山 / Búðakirkja 黑教堂） | ~3h 净开车 + 3h 停留 |
| 回 KEF 还车 | 2h |
| **合计** | **约 7.5h 开车 + 3–4h 游玩 ≈ 11–12 小时的一天** |

→ **05:30 出发，18:00–18:30 回到 KEF 还车。**

🔴 **唯一的前提：Kevin 订的 KEF→OSL 是几点起飞。**
- 傍晚航班常见时刻是 **~18:35（Norwegian / SAS）** 和 **~20:05（Norwegian）**。
- **如果是 18:35 → 这个环线做不了**（要 16:00 前回 KEF，等于只能玩 1 小时）。
- **如果是 20:05 → 可以做**，18:15 还车、19:00 到柜台，刚好。

**请先跟 Kevin 确认航班号和起飞时间，这一条决定 9/29 到底能不能去斯奈山。**
（10/5 特罗姆瑟日出 07:25 / 日落 18:15；9/29 冰岛日落约 19:00 —— 半岛最后一段会在暮色里开，
路是 54/574 号铺装公路，不难，但要算进去。）

---

## 一、逐晚候选（🥇 = 我推荐的第一顺位）

### D0 · 9/24（四）Oslo Gardermoen —— 落地就睡，只求近

| 房源 | 房/卫 | 总价 | ¥/room | 评分 | 位置 | 备注 |
|---|---|---|---|---|---|---|
| 🥇 [Modern. Quiet area. Large space.](https://www.airbnb.com/rooms/1616864516592253636) | **3BR / 2BA** | €260 | **¥1,040** | — | Nannestad | **唯一能订 1 晚的 3房2卫**，性价比碾压 |
| [A cozy house near Gardermoen](https://www.airbnb.com/rooms/1517311976763731826) | 3BR / 2BA | €426 / **2晚** | ¥1,704/晚 | 5.0 | Eidsvoll | ⚠️ min-stay 2 晚 |
| [Central Jessheim - 10 min from OSL](https://www.airbnb.com/rooms/1739223395983398156) | 4BR / 2BA | €759 / **2晚** | ¥1,518/晚 | 5.0 | Ullensaker | ⚠️ min-stay 2 晚 |
| [Semi-detached house](https://www.airbnb.com/rooms/955510432915478016) | 2BR / 2BA | €503 / **2晚** | ¥1,006/晚 | 5.0 | Gjerdrum | ⚠️ min-stay 2 晚 |
| **酒店兜底**：**Thon Hotel Gardermoen** | 2 间房 | **€86–140/间** · free-cxl 到 9/23 | **¥688–1,120** | — | 机场旁 | **全程最便宜的 2 卫方案** |
| **酒店兜底**：Clarion Hotel Oslo Airport | 2 间房 | €108–126/间 · free-cxl 到 9/23 | ¥864–1,008 | — | 机场旁 | 2 间房 = 2 卫，最省心 |
| **酒店兜底**：Park Inn Oslo Airport | 2 间房 | €212–552 · free-cxl 到当天 18:00 | — | — | 机场旁 | 19 个房型行有货 |

### D1 · 9/25（五）Reykjavík —— 选项最多的一晚

| 房源 | 房/卫 | 总价 | ¥/room | 评分 | 位置 |
|---|---|---|---|---|---|
| 🥇 [Aurora view 3BR 2BATH Luxury down town](https://www.airbnb.com/rooms/1729852848905770040) | **3BR / 2BA** | €447 | **¥1,788** | **5.0** | 雷市市中心 |
| [3BR 2BA](https://www.airbnb.com/rooms/1329176066208833432) | 3BR / 2BA | €337 | ¥1,348 | — | Garðabær（市区南 15 min） |
| [Huge Apartment - Best Location](https://www.airbnb.com/rooms/1164355089969462702) | 4BR / 2BA | €535 | ¥2,140 | 4.87 | 雷市市中心 |
| [Mani Apartments - Four Bedroom](https://www.airbnb.com/rooms/639631862185278229) | 4BR / **3BA** | €962 | ¥3,848 | 4.51 | 雷市 |
| [Tower Apartments - Sóley](https://www.airbnb.com/rooms/35826875) | 2BR / 2BA | €677 | ¥2,708 | 4.9 | 雷市 |

### D2 · 9/26（六）南岸（Vík / Hvolsvöllur）—— **只有 3 个选项，供给很紧**

Vík 镇内 **0 个** 2房2卫整套房源。最近的都在 **Hvolsvöllur**（Vík 西 1h15，但正好在
塞里雅兰瀑布 / 斯科加瀑布中间，如果第二天要往东走冰河湖，会多 1h15 回头路）。

| 房源 | 房/卫 | 总价 | ¥/room | 评分 | 位置 |
|---|---|---|---|---|---|
| ⛔ ~~[Hlíðarból Guest House](https://www.airbnb.com/rooms/1554437248972293986)~~ | 5BR / 2BA | ~~€750~~ | — | 4.64 | Hvolsvöllur ｜🔴 **房源页日期不可用，订不了** |
| ⛔ ~~[Apartment with balcony](https://www.airbnb.com/rooms/1015723380120240614)~~ | 4BR / 2BA | ~~€900~~ | — | 4.76 | Hvolsvöllur ｜🔴 **同样不可用** |
| [4BR/2BA](https://www.airbnb.com/rooms/1081195144537663933) | 4BR / 2BA | €2,089 / 2晚 | ¥4,178/晚 | 4.8 | Hvolsvöllur ⚠️ min-stay 2 晚 |

👉 **如果 D3 改成 Katla 冰洞（Vík 出发，全年开）**，住 Hvolsvöllur 就要早起多开 1h15。
建议这一晚考虑 **Vík 的酒店 2 间房**（Hótel Vík í Mýrdal / Hótel Katla）作为替代 —— 待下一轮抓。

### D3 · 9/27（日）冰河湖 Jökulsárlón —— 🔴 **只有酒店，2 间房**

| 酒店 | 房型 | 2 间房总价 | ¥/room | free-cxl |
|---|---|---|---|---|
| ⛔ Fosshotel Glacier Lagoon | Standard Double/Twin | **€508/间**，且**只剩 1 间** → 2 间 €1,067 含税 €1,194 | **¥4,776** 超预算 | 到 9/25 |
| Fosshotel Glacier Lagoon | Ocean View Double | €582 | ¥2,328 | 到 9/25 |
| Fosshotel Glacier Lagoon | Executive Suite | €1,422 | ¥5,688 | 到 9/25 ｜超预算 |
| Magma Hotel（Kirkjubæjarklaustur） | Family Room | €760 / €836(free-cxl) | ¥3,040–3,344 | 到 9/20 |
| Hótel Klaustur | The Suite | €1,046 / €1,264(free-cxl) | ¥4,184–5,056 | 到 9/13 |

🔴 ~~Fosshotel Glacier Lagoon 是唯一同时满足「离冰河湖近 + 在预算内 + 还能免费取消」的。~~
**这句已作废**：它的 Standard 只剩 **1 间**，凑 2 间要 €1,067（含税 €1,194）= **¥4,776/room 超预算**。
→ **改住 Höfn，见 `PLAN-final.md`。**
**修正 slug 后新拿到的更便宜替代（都在 Höfn 一带，离冰河湖 45–60 min）：**

| 物业 | 房型 | 2 间房总价 | ¥/room | free-cxl |
|---|---|---|---|---|
| **Árnanes Sveitagisting**（Höfn 西） | Double/Twin · 私卫 | €248–321 / €276–349(free-cxl) | **¥992–1,396** | 到 **9/20** |
| Árnanes Sveitagisting | Triple · 私卫 | €346–368 / €385–409 | ¥1,384–1,636 | 到 9/20 |
| **Lambhús Cabins**（Höfn） | Family Studio ×1 | €232–399 | — | 不可退 |

👉 **🥇 结论（已定）：住 Árnanes。** 按每间价重算 —— Árnanes 2 间 flex **€553，含税 €626 = ¥2,504/room**，
还有 **4 间**、含早、可要相连房、退到 9/20；Fosshotel Glacier Lagoon 只剩 1 间、凑 2 间 ¥4,776/room。
代价是离冰河湖多开约 50 min，但换来**冰河湖看两次两种光** + **Stokksnes/Vestrahorn 离 Höfn 只 15 min**
（极光前景比冰河湖更好）。备选 Fosshotel Vatnajökull（Höfn 镇）€345/间、剩 2 间、退到 9/25。

（`hali-country` / `the-milk-factory` 换 slug 也没抓到 —— 这两家在 Booking 上可能已下架，
需要去官网直接看。`jokulsarlon` 和 `hofn-apartments` 这两个 slug 返回 0 行 = 9/27 售罄。）

### D4 · 9/28（一）Keflavík —— 为次日斯奈山 + 还车

| 房源 | 房/卫 | 总价 | ¥/room | 评分 | 位置 |
|---|---|---|---|---|---|
| 🥇 [3BR/2BA](https://www.airbnb.com/rooms/1231709933827491677) | **3BR / 2BA** | €424 | **¥1,696** | 4.92 | Reykjanesbær（KEF 旁） |
| [3BR/2BA](https://www.airbnb.com/rooms/1302095139759149342) | 3BR / 2BA | €498 | ¥1,992 | 4.91 | Reykjanesbær |
| [Cozy home in Njardvik](https://www.airbnb.com/rooms/1468029290775302593) | 4BR / 2BA | €445 | ¥1,780 | 4.54 | Njarðvík（KEF 5 min） |

### D5 · 9/29（二）Oslo Gardermoen —— 同 D0

| 房源 | 房/卫 | 总价 | ¥/room | 备注 |
|---|---|---|---|---|
| 🥇 [Modern. Quiet area. Large space.](https://www.airbnb.com/rooms/1616864516592253636) | 3BR / 2BA | €260 | ¥1,040 | Nannestad，可订 1 晚 |
| [4BR/2BA](https://www.airbnb.com/rooms/1204471771405405295) | 4BR / 2BA | €541 / 2晚 | ¥1,082/晚 | Ullensaker ⚠️ min-stay 2 |
| **酒店兜底**：Scandic Oslo Airport | 2 间房 | €141–188/间 · free-cxl 到 9/28 | ¥1,128–1,504 | 34 个房型行有货，很宽松 |
| **酒店兜底**：Radisson Blu Airport | 2 间房 | $296–392/间 · free-cxl 到当天 18:00 | — | 36 行有货 |

### D6–D7 · 9/30–10/1（三、四）罗弗敦 2 晚 —— **供给最好的一段，22 个合格房源**

**东侧（Svolvær / Vågan，EVE 落地 2h30 就到）**

| 房源 | 房/卫 | 2晚总价 | €/晚 | ¥/room/晚 | 评分 |
|---|---|---|---|---|---|
| ⛔ ~~[5BR/2BA in Vågan](https://www.airbnb.com/rooms/1382960789125435389)~~ | 5BR / 2BA | ~~€674~~ | — | — | 4.78 ｜🔴 **日期不可用（换干净浏览器复现过）** |
| 🥇 **替代**：[Waterfront Nordic house, Vågan](https://www.airbnb.com/rooms/1362321193877972891) | **5BR/8床/2BA** | **€553** | €277 | **¥1,106** | **4.93** Guest favorite · 可退 |
| [Nordic Lodge Retreat in Lofoten](https://www.airbnb.com/rooms/1303545546783105490) | 4BR / 2BA | €898 | €449 | ¥1,796 | **4.92** |
| [Secluded house · private pool](https://www.airbnb.com/rooms/1441200146734024595) | 5BR / 2BA | €896 | €448 | ¥1,792 | 4.6 |
| [Functional architecture close to nature](https://www.airbnb.com/rooms/574286379531171221) | 4BR / **2.5BA** | €1,041 | €521 | ¥2,084 | **5.0** |
| [Unique group stay next to golf and beach](https://www.airbnb.com/rooms/45665373) | 7BR / 2.5BA | €1,634 | €817 | ¥3,268 | 5.0 |

**西侧（Reine / Ramberg / Ballstad，风景明信片那一侧）**

| 房源 | 房/卫 | 2晚总价 | €/晚 | ¥/room/晚 | 评分 |
|---|---|---|---|---|---|
| 🥇 [The heart of Ramberg](https://www.airbnb.com/rooms/1170849828585814519) | **4BR / 2.5BA** | €647 | €324 | **¥1,296** | 4.76 |
| [Seafront fisherman's cabin in Lofoten](https://www.airbnb.com/rooms/35072091) | 3BR / 2BA | €900 | €450 | ¥1,800 | **4.98**（真 rorbu 体验） |
| [Villa - Havgapet](https://www.airbnb.com/rooms/1259549145786305745) | 7BR / 2BA | €958 | €479 | ¥1,916 | 5.0 |
| [Valen house in famous Reine](https://www.airbnb.com/rooms/1314514220654606262) | 4BR / 2BA | €1,113 | €557 | ¥2,228 | 4.25（**就在 Reine**） |
| [Guest suite in Flakstad](https://www.airbnb.com/rooms/43494853) | 2BR / 2BA | €740 | €370 | ¥1,480 | 4.93 |

**rorbu / 酒店路线（Booking 实时房型行）**

| 物业 | 房型 | 2晚总价 | ¥/room/晚 | free-cxl |
|---|---|---|---|---|
| **Hattvika Lodge**（Ballstad） | Nordbua #2 · **3 卧** | €701（不可退）/ €715 | **¥1,402/晚** | 到 **9/16** |
| Hattvika Lodge | Nordbua #1/#3/#4 · 2 卧 | €639–701 | ¥1,278–1,402 | 到 9/16 |
| Hattvika Lodge | Sørbua #1 · **4 卧** | €1,156 / €1,178 | ¥2,312 | 到 9/16 |
| **Eliassen Rorbuer**（Hamnøy，那排最出名的红屋） | Waterfront Superior **2 卧** | €757（不可退）/ €1,084 | ¥1,514–2,168 | 到 **9/28** |

⚠️ **Hattvika / Eliassen 的卫生间数量 Booking 页面没写** → 这是必须发邮件问的（见待办）。
Airbnb 那批是**页面上明确标了 2BA/2.5BA 的**，所以「一定要 2 卫」这条需求，**Airbnb 那几个更可靠**。

#### 🥇 补充：**Nusfjord Arctic Resort —— 唯一在 Booking 页面上明写「2 bathrooms」的罗弗敦房源**

修正了 Booking 的 slug 之后重抓，拿到了三家之前抓空的：

| 物业 | 房型 | 卫生间 | 2 晚总价 | ¥/room/晚 | free-cxl |
|---|---|---|---|---|---|
| 🥇 **Nusfjord Arctic Resort** | **Village Cabin Suite Plus** | **2 卫（页面明写）** | €723（不可退）/ €743 | **¥1,446** | 到 **9/16** |
| **Nusfjord Arctic Resort** | **Harbor Cabin Suite Plus** | **2 卫（页面明写）** | €864–941 / €949 | ¥1,728–1,882 | 到 9/16 |
| Nusfjord Arctic Resort | House of Dahl | **5 卫** | €4,162 | ¥8,324 | — ｜远超预算 |
| **Svinøya Rorbuer** | Telegrafen 2.2 | 未写 | €681 / €876(free-cxl) | ¥1,362–1,752 | 到 **9/25** |
| Svinøya Rorbuer | Vestfjord 2.1 | 未写 | €723 / €932 | ¥1,446–1,864 | 到 9/25 |
| Svinøya Rorbuer | **Rorbu XXL+ with Sauna** | 未写 | €1,107 / €1,427 | ¥2,214–2,854 | 到 9/25 |

👉 **Nusfjord 的 Village Cabin Suite Plus 是全罗弗敦「明确 2 卫 + 在预算内」的唯一确定答案**
（¥1,446/room/晚，free-cxl 到 9/16）。Nusfjord 在西侧，离 Reine 约 40 min、离 Ramberg 15 min ——
和「D7 住西侧」的方案完全兼容。
⚠️ 但 Nusfjord 是**度假村式**，Suite Plus 只有 1 间卧室的可能性存在（"Suite" 不等于 2 卧）→
**订之前必须确认卧室数**。如果它是 1 卧 2 卫，就退回 Airbnb 那批（Ramberg 4BR/2.5BA €647/2晚）。

（`sakrisa-y-rorbuer-as` 和 `reinefjorden-sjohus` 换了正确 slug 后仍然 0 房型行 →
这两家 9/30–10/1 **确实卖完了**。`statles-rorbu` 虽然出现在 Lofoten 页面上，
但它其实在 **Møre og Romsdal 的 Bud，不在罗弗敦**，排除。）

### D8–D10 · 10/3–10/5（六–一）特罗姆瑟 3 晚 —— 18 个合格房源

| 房源 | 房/卫 | 3晚总价 | €/晚 | ¥/room/晚 | 评分 |
|---|---|---|---|---|---|
| 🥇 [Houseboat in Tromsø](https://www.airbnb.com/rooms/1607078897559083655) | **3BR / 3BA** | €825 | €275 | **¥1,100** | **5.0** ｜住船上，卫生间比人少 |
| 🥇 [5BR/2.5BA Tromsø](https://www.airbnb.com/rooms/1763946111917505608) | **5BR / 2.5BA** | €1,155 | €385 | ¥1,540 | — |
| [3BR/2BA Tromsø](https://www.airbnb.com/rooms/805864934151694916) | 3BR / 2BA | €1,111 | €370 | ¥1,480 | 4.86 |
| [Cozy house on Tomasjord](https://www.airbnb.com/rooms/938536829410600780) | 3BR / 2BA | €1,171 | €390 | ¥1,560 | 5.0 |
| [Gorgeous views, close to downtown](https://www.airbnb.com/rooms/880420426360588834) | 4BR / 2BA | €1,600 | €533 | ¥2,132 | 4.95 |
| [The Loft I 4BR/2 Bath](https://www.airbnb.com/rooms/1480974381910568232) | 4BR / 2BA | €1,734 | €578 | ¥2,312 | 5.0 ｜市中心 |
| **酒店兜底**：Thon Hotel Polar | 2 间房 · 3 晚 | €690–908 | ¥920–1,210 | 到 10/2 |
| **酒店兜底**：Scandic Ishavshotel | 2 间房 · 3 晚 | €898–1,238 | ¥1,197–1,650 | 到 10/2 |

**特罗姆瑟公寓型（修正 slug 后新拿到的，都是整套公寓）**

| 物业 | 房型 | 3 晚总价 | ¥/room/晚 | free-cxl |
|---|---|---|---|---|
| 🥇 **Enter Amalie Apartments** | **Three-Bedroom Loft** | €925 | **¥1,233** | 不可退 |
| **Enter Viking Apartments** | **Three-Bedroom** | €1,206 / €2,172(free-cxl) | ¥1,608–2,896 | 到 **9/3** ⚠️ 只剩 2 天 |
| Enter Viking Apartments | Four-Bedroom | €1,520 / €2,735 | ¥2,027–3,647 | 到 9/3 |
| Enter Viking Apartments | Two-Bedroom | €768–904 / €1,627 | ¥1,024–2,169 | 到 9/3 |
| **TA Vervet Apartment** | Two-Bedroom | €535 / €595(free-cxl) | **¥713–793** | 到 9/19 |
| TA Vervet Gjøa I & J | Two-Bedroom | €567 / €630 | ¥756–840 | 到 9/19 |
| TA Vervet Gjøa I & J | Two-Bedroom + 阳台海景 | €1,338 / €1,487 | ¥1,784–1,983 | 到 9/19 |
| Enter St. Elisabeth Suites | Suite ×2 间 | €1,074–1,177 | ¥1,432–1,569 | 到 10/1 |
| Enter St. Elisabeth Suites | Family Suite ×2 间 | €1,668 | ¥2,224 | 到 10/1 |

✅ **顺手答掉一个悬案：Vervet Apartments 没有闭店。** 之前有 listing 显示「2026-08 → 2027-08 关闭」，
实测 **10/3–10/6 正常放房、正常报价**（€535/3 晚起，free-cxl 到 9/19）—— 那条闭店信息是错的或已作废。
⚠️ Vervet 和 Enter 系列的 Two-Bedroom **多为 1 卫**，Booking 页面没写卫生间数 →
「一定要 2 卫」还是以 Airbnb 那批（明写 2BA/2.5BA/3BA）为准，这几家当**价格锚**和兜底。

---

## 二、如果只看「性价比最高的一套组合」

> 🔴 **这一节已被 [`PLAN-final.md`](PLAN-final.md) 取代** —— 那里的组合修掉了本文的三处错误
> （每间价 / 冰岛含税 / 两个订不到的 🥇），并把游轮 pass 之后的 10/2 那晚也排进去了。
> 最终数字：**12 晚 €3,977 ≈ ¥31,816，折 ¥1,326/房/晚。**

## 三、现在就该下手的顺序（按会先卖光排）

1. 🔴 **Fosshotel Glacier Lagoon 9/27 两间房** —— free-cxl 只到 **9/25**，方圆 60 km 就这几家。今天订。
2. 🔴 **罗弗敦 9/30–10/1** —— Hattvika 的 free-cxl 已经是 **9/16**（比别家早），先订可退的 Airbnb。
3. 🟠 **特罗姆瑟 3 晚** —— 极光季开季，Houseboat 这种独一份的先没。
4. 🟠 **南岸 9/26** —— 只有 3 个选项，等于随时会变成 0 个。
5. 🟢 Gardermoen 9/24 + 9/29、Keflavík 9/28 —— 供给充足，可以等决策定了再订。

> 全部按「**可免费取消**」下单。9 月末冰岛南岸和 E10 的风暴封路太常见，
> 省下的那点不可退折扣不值得。

---

## 四、待办 / 需要人工确认

- [ ] **Kevin 的 KEF→OSL 航班起飞时间** ← 决定 9/29 斯奈山能不能做（唯一的硬前提）
- [ ] **Hattvika Lodge / Eliassen Rorbuer / Svinøya Rorbuer 的卫生间数**（Booking 页面没写）→ 发邮件
- [ ] 🔴 **Nusfjord「Village Cabin Suite Plus」到底几间卧室**（2 卫已确认，卧室数没写）
      —— 这是全罗弗敦最优解，也是唯一需要确认的一点
- [x] ~~8 个 slug 抓空~~ → **已修正**：`svinoya`（不是 `svinoya-rorbuer`）、`nusfjord-as`、
      `sakrisa-y-rorbuer-as`、`park-inn-oslo-airport`、`enter-amalie-apartments` /
      `enter-viking-apartments` / `ta-vervet-apartment`（不是 `enter-city-apartments`）。
      修正后 12 家有数据、3 家确认售罄、2 家（`hali-country` / `the-milk-factory`）疑似 Booking 下架
- [x] ~~Vík 镇内酒店 2 间房报价~~ → **Hotel Katla €615–683/间 = ¥4,920–5,464/room，超预算**。
      Vík 一带 9/26 没有在预算内又有 2 间的选择 → **9/26 定 Hotel Hvolsvöllur ×2 间 €326（¥1,496/room，到店付，退到 9/24）**
- [x] ~~酒店那几行的 €/$ 到底是单间价还是两间总价~~ → 🔴 **已确认是「每间每晚」**（三条证据见顶部）。
      本文所有酒店 ¥/room 要 ×2 重读；`PLAN-final.md` 已全部重算并加上 11% VAT + 城市税。
      （Radisson 两家返回 USD 而不是 EUR，说明它忽略了我的货币参数）
- [ ] D3 蓝冰洞 → Katla 冰洞的决定（等 Kevin 找票）
