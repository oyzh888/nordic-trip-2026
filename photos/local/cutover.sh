#!/usr/bin/env bash
# 正式相册从「wrangler dev + 模拟 R2」切到「Miniflare + blobd（普通文件）」。停机约 10～20 秒。
#   bash photos/local/cutover.sh            # 切换
#   bash photos/local/cutover.sh rollback   # 退回旧模式（旧存储一个字节都没动过；但切换之后新传的文件旧模式里没有）
# 数据库（Durable Object 的 SQLite）两种模式共用同一份，不需要搬。
set -euo pipefail
STORE=${PHOTOS_STORE:-/mnt/localssd/photos-store}
PORT=${PHOTOS_PORT:-41069}
HERE=$(cd "$(dirname "$0")/.." && pwd)
PY=/mnt/localssd/venvs/photos/bin/python
set -a; . "$HOME/.secrets/nordic-photos.env"; set +a
api() { curl -s -m 30 -H "Authorization: Bearer $PIPE_TOKEN" "$@"; }
ts() { date +%T; }

if [ "${1:-}" = rollback ]; then
  echo "[$(ts)] 退回旧模式"
  tmux kill-session -t "=photos-local-blobd" 2>/dev/null || true
  STORE_MODE=r2 bash "$HERE/local/run_local.sh"
  exit 0
fi

echo "[$(ts)] 1/6 服务运行中先补导一遍（只读旧存储）"
$PY "$HERE/local/export_r2.py" "$STORE/state" "$STORE/files"
before=$(api "http://127.0.0.1:$PORT/photos/api/stats" | $PY -c "import json,sys;d=json.load(sys.stdin);print(d['items']['c'], d['uploading'])")
echo "        切换前：照片 / 未完成上传 = $before"

echo "[$(ts)] 2/6 停旧服务（停机开始）"
T0=$(date +%s)
tmux kill-session -t "=photos-local" 2>/dev/null || true
for i in $(seq 30); do curl -s -m 1 -o /dev/null "http://127.0.0.1:$PORT/" || break; sleep 0.5; done
# tmux kill-session 有时把子进程留成 T（停住）状态、还占着端口 —— 端口没放就直接结束占端口的进程
P=$(ss -ltnp 2>/dev/null | grep "127.0.0.1:$PORT " | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true)
[ -n "$P" ] && { echo "        端口还被 $P 占着，结束它"; kill $P; sleep 1; kill -9 $P 2>/dev/null || true; }
sleep 1   # 让旧 workerd 把最后的写入落盘

echo "[$(ts)] 3/6 补导停机前最后的增量"
$PY "$HERE/local/export_r2.py" "$STORE/state" "$STORE/files" --verify

echo "[$(ts)] 4/6 新模式起服务"
STORE_MODE=files bash "$HERE/local/run_local.sh"
api -X POST "http://127.0.0.1:$PORT/photos/api/pipe/reset-uploads"; echo
echo "        停机 $(( $(date +%s) - T0 )) 秒"

echo "[$(ts)] 5/6 自检"
after=$(api "http://127.0.0.1:$PORT/photos/api/stats" | $PY -c "import json,sys;d=json.load(sys.stdin);print(d['items']['c'], d['uploading'])")
echo "        切换后：照片 / 未完成上传 = $after"
[ "${before%% *}" = "${after%% *}" ] || { echo "❌ 照片数对不上，退回：bash $0 rollback"; exit 1; }
$PY - "$PORT" <<'EOF'
import os, sys, random, requests
B = f'http://127.0.0.1:{sys.argv[1]}/photos'; H = {'authorization': 'Bearer ' + os.environ['PIPE_TOKEN']}
it = requests.get(B + '/api/list', headers=H).json()['items']
bad = [i['n'] for i in random.sample(it, min(40, len(it)))
       if requests.get(f"{B}/f/{i['h']}/o", headers=H).status_code != 200 or (i['f'] & 1 and requests.get(f"{B}/f/{i['h']}/t", headers=H).status_code != 200)]
print(f'        随机抽 {min(40, len(it))} 张取原图 + 缩略图：失败 {len(bad)}', bad[:3]); sys.exit(1 if bad else 0)
EOF
(cd "$HERE/test" && timeout 120 $PY api_e2e.py "http://127.0.0.1:$PORT" | tail -n1)

echo "[$(ts)] 6/6 重启 GPU 端（磁盘用量改为统计整个 $STORE）"
tmux kill-session -t "=photos-pipe" 2>/dev/null || true
kill $(pgrep -f 'pipeline/[w]orker[.]py --base') 2>/dev/null || true
sleep 2
bash "$HERE/pipeline/run.sh"
echo "[$(ts)] ✅ 完成。全量逐个核对：$PY $HERE/local/verify_store.py http://127.0.0.1:$PORT"
