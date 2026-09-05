# `_research/` 是什么 —— 全部价格的原始证据，别删

这个目录里的 **916 个文件 —— 306 张截图 + 459 份 JSON + 71 份日志 + 46 个抓取脚本 + 27 份研究笔记**，是
`notes/*.md` 和 `viz/` `story/` `styles/` 里**每一个价格数字的出处**。
它占了 repo 的 90 MB，看着像临时文件，**但它不是** ——
2026 年 9 月这些房源/车/机票的报价，**过了出发日就再也抓不回来**。
删掉它，剩下的文档就从「实抓」退化成「据说」。

> 一句话：**`notes/*.md` 是结论，这里是证据。** 想核对某个数字，按下面的约定顺着找。

---

## 一、命名约定（45 组，一眼能找）

每一次抓取都是**同名三件套**，前缀一样：

```
jobs_<X>.json     ← 输入：这次要抓哪些目标（房源/车/航班 + 日期 + 人数）
log_<X>.txt       ← 过程：跑的时候的 stdout，含失败项和重试
out_<X>/          ← 产出：每个目标一份 .json（结构化结果）+ 可选 .png（页面截图）
```

**重跑任何一组**：`python3 <对应脚本>.py jobs_<X>.json out_<X>/`
（脚本用哪个见第三节；全部走 Playwright + Chromium，需要能出网。）

`out_<X>/` 里没有 `.png` 的，是因为那次只要结构化数字（价格行/报价表），
**有 `.png` 的都是「可订证据」** —— 截的是当时那个房型行 / 报价行的实际网页。

---

## 二、45 组分别在回答什么问题

### 住宿 · Airbnb 搜索与核实

| 组 | 抓了什么 | 产出 |
|---|---|---|
| `abnb` | 第一轮：全程 12 个落脚点，整套房 ≥2 房 ≥2 卫 | 12 json |
| `abnb2` | 第二轮：收敛成 10 个点（含 keflavik / borgarnes） | 10 json |
| `abnb3` | 罗弗敦补抓（east / east-wide / mid 三种范围） | 3 json |
| `abnb4` | 南岸 + 冰河湖复抓（3BR 版本） | 3 json |
| `nobath` | 放宽到**不限卫浴数**，看池子能大多少（9 个点） | 9 json |
| `nobath_detail` | 上一组挑出的 **26 个房源逐一开详情页**核实真实日期/价格 | 26 json + **78 png** |
| `cands` | **候选池定稿**：23 个入选房源逐一开页核实 | 23 json + **69 png** |

### 住宿 · Booking 酒店房型行（乡下不接 1 晚 → 改开 2 间的兜底路线）

| 组 | 抓了什么 |
|---|---|
| `prop` | 冰河湖一带 19 家（Fosshotel Glacier / Hali / Klaustur / Magma / Höfn…） |
| `prop2` | 罗弗敦 18 家 rorbu（Svinøya / Sakrisøy / Nusfjord / Reine…） |
| `prop3` `prop4` `prop6` | Vík–Skógar 一带三轮，共 30 家 |
| `prop5` | 4 家的**单间**价格（用来算「开 2 间 vs 开 1 间」） |
| `prop7` | 特罗姆瑟 10 家市区酒店 |
| `mid2` `mid2b` | 中档档位复算：Klaustur / Vík / Band / Höfn 的 1 卫 vs 2 卫 |
| `west` | **Borgarnes 一带 6 家**（斯奈山跳板；见 `../ICELAND-oneway.md` 第五节） |
| `shot` `shot2` | 4 + 2 家的**房型行截图**（Anna / Fosshotel / Hvolsvöllur / Árnanes） |

### 住宿 · Steve 自己找的那一套（现已成为默认方案）

| 组 | 抓了什么 | 产出 |
|---|---|---|
| `steve3` | Hörgsland 9/26（含 2 晚版）· Birkifell 9/27 · Stracta | 5 json |
| `steve4` | Njarðvík 9/28 · 奥斯陆 10/5 | 2 json + **6 png** |
| `steve5` | 罗弗敦新链接 | 1 json + **4 png** |
| `steve6` `steve6b` | 罗弗敦 east-4BR · Lyngvær · Vågan(1卫) | 3 json |
| `steveplan` | **整套 6 段逐一核实**（9/25 雷市 / 9/28 / 9/29 / 9/30–10/2 / 10/2–10/5 / 10/2–10/6） | 6 json + **18 png** |

### 租车 · DiscoverCars 实时报价

