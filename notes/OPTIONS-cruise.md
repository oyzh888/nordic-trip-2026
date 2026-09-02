# 邮轮舱位（D8 10/2 Svolvær 22:15 → Tromsø 10/3 14:15）

> 这是 `PLAN-booking.md` 里排第 1 的稀缺品：卖光就整段行程断掉。
> 本文所有价格都是 **2026-09-01 实时抓下来的**，来源写在每一节。
> 黑话先解释：**port-to-port（港到港）** = 只买挪威海岸邮轮的一段船票，
> 不是买 6–12 天的整趟巡游；**deck space（甲板票/无舱位票）** = 只买船票不要房间，
> 通宵靠躺椅；**Hurtigruten / Havila** 是同一条 Bergen–Kirkenes 海岸航线上的**两家公司**。

---

## 🔴 最重要的一条：10/2 那班船不是 Hurtigruten，是 **Havila**

**Hurtigruten 10 月 2 日根本没有从 Svolvær 出发的船。** 这不是"卖光了"，是那天没有它的船。

怎么确认的（两条独立证据）：
1. 官网 port-to-port 订票页填 10/02/2026 → "We could not find any departures that match this date"。
2. 直接打它的可用性 API（`POST /nellie-coastal-v2/api/availability`）查了 9/20–10/10 三个整周，
   返回的 Svolvær→Tromsø 班期是 **9/22、9/23、9/25、9/27、9/30、10/3、10/4、10/6、10/8** ——
   **10/1、10/2、10/5、10/7 全部没有**。

原因是这条航线的**排班机制**：Hurtigruten 7 条船 + Havila 4 条船 = 11 条船轮转，
整个 Bergen→Kirkenes→Bergen 往返正好 11 天，所以每天都有船，但**每天只有一家公司的船**。
10/2 从 Svolvær 北上 22:15 的那条，按轮转推算是 **Havila Polaris**（grounded search，
cruisemapper + Havila 排班交叉核对）。

**结论：这段行程能不能成立，取决于 Havila，而不是 Hurtigruten。**

---

## 1. Havila 10/2（要买的那班）—— ⚠️ 价格未验证，必须人工确认

**技术上从这台机器拿不到实时价。** 已经试过并全部失败：

| 试过的路 | 结果 |
|---|---|
| `havilavoyages.com/en/port-to-port`、`/en/booking` | 404 / **403 Cloudflare** |
| `/nb/ruteplan`、`/en` | **403 Cloudflare**（"Click to reveal" 人机验证）|
| `/nb/havn-til-havn` | ✅ 200，页面能开，但订票入口是个 JS 按钮 |
| 点那个 **"Bestill havn-til-havn"** 按钮 | 跳到**另一个域**：`prod.havilavoyages.com/touchhvl/?inJson={"caller":"D-FLOW",...}` |
| 直接打那个 D-FLOW 引擎 | 页面 200，但它是 **Flutter/CanvasKit** 应用（画在 canvas 上、**零 DOM**），而且它的主程序 `main.dart.js` 返回 **403** → 应用根本没启动，截图是纯空白 |

即 Cloudflare 把这个 pod 的 IP 挡在 Havila 订票引擎之外，**不是选择器写错**。

**能拿到的参考信息**（grounded search，havilavoyages.com + rome2rio + 乘客游记，**低置信度**）：

| 项 | 参考值 | 置信度 |
|---|---|---|
| 基础 port-to-port 票（含甲板/座位，不含房间）| **NOK 800–950 / 人** | 低（rome2rio 口径不明）|
| 内舱 / 外舱 / suite | 官网只在订票流程里给价，没有价目表 | ⛔ 未知 |
| **餐食** | **port-to-port 票不含餐** | 中 |
| 主餐厅 Havrand 晚餐 | ~NOK 595 / 人（2024 乘客实付）| 中 |
| Hildring 五道菜 fine dining | NOK 855 / 人 | 中 |
| Havly Café（三明治/披萨/鱼汤）| 便宜档，port-to-port 乘客可用 | 中 |
| 退改 | 分票种，`FLEX-billett` 可改；普通票有手续费 | 中 |

