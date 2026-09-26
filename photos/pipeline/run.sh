#!/usr/bin/env bash
# 常驻启动 GPU 分析端（对线上 nordic.airacle.com）。幂等：已经在跑就什么都不做 —— 可以放进 cron 当保活。
#   bash photos/pipeline/run.sh            # 起在 tmux 会话 photos-pipe 里
#   tmux attach -t photos-pipe             # 看实时日志
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PHOTOS_PY:-/mnt/localssd/venvs/photos/bin/python}"
LOG="${PHOTOS_LOG:-${PHOTOS_CACHE:-/mnt/localssd/photos-cache}/worker.log}"
mkdir -p "$(dirname "$LOG")"

# 先查再起：只有真的没在跑才启动（[w] 括号防止 pgrep 匹配到自己）
if pgrep -f "pipeline/[w]orker.py --base https://nordic.airacle.com" >/dev/null; then
  echo "已经在跑：$(pgrep -f 'pipeline/[w]orker.py --base https://nordic.airacle.com' | tr '\n' ' ')"
  exit 0
fi
if tmux has-session -t photos-pipe 2>/dev/null; then
  echo "tmux 会话 photos-pipe 在，但 worker 进程不在 —— 看一眼 $LOG 再决定（不自动杀）"
  exit 1
fi
tmux new -d -s photos-pipe "cd '$HERE/..' && while true; do '$PY' pipeline/worker.py --base https://nordic.airacle.com 2>&1 | tee -a '$LOG'; echo \"[\$(date -Is)] worker 退出，30 秒后重启\" | tee -a '$LOG'; sleep 30; done"
echo "已启动：tmux attach -t photos-pipe   日志 $LOG"
