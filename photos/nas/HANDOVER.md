# 交接：把共享相册的「原件」迁到这台 NAS（冷存储）

> 给 NAS 上的 agent。你看不到之前的对话，所以这份文档自包含。先通读一遍再动手。

## 0. 一句话

我们有一个共享相册服务（Cloudflare Worker + R2 + 一个 GPU 分析端）。**照片和视频的原件占了 99% 的空间，Cloudflare 这边快放不下了。**
你的任务是在这台 NAS 上搭一个**冷存储**，让相册把原件慢慢搬过来；R2 继续放缩略图 / 预览 / 新上传的（热）。**异构是常态**：有的照片已经搬过来了、有的还在 R2，读起来完全一样，所以可以一张一张慢慢迁、随时停、随时回头。

## 1. 先读这些（都在仓库里，分支名别搞错）

```
仓库   https://github.com/oyzh888/nordic-trip-2026.git
分支   zouyang/photos-r2-authoritative          ⛔ 不要推 main，不要改别人的分支；有改动请新建 zouyang/ 开头的分支再说
```

| 文件 | 内容 |
|---|---|
| `photos/docs/COLD-STORE.md` | **设计 + 安全阀 + 分阶段上线 + 接口 + 配置（必读）** |
| `photos/ENGINE.md` | 相册引擎的分层和接口契约（了解背景） |
| `photos/nas/docker-compose.yml` + `cold.env.example` | 你要部署的东西：blobd + 搬运工 + 可选隧道 |
| `photos/nas/cold_mover.py` | 搬运工（纯标准库）。`--help` 看全部子命令：`run / status / scrub / check / gc` |
| `photos/local/blobd.mjs` | NAS 上的文件存储服务（Node，约 140 行，读它就知道它做什么） |
| `photos/test/cold_e2e.py` | 43 项端到端测试，说明了每个行为的预期（本机跑过，全过） |

## 2. 你要做的（分阶段，每一步验过再走下一步）

### 阶段 A —— 摸清这台机器（只读，先别装东西）

用一条命令的输出回答下面每一项，**写进最后的报告**：

- [ ] 有没有 Docker / `docker compose`？（`docker --version`、`docker compose version`）没有的话，blobd 可以直接用 `node`（≥ 20）跑，搬运工只要 `python3`；告诉我你选哪条路。
- [ ] 放原件的目录：哪个卷、**剩余空间**（相册现在约 **400 GB**，请留 ≥ 1 TB 余量）、文件系统类型、**磁盘阵列级别**（RAID1 / 5 / 6 / SHR / 单盘？）。
- [ ] 这台 NAS 的**公网下载 / 上传带宽**（`speedtest` 之类，或估算）—— 全量复制受下载带宽限制，读已搬走的原件受上传带宽限制。
- [ ] 这台机器上**已经有没有 `cloudflared`**（有的话它挂着哪些主机名、跑在 Docker 的哪个网络里 / 是不是 host 网络）。有的话我们可以复用，不必新建隧道。
- [ ] 有没有现成的备份 / 快照机制（因为之后 NAS 会是原件的**唯一副本**）。

### 阶段 B —— 起存储（`blobd`），先不接任何东西

先定义一个小函数（后面所有 `mv …` 都是它；它在搬运工容器里跑，令牌从 `.env` 来，不用你导出环境变量）：
```bash
cd photos/nas
mv() { docker compose --env-file ~/photos-cold.env run --rm --no-deps mover sh -c 'exec python /app/cold_mover.py "$@" --engine "$ENGINE_URL" --blobd http://blobd:41071' sh "$@"; }
```
没有 Docker 的话：`export` 好 `PIPE_TOKEN` `BLOBD_TOKEN`（别回显），直接 `python3 cold_mover.py … --engine https://… --blobd http://127.0.0.1:41071`。

1. 克隆仓库（上面的分支）；`cd photos/nas && cp cold.env.example ~/photos-cold.env && chmod 600 ~/photos-cold.env`（配置放在 git 工作区**之外**）。后面所有 `docker compose` 命令都加 `--env-file ~/photos-cold.env`。
2. **自己生成两把令牌**写进 `~/photos-cold.env`（`chmod 600`）：
   ```
   openssl rand -hex 32   # → BLOBD_TOKEN       全权限，只在内网用，绝不出隧道
   openssl rand -hex 32   # → BLOBD_EDGE_TOKEN  只读 + 删，给 Cloudflare 上的 Worker 用
   ```
   ⛔ **令牌不要打印到终端 / 日志 / 回复里，也不要写进任何会进 git 的文件。** 汇报时只说长度和文件路径。
