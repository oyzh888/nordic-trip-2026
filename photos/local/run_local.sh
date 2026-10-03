#!/usr/bin/env bash
# 相册跑在本机：同一份 Worker 代码交给 workerd（wrangler dev 的本地运行时），
# R2 / Durable Object 的数据全部落在 $STORE/state（本地 NVMe），不再用 Cloudflare 的存储，也就没有免费额度这回事。
# 对外：Cloudflare Tunnel（photos.airacle.com → 127.0.0.1:$PORT），见 tunnel.sh。
# 幂等：重复执行 = 用当前代码重启服务（数据不动）。
#   用法：bash photos/local/run_local.sh            # 重启 Worker + GPU 端
set -euo pipefail
STORE=${PHOTOS_STORE:-/mnt/localssd/photos-store}
PORT=${PHOTOS_PORT:-41069}
SESS=${PHOTOS_SESSION:-photos-local}
# files = 照片存成 $STORE/files 下的普通文件，由 blobd（多进程、直接读写磁盘）管；
# r2    = 旧模式：wrangler dev 里用 JS 模拟的 R2（单线程，上传 60～70 MB/s 封顶）
STORE_MODE=${STORE_MODE:-r2}
BLOBD_PORT=${BLOBD_PORT:-$((PORT + 100))}
ENVF=${PHOTOS_ENV:-$HOME/.secrets/nordic-photos.env}
MAX_BYTES=${MAX_BYTES:-500000000000}            # 500 GB：照片 + 缩略图 + 数据库合计，超了拒绝新上传
MIN_FREE_BYTES=${MIN_FREE_BYTES:-200000000000}  # 整块盘剩余低于 200 GB 也拒绝（盘上不只有相册）
HERE=$(cd "$(dirname "$0")/.." && pwd)

mkdir -p "$STORE/app" "$STORE/state" "$STORE/logs"
# 代码拷一份到 $STORE/app 再跑：在仓库里改代码不会让线上服务跟着热重载
rsync -a --delete "$HERE/src" "$HERE/public" "$STORE/app/"
sed 's/"workers_dev": true,/"workers_dev": false,/' "$HERE/wrangler.jsonc" > "$STORE/app/wrangler.jsonc"
( set -a; . "$ENVF"; set +a
  umask 077
  { echo "ALBUM_PASS=$ALBUM_PASS"; echo "SESSION_SECRET=$SESSION_SECRET"; echo "PIPE_TOKEN=$PIPE_TOKEN"
    [ -n "${ORIGIN_KEY:-}" ] && echo "ORIGIN_KEY=$ORIGIN_KEY"
    if [ "$STORE_MODE" = files ]; then echo "BLOBD=http://127.0.0.1:$BLOBD_PORT"; echo "BLOBD_TOKEN=$BLOBD_TOKEN"; fi
    echo "MAX_BYTES=$MAX_BYTES"; echo "MIN_FREE_BYTES=$MIN_FREE_BYTES"; } > "$STORE/app/.dev.vars" )

if [ "$STORE_MODE" = files ]; then
  mkdir -p "$STORE/files"
  tmux kill-session -t "=$SESS-blobd" 2>/dev/null || true
  ( set -a; . "$ENVF"; set +a
    tmux new -d -s "$SESS-blobd" "while true; do BLOBD_DIR='$STORE/files' BLOBD_PORT=$BLOBD_PORT BLOBD_TOKEN='$BLOBD_TOKEN' BLOBD_PROCS=\${BLOBD_PROCS:-8} \
      node '$HERE/local/blobd.mjs' 2>&1 | tee -a '$STORE/logs/blobd.log'; sleep 2; done" )
  for i in $(seq 20); do curl -s -m 2 -o /dev/null -H "x-blobd-token: $( set -a; . "$ENVF"; echo "$BLOBD_TOKEN")" "http://127.0.0.1:$BLOBD_PORT/health" && break; sleep 0.5; done
  echo "blobd: $(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:$BLOBD_PORT/health) on :$BLOBD_PORT（无令牌应为 403）"
fi
tmux kill-session -t "=$SESS" 2>/dev/null || true
if [ "$STORE_MODE" = files ]; then
  # 不用 wrangler dev：它挂的调试器会把 Worker 发出的每个请求连同响应体抄给 Node，从 blobd 取照片时下载卡死（见 serve.mjs）
  tmux new -d -s "$SESS" "while true; do APP_DIR='$STORE/app' STATE_DIR='$STORE/state' PORT=$PORT node '$HERE/local/serve.mjs' 2>&1 | tee -a '$STORE/logs/worker.log'; sleep 3; done"
else
tmux new -d -s "$SESS" "cd '$STORE/app' && while true; do wrangler dev --local --ip 127.0.0.1 --port $PORT \
  --persist-to '$STORE/state' --live-reload=false --show-interactive-dev-session=false 2>&1 | tee -a '$STORE/logs/worker.log'; sleep 3; done"
fi
for i in $(seq 60); do curl -s -o /dev/null -m 3 "http://127.0.0.1:$PORT/photos/" && break; sleep 1; done
echo "worker: $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/photos/) on :$PORT"