| 组 | 抓了什么 |
|---|---|
| `cars` | 第一轮 4 段（冰岛 KEF 4 天 / 罗弗敦 EVE / 特罗姆瑟 2 天） |
| `dc` `dc2` `dc3` `dc4` | 四轮复算，含挪威 EVE→TOS 异地、TOS 3 天、OSL 1 天 |
| `oneway` | **异地还车费实测**：6 种取还组合（基准 KEF→KEF 5 天 $258，EGS→KEF 4 天 $606 → 异地费 ≈ +$350–400） |
| `split` | Steve 提的「同地租 N 天 + 最后 1 天异地」5 个变体（见 `../OPTIONS-cars-split.md`） |
| `verify` | 4 个报价的复核（KEF 9/25 17:00 提车 / EVE→TOS 6 天 / 3 天 / TOS 2 天） |

### 机票

| 组 / 目录 | 抓了什么 |
|---|---|
| `fly` `fly2` | 罗弗敦↔特罗姆瑟↔奥斯陆 4+2 个航段 |
| `out_flights` `out_fly_air` `out_fly_air2` | Google Flights DOM 三轮（含 12 张截图） |
| `out_isdom` | **冰岛国内线**：RKV→EGS 9/26 · HFN→RKV 9/28 · EGS/AEY→RKV（5 张截图） |

🔴 **Google Flights 抓的是 `for 4 adults` → 返回的价格是 4 人总价，不是单人价。**

### Steve 一个人的后半段（10/6 分手 → 南法/伦敦 → 回湾区）

见 [`../SOLO-after-oslo.md`](../SOLO-after-oslo.md)。**这一组的口径和上面所有机票都不同：**

| 组 | 抓了什么 | 产出 |
|---|---|---|
| `solo` | 14 段：OSL→NCE/MRS/LON/CDG（10/6）· NCE/MRS/LON/CDG→SFO/SJC（10/11）· 尼斯↔伦敦连接 · 10/19 多待一周版 | 14 json + **14 png** |
| `solo2` | **伦敦→SFO 逐日扫 10/9–10/20**（找出价格断崖在 10/15）+ 尼斯→SFO 4 天对照 | 16 json + **16 png** |
| `solo3` | 5 段：10/5 提前一天走（OSL/TOS 出发）· 10/14·10/18 尼斯→伦敦 · 10/15 LHR 直飞时刻 | 5 json + **5 png** |
| `solostay` | 尼斯 5/9/13 晚 + 伦敦 1/4 晚的**单人**整套房实价（Airbnb） | 5 json |
| `solo_q` | 6 份研究笔记：十月气候对比 / 蔚蓝海岸 5 天 / 普罗旺斯 vs 里维埃拉 / 伦敦 5 天 / 尼斯有无跨大西洋 / LHR→SFO·SJC | 6 md |

🔴 **`flights_solo.py` 是全 repo 唯一按 `1 adult` + USD 查的机票脚本。**
其余 `flights_*.py` 全写死 `for 4 adults` → 那些是 4 人总价。**两边的数字不能放同一张表。**

⚠️ 命名有一处偏离约定：研究那组是 `q_solo.json` / `log_solo_q.txt` / `out_solo_q/`
（不是 `jobs_solo_q.json`），因为它喂给 `gsearch.py` 而不是抓取脚本 —— 和 `out2/` `out_cars/` 同类。

⚠️ `stay_solo.py` + `log_solostay.txt` 里记着一个坑：**Booking.com 的搜索结果页现在抓不到**
（2026-09-05：`searchresults.html` 回 HTTP **202** 并跳首页，`[data-testid=property-card]` 为 0
—— 站方 bot 拦截，不是脚本坏了）。所以这一段住宿价走 Airbnb。

### 邮轮（Svolvær → Tromsø 10/2）

没有 `jobs_` 文件，是一串**逐步攻破**的探测脚本（Hurtigruten 有 JSON API；
Havila 是 Flutter/CanvasKit 页面、零 DOM，只能监听网络请求）：

| 目录 | 内容 |
|---|---|
| `out_cruise` | 26 份：表单结构、XHR 端点、舱位价、1 张截图 |
| `out_cruise_g` | 4 份 gsearch 研究笔记（Havila 票价 / 10-02 班次 / Torghatten / Widerøe） |

### 图片素材（给 `story/` 和 `styles/` 用）

| 组 / 文件 | 内容 |
|---|---|
| `img` `img2` | 从 Booking/Airbnb 详情页抓**住宿实拍的 CDN 直链**（不下载，只要 URL） |
| `out_wiki.json` `out_wiki2.json` | Wikimedia Commons 风光图候选（自由授权 + 作者/许可信息） |
| `out_wiki_picked.json` | 挑定的那批，已解析成 `/thumb/` URL |

