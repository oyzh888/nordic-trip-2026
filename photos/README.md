# 共享相册 · <https://nordic.airacle.com/photos/>

一行话：**大家把旅途里的照片和视频传到同一个地方，GPU 端自动看图、认人、分组，谁都能搜、能挑、能一键打包下载。**
照片存在 Cloudflare（不会跟着任何一台机器消失）；AI 那部分是锦上添花 —— GPU 端不在线时，上传 / 浏览 / 下载全部照常。

## 怎么用（给同行的人）

1. **进相册**：打开邀请链接（`/photos/#k=口令`，群里发的那条），或者打开 `/photos/` 手输口令。第一次会问「你是谁」，写个名字就行。
2. **上传**：右上角「＋ 上传」，照片视频一起选。
   - 同一张传两次只存一份（按内容识别，不看文件名）
   - 网断了、页面关了，重新选同一批文件会**从断点继续**，已传完的直接跳过
3. **找有你的照片**：「人物」页 → 找到自己的脸 → 点「这是我」。之后顶部的「⭐ 与我相关」就是**有你出镜的 + 你传的**，新传的照片会自动归进来。
4. **搜**：搜索框直接写中文或英文 —— 「极光」「黑沙滩上的合影」「吃饭」「waterfall」都行，按画面内容搜，不靠文件名。
5. **排 / 分组**：📅 按天 · 📍 按地点（到景点名，比如「塞里雅兰瀑布 · 冰岛」）· ✨ 按时刻（一段段经历，★ 是最值得纪念的几段）· 📷 按设备（谁的手机拍的）。
6. **挑**：「相似只留最好」默认开着 —— 连拍的几张只显示 AI 打分最高的一张，点开能看整组、能换成别的。「★ 精选」是 AI 觉得值得纪念的（极光、合影、瀑布、冰川……）。
7. **下载**：点「选择」→ 勾几张（或「全选当前」）→ 「⬇ 打包下载」出一个 zip（原图原画质），手机上用「📲 存到手机」直接进系统相册。
8. **✨ AI 改图**：点开一张照片 →「✨ AI 改图」→ 写一句话（「把天空换成极光」「去掉背景里的路人」）或点预设 → 选模型 → 大约 10–30 秒后，改好的图作为**一张新照片**出现在原图旁边。
   - **原图不会被改动**
   - 新图上有 ✨ 角标，信息栏能看到它从哪张改来、用的哪句话、谁改的；按住「按住看原图」可以对比
   - 每人每天 60 次，同时最多 3 张在改

## 架构

```
浏览器 ──► nordic.airacle.com（主站 Worker）──service binding──► nordic-photos Worker ──► R2 桶（原件 / 缩略图 / 预览 / 720p 视频）
                                                                   │
                                                                   └──► Album（Durable Object + SQLite：所有元数据、搜索、人脸、聚类）
                                                                             ▲
GPU 机上的 pipeline/worker.py ── 主动连过来（HTTP 轮询 + 一条 WebSocket），不需要开端口 ──┘
```

| 部分 | 在哪 | 做什么 |
|---|---|---|
| `src/index.js` | Worker | 口令鉴权（HMAC cookie 30 天）；分片上传 → R2；Range 下载 / 视频拖动；zip 流式打包 |
| `src/album.js` | Durable Object | 元数据、去重、断点续传状态、搜索（关键词 + 向量）、查询缓存、人物 / 聚类 / 改图队列 |
| `public/photos/` | 静态资源 | 前端（原生 JS，无框架、无构建） |
| `pipeline/` | 任意一台有 GPU 的机器 | 补 EXIF、缩略图、转码；三个模型；聚类；AI 改图 |

**去重和断点续传**：内容 ID = 按 8 MB 分块各算 SHA-256、再对这串哈希算一次 SHA-256。浏览器边读边算，传之前先问服务端「这个 ID 有没有、传到第几块了」，所以重复的文件一个字节都不用传，断掉的从下一块接着传。

**搜索和缓存**：一条搜索 = 关键词命中（VLM 写的中文描述 / 物体 / 别名 / 英文词）+ SigLIP 向量相似度。没见过的搜索词由 GPU 端经 WebSocket 算向量（~20 ms），**算过的词永久缓存**在 Album 里，下次（包括 GPU 端离线时）直接用。

## GPU 分析端（`pipeline/`）

三个模型常驻一张卡（合计 ~22 GB 显存）：

