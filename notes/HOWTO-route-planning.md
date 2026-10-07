# 怎么做一份「路线 + 地图 + 时间表」攻略（给下一个 agent）

> 来源：2026-10-04 Senja 一日自驾（`/senja/`）、9/24–9/29 后半段订票页（`/solo/`、`/solo/trip/`）、
> 9/26 实用页（`/info/` + 日历）。**每一步都有对应脚本，可以直接照抄**；下面写的坑全部真踩过。
> 要重跑的价格抓取（Booking / Airbnb / 机票 / 租车）见 [`_research/INDEX.md`](_research/INDEX.md)，这里讲的是「把一堆地点变成一条能开的路线」。

## 一、流程（顺序别乱）

| # | 做什么 | 怎么做 | 脚本 |
|---|---|---|---|
| 1 | **地址 → 坐标** | OSM Nominatim 地理编码。**每秒 1 次、必须带 User-Agent**；同名地点会返回多个候选（Fjordgård 就有两个点，取村中心）；先打印候选再选，别取第一个 | `senja_route.py`（`PTS`） |
| 2 | **坐标 → 真实道路时间** | OSRM `table`（全部两两组合，一次请求）。**不要用直线距离**；Senja 的峡湾会让 Lanesbogen→Bergsbotn 直线 19 公里变成路上 47.5 公里 / 48 分钟 | `senja_route.py` |
| 3 | **定顺序** | 起点和终点固定，中间 ≤8 个点直接**穷举全部排列**（6 个点 720 种，瞬间）。别靠感觉排，原图的顺序就有一处反了（多走 6 km） | `senja_route.py` |
| 4 | **量化绕路** | 每一站的「边际绕路」= 有它的总驾驶时间 − 拿掉它之后的总时间。支线村庄（要进去再原路出来）一站就是 12–24 分钟 | `senja_extra.py` |
| 5 | **硬约束用官方实时数据** | 渡轮 / 公共交通查 **Entur**（见第二节）。末班船决定整条线路，所以必须是官方数据 | `entur_ferry.py`（输出 `out_entur_ferry.json`）、`senja_extra.py` |
| 6 | **日落** | `astral`（`pip install --user astral`），不是估 | `senja_extra.py` |
| 7 | **从硬约束倒推** | 从「末班船 − 缓冲」往回推每一站**最晚几点必须走**，比正推「几点到」有用得多 | `site/senja/index.html` 里的 `compute()` |
| 8 | **做成页面** | Leaflet + Esri 深灰底图；数据由脚本写成 `data.js`，页面纯静态；用户可改出发时间和停留 | `senja_build.py` → `site/senja/` |
| 9 | **日历** | 生成 `.ics`（UTC、CRLF、每行 ≤75 字节折行），再用 `icalendar` 库解析一遍验证 | `build_info.py` → `site/cal/` |
| 10 | **地址 / 入住时间** | Booking 房源页有完整地址和精确坐标；**Airbnb 房源页只到街区**（坐标有一两百米模糊），门牌号和门锁密码只在订单里 | `practical_scrape.py`、`build_info.py` |

## 二、Entur（挪威官方公共交通数据）怎么查

```python
H = {"ET-Client-Name": "<随便写个名字>", "Content-Type": "application/json"}      # 必须带这个 header
# 1) 找站点 id
GET https://api.entur.io/geocoder/v1/autocomplete?text=Botnhamn&size=6          # → NSR:StopPlace:63913（Botnhamn ferjekai）
# 2) 查某天的班次（含实时、含取消）
POST https://api.entur.io/journey-planner/v3/graphql
{ stopPlace(id:"NSR:StopPlace:63913"){ estimatedCalls(startTime:"2026-10-04T00:00:00+02:00", timeRange:86400,
    numberOfDepartures:30, includeCancelledTrips:true){ aimedDepartureTime expectedDepartureTime realtime cancellation
    serviceJourney{ estimatedCalls{ quay{name} aimedArrivalTime aimedDepartureTime } } } } }
```

`serviceJourney.estimatedCalls` 里能直接取到对岸的到达时间，**航程分钟数就是这么算出来的**（Botnhamn → Brensholmen = 35 分钟，不是 45）。

