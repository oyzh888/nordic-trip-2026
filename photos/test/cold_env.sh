#!/usr/bin/env bash
# 起冷存储测试环境：模拟 NAS（blobd，:41191）+ 配了冷存储的本地 Worker（:8791）。凭证是一次性随机的，和线上无关。幂等。
#   bash test/cold_env.sh && python test/cold_e2e.py http://localhost:8791 < /dev/null
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
T=${COLD_TEST_DIR:-${TMPDIR:-/tmp}/coldtest}
mkdir -p "$T/app" "$T/nas" "$T/state"
rnd() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }
if [ ! -f "$T/creds.env" ]; then
  ( umask 077; cat > "$T/creds.env" <<EOT
ALBUM_PASS=cold-test-$(rnd 6)
SESSION_SECRET=$(rnd 32)
PIPE_TOKEN=$(rnd 32)
BLOBD_TOKEN=$(rnd 32)
BLOBD_EDGE_TOKEN=$(rnd 32)
EOT
  )
fi
set -a; . "$T/creds.env"; set +a
rsync -a --delete "$HERE/src" "$HERE/public" "$T/app/"
sed 's/"MAX_BYTES": "[0-9]*"/"MAX_BYTES": "0"/' "$HERE/wrangler.jsonc" > "$T/app/wrangler.jsonc"
( umask 077; cat > "$T/app/.dev.vars" <<EOT
ALBUM_PASS=$ALBUM_PASS
SESSION_SECRET=$SESSION_SECRET
PIPE_TOKEN=$PIPE_TOKEN
COLD_URL=http://127.0.0.1:41191
COLD_TOKEN=$BLOBD_EDGE_TOKEN
COLD_FIRST=${COLD_FIRST:-0}
EOT
)
# e2e.py 从 photos/.dev.vars 读口令（它是 .gitignore 的）—— 这里只放口令和令牌，不放 COLD_*，免得默认实例也走冷存储
grep -v '^COLD_' "$T/app/.dev.vars" > "$HERE/.dev.vars"
tmux kill-session -t cold-blobd 2>/dev/null || true
tmux new -d -s cold-blobd "BLOBD_DIR=$T/nas BLOBD_PORT=41191 BLOBD_TOKEN=$BLOBD_TOKEN BLOBD_EDGE_TOKEN=$BLOBD_EDGE_TOKEN BLOBD_PROCS=2 node $HERE/local/blobd.mjs 2>&1 | tee -a $T/blobd.log"
tmux has-session -t cold-dev 2>/dev/null || tmux new -d -s cold-dev "cd $T/app && wrangler dev --local --ip 127.0.0.1 --port 8791 --persist-to $T/state --live-reload=false --show-interactive-dev-session=false 2>&1 | tee -a $T/worker.log"
for i in $(seq 60); do curl -s -m 2 -o /dev/null http://127.0.0.1:8791/photos/ && break; sleep 1; done
echo "Worker :8791 $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8791/photos/) · 模拟 NAS :41191 $(curl -s -o /dev/null -w '%{http_code}' -H "x-blobd-token: $BLOBD_TOKEN" http://127.0.0.1:41191/health)"