3. 设 `COLD_DATA_DIR`（阶段 A 选好的目录；这台 NAS 用 `/volume2/UserFolder/photos-cold`，RAID1）、`ENGINE_URL=https://nordic.airacle.com`。
4. `docker compose --env-file ~/photos-cold.env up -d blobd`，等 healthy。验证（在 NAS 上，端口没映射到宿主机，所以要进容器网络里验）：
   ```bash
   docker compose exec blobd wget -qO- --header "x-blobd-token: $BLOBD_TOKEN" http://127.0.0.1:41071/health   # 应返回 {"ok":true,...}
   docker compose exec blobd wget -S -qO- http://127.0.0.1:41071/health 2>&1 | head -1                         # 无令牌应是 403
   ```

### 阶段 C —— 让 Cloudflare 上的 Worker 能经隧道读到它

Worker 在 Cloudflare 上，够不着 NAS 的内网，要经 **Cloudflare Tunnel** 暴露一个主机名，**令牌保护**（这个账号没有 Zero Trust Access，所以保护靠 `BLOBD_EDGE_TOKEN`）。

- **路 1（推荐）新建隧道**：Steve 在 Cloudflare Zero Trust 里建一条隧道，给你 `TUNNEL_TOKEN`；Public Hostname 指到 `http://blobd:41071`；`docker compose --profile tunnel up -d`。
- **路 2 复用已有 cloudflared**：如果阶段 A 发现已有的 cloudflared 和 blobd 能互相访问到（同一个 Docker 网络，或把 blobd 的端口只绑 `127.0.0.1` 并发布出来给 host 网络的 cloudflared 用），就在那条隧道里加一个 Public Hostname。**⛔ 不要动已有的那些主机名（里面有别的服务在用），只加新的。**
- 主机名由 Steve 定（要在放相册 Worker 的同一个 Cloudflare 账号下）。**不要把主机名写进仓库。**

验证（从 NAS **外面**，比如你的机器或随便一台能上网的，走公网）：
```bash
curl -s -o /dev/null -w '%{http_code}\n' https://<主机名>/health                                   # 应是 403（无令牌）
curl -s -o /dev/null -w '%{http_code}\n' -H "x-blobd-token: $BLOBD_EDGE_TOKEN" https://<主机名>/health   # 应是 200
curl -s -o /dev/null -w '%{http_code}\n' -X PUT -H "x-blobd-token: $BLOBD_EDGE_TOKEN" -d x https://<主机名>/o/x/t   # 应是 403（edge 令牌不能写）
```

**然后停下来，把这些告诉 Steve**（用 §5 的格式）：隧道主机名 + 「`BLOBD_EDGE_TOKEN` 在 `<路径>/.env` 里」。Steve 会：
1. 把主机名和 `BLOBD_EDGE_TOKEN` 设成 Worker 的 secret（`COLD_URL` / `COLD_TOKEN`）并部署引擎（**这一步你不做，也没有这个权限**）；
2. 把 `PIPE_TOKEN` 给你（用来调相册的搬运接口 + 下载原件）。
你**不要**自己去改线上 Worker 的绑定或 secret。

### 阶段 D —— 金丝雀（只搬 20 个）

Steve 说引擎已部署、给了 `PIPE_TOKEN` 之后：

1. `.env` 里填 `PIPE_TOKEN`，保持 `MOVER_ARGS=--limit 20`。
2. 先 dry-run 看清单：`mv run --dry-run`
3. `docker compose up -d mover`，看日志：应该出现 `搬了 20/20 个`。
4. 验证（**每一项都要做**）：
   ```bash
   mv status                  # 「NAS 有核对过的」= 20；「R2 已释放」= 0（现在绝对不能有）
   mv scrub                   # 把 NAS 上的 20 个读回来重算内容 ID，应全对
   mv check --sample 3        # 走公网读回来，内容 ID 对；记下 Mbps
   ```
5. **这一步以后 R2 里那份原件一个都还没动**。确认无误后再进下一阶段。

### 阶段 E —— 全量复制（仍然不删 R2）