👉 **行动项（今天）**：直接找 Havila 订，路径三选一 ——
① 用**自己家的网/手机**开 `havilavoyages.com/nb/havn-til-havn` →「Bestill havn-til-havn」
（Cloudflare 只挡这个 pod，正常家用 IP 没问题）；
② 邮件 `booking@havilavoyages.com`；③ 电话 `+47 815 33 300`。
**要问清 4 件事**：10/2 Svolvær 22:15 还有几间舱；2 间双人舱的总价；含不含早餐；退改政策。

---

## 2. Hurtigruten 实时价（已验证）—— 作为价格锚 + 备选班期

来源：`POST https://www.hurtigruten.com/nellie-coastal-v2/api/availability`（无签名，可复算，
脚本 `notes/_research/hrg_api.py`）。**单位：USD，每人价**，发船 22:15 当地 / 次日 14:15 抵达。

舱型（第一次出现解释一下）：**PolarInside** 内舱无窗 · **PolarOutside** 外舱有窗 ·
**ArcticSuperior** 高一档、位置更好 · **ExpeditionSuite** 套房。

| 出发日 | 船 | PolarInside | PolarOutside | ArcticSuperior |
|---|---|---:|---:|---:|
| 9/22 | Nordlys | — | $418 | — |
| 9/23 | Nordkapp | — | $351 | $540 |
| 9/25 | Polarlys | $310 | $364 | $563 |
| 9/27 | Richard With | — | $418 | — |
| 9/30 | Kong Harald | — | $418 | $563 |
| **10/1、10/2** | **无船（Havila 日）** | — | — | — |
| **10/3** | **Nordlys** | — | — | **$563** |
| 10/4 | Nordkapp | — | $418 | $563 |
| 10/6 | Polarlys | $310 | $364 | $563 |
| 10/8 | Richard With | $310 | $418 | $563 |

🔴 **一间舱装不下 4 个人** —— 用 1 舱 4 人查，API 返回 200 但结果为空。
**必须 2 间舱**，正好也匹配「两个男生 + 一对夫妻」。

所以 4 人 2 舱的总价（换算 $1≈¥7.1）：

| 档 | 每人 | 4 人合计 | ≈ RMB |
|---|---:|---:|---:|
| PolarInside（仅 9/25、10/6、10/8 有）| $310 | **$1,240** | ¥8,800 |
| PolarOutside（常见档）| $418 | **$1,672** | ¥11,900 |
| 10/3 只剩 ArcticSuperior | $563 | **$2,252** | ¥16,000 |

**这就是 Havila 报价的对标线**：Havila 若报到 4 人 ¥12,000 以内属正常，
明显更高就先谈或者走下面的备选。

⚠️ 甲板票（deck space）没查出来 —— API 的 `deckspaces` 字段形状不对，返回 **HTTP 400**。
一段 16 小时通宵、10 月的挪威北极圈，**本来也不建议 4 个人靠躺椅过夜**，优先级放低。

---

## 3. 如果 Havila 10/2 拿不到 —— 两个备选，代价都已量化

### 备选 A：改坐 Hurtigruten 10/3（22:15 → 10/4 14:15）
- 舱位实时可订，但**只剩 ArcticSuperior $563/人 → 4 人 $2,252（¥16,000）**。
- 🔴 代价：整段后移一天 → **Lofoten 多住一晚、Tromsø 少一晚**，
  而 Tromsø 那 3 晚（10/3 起）已经在 `OPTIONS-stay.md` 里选好了，得整段重订。
- 也就是说 A 便宜不了，还要动住宿。**不是好选择。**

### 备选 B：不坐船，飞 Lofoten → Tromsø
Google Flights 实时查（4 人含税总价，NOK，脚本 `notes/_research/flights_gf.py`）：

| 航段 | 10/2 实时结果 |
|---|---|
| **SVJ → TOS** | 只有 2 个班次，都要**经 Bodø 甚至 Bergen 绕、16 小时以上**，而且 **Price unavailable** |
| **LKN → TOS** | 0 个结果 |
| **EVE（Evenes/Harstad-Narvik）→ TOS** | 有票但全部**经 Oslo 绕 4–6 小时**：最低 **NOK 7,768 / 4 人**（≈¥5,200），SAS 最快 4 小时 NOK 10,796 |