## 三、搜索引擎给的班次不能信（这次差点出事）

用 Gemini 联网搜索（`_research/gsearch.py`，需要装了 google-genai 的 Python 环境和网关凭证，见文件顶部）查「Botnhamn 周日渡轮」，它给了：
- 18:00 之后还有 **20:00、21:30 两班** —— **不存在**。Entur 当天只有 11:15 / 16:00 / 18:00，18:00 是**末班**；
- 运营商官网链接 **404**；
- 一个「时刻表 PDF」链接，下载下来**其实是一个网页**。

后果是：如果信了，「错过 18:00 还有下一班」，整个线路的紧迫感就全错了。
**规则：班次、末班、能不能预订，一律以官方实时数据或订单为准；搜索引擎只用来找线索，然后去验证。**
页面上写不确定的事要直接写「没能核实」（这次的例子：渡轮能否预订车位）。

## 四、"验证"的口径要说实话

- OSRM 公共服务和 `routing.openstreetmap.de` **用同一份 OpenStreetMap 数据**，两个引擎总时间一致只是**一致性检查，不是独立验证**；Google 的实时路况这边取不到。
  所以页面里放了「用 Google 地图打开整条线路」的按钮，让人在手机上自己对一遍。
- 行驶时间默认 **+10%**（弯路、会车、拍照停车），页面上可以关。
- 坐标、班次、日落都在页面底部写了来源和日期。

## 五、协作和发布的坑（全部踩过）

| 坑 | 症状 | 怎么做 |
|---|---|---|
| 同一个仓库目录里有别的 agent 在别的分支上干活 | `git status` 看着正常，但 `git branch --show-current` 不是 `main`；推送会把别人没发布的提交一起带出去 | 动手前先看分支。用 `git worktree add -b <新分支> <新目录> <明确的远端 ref>` 开隔离目录，**别碰别人的工作区** |
| `FETCH_HEAD` 被别的进程改写 | 刚 fetch 完，`FETCH_HEAD` 又指回本地提交 | 永远 fetch 到**命名的 ref**：`git fetch <url> +main:refs/remotes/<名字>/main` |
| 部署时线上配置和 `main` 不一样 | 照片分支把 `wrangler.jsonc` 里指向本机的旧变量去掉了；从 `main` 部署会改回去 | 用「线上正在用的那份」`wrangler.jsonc` + `worker/`，加上要发布的 `site/`，放进**干净的临时目录**再 `wrangler deploy`（它只上传有变化的文件），部署前后各 `curl` 一遍关键页面的状态码 |
| 机器重建后工具没了 | `ModuleNotFoundError`、`git` 报 `Author identity unknown` | `pip install --user playwright astral pillow`；浏览器用系统 Chrome：`chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])`；git 用 `git -c user.name=… -c user.email=… commit`，不改全局配置 |
| 地图底图出水印 | CARTO `dark_all` 2026 年起要 API key，整张图打满 "API KEY REQUIRED" | 用 Esri 深灰：`World_Dark_Gray_Base` + `World_Dark_Gray_Reference` |
| 手机上表格最重要的两列被挤出屏幕 | 站点样式给所有 `table` 设了 `min-width:560px` | 手机宽度下对那张表 `min-width:0`，并隐藏次要列 |
| `app.js` 里已经有 `$` `esc` `hm` | 页面报 `Identifier 'hm' has already been declared` | 页面脚本放进 IIFE，别重名 |
| 公开仓库里的订单号 | PNR / 电子票号 / 确认码 / 门牌号 | **不进库**。提交前对 `git diff --cached` 用 grep 扫一遍 PNR、token、secret、key |

## 六、给下一个 agent 的建议顺序

1. 先读本文 + [`_research/INDEX.md`](_research/INDEX.md)（价格证据怎么对应）。
2. 要做新的一天的线路：复制 `senja_route.py` 改 `PTS` / `MID` / 起终点 → `senja_extra.py` → `senja_build.py` → 复制 `site/senja/` 改文案。
3. 先 `git branch --show-current`，再动手；用隔离目录；部署前后都验页面。