`.env` 的 `MOVER_ARGS` 改成空，`docker compose up -d mover`（重建）。它会一直守着搬，新传的照片过 10 分钟 + 分析完成后也会接着搬。
- 每过一阵看 `status`；全量完成的标志：「只在 R2」里剩下的都是还没分析完 / 缩略图没好的新照片。
- 全量完成后：`scrub --sample 200` 应全对；NAS 上 `o/` 和 `g/` 的文件数、总字节 ≈ `status` 里「NAS 有核对过的」。
- 搬运速度大概多少 MB/s、预计多久，请告诉 Steve。

### 阶段 F —— 释放 R2（⚠️ 不可逆，要 Steve 明确说「可以释放」）

**只有 Steve 明确同意后才做。** 在此之前不要给搬运工加 `--release-after-days`。同意后：
1. 先释放 5 个（金丝雀）：`mv run --once --release-after-days 0 --release-limit 5`，然后 `mv check --h <这 5 个的 h>`（走用户真实路径读，内容 ID 要对）。
2. 没问题再改成常驻 `--release-after-days 14`（搬完 14 天后才删 R2 副本，这 14 天两份都在）。

## 3. 绝对不要做的

- ⛔ 不要打印 / 记录 / 提交任何令牌（`BLOBD_TOKEN`、`BLOBD_EDGE_TOKEN`、`PIPE_TOKEN`、`TUNNEL_TOKEN`）。只汇报长度和文件路径。
- ⛔ 不要在 Steve 同意之前释放 R2 副本（不加 `--release-after-days`）。
- ⛔ 不要改线上 Worker / R2 / 数据库的任何配置；你只通过 `cold_mover.py` 调那 5 个 `cold-*` 接口。
- ⛔ 不要把 blobd 的端口直接映射到公网或宿主机的所有网卡；外面只能经隧道 + 令牌。
- ⛔ 不要动这台 NAS 上别的服务（尤其是已有的 `cloudflared` 主机名和别的容器）。
- ⛔ 不要删除 NAS 上 `COLD_DATA_DIR` 里的任何文件（孤儿清理 `gc` 默认只列，`--apply` 要 Steve 同意）。
- ⛔ 公开仓库里**不要写**主机名、IP、路径、令牌 —— 这些只放在 NAS 本机的 `.env` 里。

## 4. 相册本身（想访问的话）

- 地址：`https://nordic.airacle.com/photos/`（需要口令 + 名字；你不需要进去，搬运工走令牌）。
- 接口契约见 `photos/ENGINE.md`；搬运相关接口见 `photos/docs/COLD-STORE.md` 的「接口」一节。
- 鉴权：`Authorization: Bearer <PIPE_TOKEN>`。`GET /photos/f/<h>/o` 取原件、`GET /photos/api/pipe/cold-status` 看进度。
- 内容 ID `h` 的算法：每 8 MB 一块各算 SHA-256，再对这串哈希算一次 SHA-256（`cold_mover.py` 里的 `Cid` 类就是它）。文件名里的 `h` 必须等于文件内容的这个值，所以任何一个文件都能被独立验证。

## 5. 汇报格式（每个阶段结束都按这个报）

```
阶段：A / B / C / D / E / F
结果：通过 / 卡住（一句话原因）
证据：<命令 + 关键输出（不含令牌）>
数字：NAS 剩余空间 · 已搬个数 / 字节 · 速度 MB/s · scrub 不对的个数
需要 Steve：<要他做的事，没有就写「无」>
下一步：<你准备做什么>
```

## 6. 常见问题

| 现象 | 多半是 |
|---|---|
| 搬运工报 `ConnectionRefusedError` | blobd 没起 / 容器网络里名字不是 `blobd` |
| `cold-done` 回 `不在冷存储里` | 隧道没通、`COLD_URL` / `COLD_TOKEN` 没配对，或 blobd 里真没有这个文件 —— 引擎是**从公网经隧道**核对的 |
| `cold-done` 回 `大小 X ≠ 应有 Y` | 写进 NAS 的文件不完整（磁盘满了？），重跑一遍会重新下载覆盖 |
| `409 冷存储没配` | Worker 还没设 `COLD_URL` / `COLD_TOKEN`（阶段 C 之后 Steve 做） |
| `503 冷存储暂时连不上` | 这是**设计行为**：NAS / 隧道断了，读已释放的原件会这样；缩略图、预览、上传不受影响。恢复后自动好 |