🔴 **Google Flights 卖不了 Widerøe 的 SVJ→TOS 直飞**（Widerøe 的短程支线航班很多不进 GDS）。
Grounded search 说这条直飞**存在、约 50 分钟**，官网票价区间 **NOK 1,819–3,699 / 人单程**
（wideroe.no，10 月初），第三方显示低至 ~NOK 800–1,000。
→ **必须去 wideroe.no 自己查**，这是本条唯一没验证的数字。

**B 的隐藏红利**：不坐船就不用把车开到 Svolvær 还 ——
`OPTIONS-cars.md` 里实测的 **EVE→Svolvær 单程异地还车费 ≈ $320**（NOK 3,400）就省掉了，
而且同地还车最便宜的四驱自动是 Toyota Urban Cruiser **$167 / 3 天**。
所以 B 的真实差价 = 机票 − $320 异地费 − （省下的船票）。

### 三个方案总账（4 人）

| 方案 | 交通 | 异地还车费 | 合计 | 备注 |
|---|---:|---:|---:|---|
| **Havila 10/2 + 2 舱** | 未知（对标 ¥12,000）| +$320 | **≈¥14,300?** | ✅ 保持原行程、省一晚酒店、风景 |
| Hurtigruten 10/3 | $2,252 | +$320 | ≈¥18,200 | ⛔ 要重订 Tromsø 3 晚 |
| 飞 SVJ→TOS（直飞，待查）| ~NOK 3,200–14,800 | **$0** | ≈¥3,000–14,000 | 快，但少了海岸线；LKN/SVJ 班次少 |

**推荐：先全力拿 Havila 10/2。** 它是唯一不动其它任何预订的选项，
而且 22:15 出发、次日 14:15 到，**整个上午在船上看 Vesterålen 海岸线**，
本身就是行程亮点，还顺带省一晚住宿。

---

## 4. 顺手确认的一条（对 Tromsø/Senja 那天有用）

**Brensholmen–Botnhamn 汽车渡轮（Senja 那条，Torghatten Nord 181 线）2026 年全年运营**，
不是季节性停开 —— 之前按"季节性"标的风险可以划掉。2026-08-31 起的班表：

- **Brensholmen 开**：08:45 / 10:45 / 12:45（周五停）/ 15:00 / 17:00 / 19:00 / 20:45
- **Botnhamn 开**：08:00 / 09:45 / 11:45（周五停）/ 14:00 / 16:00 / 18:00 / 20:00
- 航程 35–45 分钟；车费 NOK 228 / 车 / 单程。
- ⚠️ 我们的 Senja 日是 **10/5 周一**，不受"周五停"影响。出发前一周再核一次 Entur。

**Svolvær–Tromsø 没有快艇（hurtigbåt）**，别浪费时间找 —— 只有海岸邮轮、飞机、或长途巴士。

---

## 5. 数据怎么来的（可复算）

| 脚本 | 干什么 |
|---|---|
| `notes/_research/cruise_probe.py` / `cruise_links.py` | 找出真正活着的订票页（`/en-us/port-to-port`；`.co.uk` 是 521，`/norwegian-coastal-express/port-to-port` 是 404）|
| `notes/_research/cruise_p2p.py` / `cruise_drive*.py` / `cruise_go.py` | 逐级摸清表单（testid `from-port-dropdown` / `to-port-dropdown` / `cabin-choice-want-cabin`）|
| `notes/_research/cruise_book.py` | 完整驱动一次，产出 `?searchData=` 深链 **并暴露出后端 API** |
| **`notes/_research/hrg_api.py`** | ⭐ 之后都用这个：直接 POST 那个 API，几秒出一整周班期+舱型价 |
| `notes/_research/havila_*.py` | Havila 的四条路全部试过（见上表），全被 Cloudflare 挡 |
| `notes/_research/flights_gf.py` | Google Flights 实时票价 |

🔴 **踩过的坑，别重踩**：Hurtigruten 的出发日期框是**掩码输入**，
写 `10/02/2026` 会被读成 `02/10/2026` 并报 "Date must be today or later"，搜索按钮一直是 disabled。
**能用的写法是不带斜杠的 `02102026`（DMY 纯数字）**，控件自己会显示成 `10/02/2026`。
所以脚本里每次写完日期都要**回读 + 检查搜索按钮是否可点**，不能只写一次就信。
（和之前 DiscoverCars 静默用了默认日期那个坑是同一类错误。）