| 模型 | 用途 |
|---|---|
| Qwen3-VL-8B | 看图写中文描述 + 物体 / 场景 / 特殊场景（极光、合影……）/ 纪念价值 / 观感分 |
| SigLIP2 so400m | 图文同一个向量空间：以文搜图、连拍判重、场景聚类 |
| InsightFace buffalo_l | 人脸检测 + 身份向量 → 人物聚类、认领后自动归人 |

地名：Nominatim 反查城镇 + Overpass 找 500 米内有名字的景点（瀑布、冰川、海滩、教堂……），中文名统一转简体。

```bash
uv venv /mnt/localssd/venvs/photos
uv pip install --python /mnt/localssd/venvs/photos/bin/python -r pipeline/requirements.txt
bash pipeline/run.sh                   # 常驻，对线上；幂等，已在跑就不动
python pipeline/worker.py --base http://localhost:8787 --once   # 本地 dev：处理完积压就退出
```

令牌 `PIPE_TOKEN` 来自环境变量或 `~/.secrets/nordic-photos.env`（本地 dev 读 `photos/.dev.vars`），都不进仓库。

### AI 改图走哪条路

**模型不在本机跑。** GPU 端通过一个模型网关（`foundry_aws_gateway`）拿短期凭证，去调 Google Vertex 和 OpenAI 官方接口：

| 前端选项 | 实际模型 id | 服务方 | 实测耗时 |
|---|---|---|---|
| Nano Banana 2（默认） | `gemini-3.1-flash-image` | Google Vertex | ~12 s |
| Nano Banana Pro | `gemini-3-pro-image` | Google Vertex | ~18 s |
| GPT Image 2 | `gpt-image-2` | OpenAI 官方 | ~26 s |

网关的 Python 包不在这个仓库，也不在 PyPI：用环境变量 `GATEWAY_SRCS` 指向它的源码目录（或写进 `~/.secrets/nordic-photos.env`）。拿不到网关时 AI 改图按钮自动隐藏，其余功能不受影响；也可以用 `--no-edit` 显式关掉。

改好的图：送进模型前长边缩到 2048；输出存成 JPEG，**带上原图的拍摄时间和 GPS**（下载回手机相册也排在原图旁边），不写相机型号；它不参与连拍分组（否则会和原图并成一组、被「相似只留最好」藏掉）。

### 阈值是怎么定的

都在测试集上量过（`pipeline/cluster.py` 里每个常数旁边写着实测值）：

| 判断 | 阈值 | 依据 |
|---|---|---|
| 两簇脸是同一个人 | 平均余弦 ≥ 0.36 | 同一个人不同照片 0.41–0.76；不同的人最高 0.23 |
| 自动归人 | ≥ 0.40 且比第二像的人高 0.05 | 写名字比分簇后果大，稍严 |
| 连拍（几乎一样） | SigLIP ≥ 0.88，或 10 秒内 ≥ 0.85；3 分钟内、300 米内 | 同一张轻糊 0.96 / 重糊 0.85–0.87；两个不同的瀑布 0.91、同一冰河湖两个机位 0.84 |
| 新的一段「时刻」 | 隔 45 分钟或移动 2 公里 | — |
| ★ 时刻 | 模型打 ≥4 分、段里至少两张 ≥4（或一张 5），且最多占三分之一 | 原来 13 段里 11 段带 ★，等于没标 |

## 部署

```bash
cd photos && wrangler deploy           # 相册 Worker（先部署它，主站的 service binding 指向它）
cd .. && wrangler deploy               # 主站
```

secret 只用 `wrangler secret put`（`ALBUM_PASS` · `SESSION_SECRET` · `PIPE_TOKEN`），不进仓库。

## 测试

```bash
python test/e2e.py   http://localhost:8787            # 服务端：鉴权、上传、去重、续传、下载、zip、搜索、人物……
python test/ui.py    http://localhost:8787            # Playwright：手机 / 桌面两种尺寸走一遍界面
python test/pipe_e2e.py http://localhost:8787         # 真照片 + 真模型 + 真 AI 改图（自己起 worker.py）
python test/pipe_e2e.py https://nordic.airacle.com --external   # 线上：常驻 worker 已在跑，只看结果
```

测试素材（Wikimedia Commons 风景 + 公众人物的公开照片）在本地盘上，不进仓库；每轮结束（包括失败）会把本轮的文件、用户、人物、搜索词、改图记录全部删掉。