### 网络研究（Gemini + Google Search，非抓取）

`out2/` `out_cars/` `out_stay/` `out_gs_fly/` `out_cruise_g/` 里的 **20 份 `.md`** ——
冰洞季节、斯奈山耗时、雷克雅内斯火山状态、Widerøe 开票窗口、各段住宿/租车综述。
产生它们的是 `gsearch.py`。

### 其他

`smoke`（一次性连通性测试，`out_smoke/` 已 gitignore）· `out_bk` `out_cars_live` `out_shots` `out_shots2`
（早期单次抓取）· `out_detail` `out_detail2` `out_detail3`（住宿详情核实三轮，**57 张截图**）。

---

## 三、脚本按目标站点分组（顶层 44 个 + `out_gs_fly/` 里 2 个 Widerøe 试探）

| 目标 | 脚本 | 备注 |
|---|---|---|
| **Booking.com** | `bk_scrape.py`（搜索结果，带房/卫数）· `bk_prop.py`（**房型行 = 主力**）· `bk_shot.py`（房型行截图）· `slug_find.py` `slug_west.py`（从 SEO 落地页刨真实 slug）· `bk_img_fix.py`（监听请求拿带签名的图片 URL） | 🔴 **slug 猜不出来，只能采** |
| **Airbnb** | `abnb_scrape.py`（搜索）· `abnb_detail.py`（按我们的真实日期逐个核实） | |
| **Booking（已失效）** | `stay_solo.py` | ⚠️ 2026-09-05 起搜索结果页 HTTP 202 跳首页，留着记录这个坑 |
| **DiscoverCars** | `dc_direct.py`（**主力**：`/search/<uuid>?sq=<base64 json>` 深链）· `dc_cars.py`（驱动日历表单）· `dc_loc.py`（取地点 id）· `dc_probe.py` | 深链比点表单稳得多 |
| **Google Flights** | `flights_gf.py` `flights_fly.py` `flights_proxy.py` `flights_isdom.py`（**4 adults**）· `flights_solo.py`（🔴 **1 adult + USD，只给 `../SOLO-after-oslo.md` 用**） | 都是 DOM 渲染后再读 |
| **Hurtigruten** | `hrg_api.py`（**有 JSON API，最省事**）· `cruise_p2p.py` `cruise_probe.py` `cruise_links.py` `cruise_drive.py` `cruise_drive2.py` `cruise_go.py` `cruise_book.py` | 7 个是逐步摸清表单的过程 |
| **Havila** | `havila_probe.py` `havila_book.py` `havila_dflow.py` `havila_net.py` `havila_shot.py` `hav_assets.py` | 🔴 Flutter/CanvasKit，**零 DOM，只能抓网络请求**；`/en/booking` 从这里是 CF-403 |
| **图片** | `wiki_img.py` `wiki_img2.py`（Commons）· `pick_imgs.py`（挑图，含踩过的 3 个坑）· `resolve_thumbs.py` · `img_scrape.py`（住宿实拍 URL） | |
| **建页** | `build_story.py` → `story/data.js` · `build_styles.py` → `styles/data.js` · `gen_candidates.js` → `../CANDIDATES.md` | ⚠️ 三个 `data.js` 目前各自独立，见 `../../README.md` |
| **研究** | `gsearch.py`（Gemini + Google Search via Foundry Gateway） | 出 `.md` 不出 json |

---

## 四、引用这里的数字时必须记住的三条

1. 🔴 **Booking 的行价是「每间每晚」**，而**冰岛酒店不含 11% VAT + €6/间/晚城市税**。
   2 间的含税价 = `行价 × 2 × 1.11 + €12`。Airbnb 和挪威的价格**已含税含费**。
2. 🔴 **Google Flights 那些价格是 4 人总价**（查询串里写了 `for 4 adults`）——
   **唯一例外是 `solo*` 那几组**（`flights_solo.py`，`for 1 adult` + USD，给 `../SOLO-after-oslo.md`）。
   **4 人价和单人价不能放同一张表。**
3. **汇率全项目固定**：`€1 = ¥8.0` · `$1 = ¥7.1` · `NOK 1 = ¥0.67`。
   所有 `.md` 用的都是这三个数，改汇率会让所有文档互相矛盾。

## 五、抓取时间线

`2026-09-01`：住宿 + 租车 + 邮轮第一轮 · `2026-09-02`：机票、异地还车、Steve 那套链接、
冰岛国内线、Borgarnes 复查、图片素材 · `2026-09-05`：Steve 单人后半段（`solo*`，1 adult/USD）。**报价均为当日实时**，之后可能已变。
