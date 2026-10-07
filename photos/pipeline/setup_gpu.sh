#!/usr/bin/env bash
# GPU 分析端的运行环境：Python venv + 三个模型。机器（pod）重建后 /mnt/localssd 会清空，跑这一个脚本就能装回来。
# 幂等：已经装好的跳过。约 10～20 分钟（大头是 Qwen3-VL-8B 的 16 GB 权重）。
#   bash photos/pipeline/setup_gpu.sh && bash photos/pipeline/run.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
VENV=${PHOTOS_VENV:-/mnt/localssd/venvs/photos}
export HF_HOME=${HF_HOME:-/mnt/localssd/.cache/huggingface}
export INSIGHTFACE_HOME=${INSIGHTFACE_HOME:-/mnt/localssd/.cache/insightface}
export UV_CACHE_DIR=${UV_CACHE_DIR:-/mnt/localssd/.cache/uv}
mkdir -p "$(dirname "$VENV")" "$HF_HOME" "$INSIGHTFACE_HOME"
[ -x "$VENV/bin/python" ] || uv venv -q -p 3.11 "$VENV"
# AI 改图走模型网关：它的客户端库还需要这几个（库本身用源码路径 GATEWAY_SRCS 引入，不安装）
uv pip install -q --python "$VENV/bin/python" -r "$HERE/requirements.txt" boto3 filelock msal 'types-boto3[s3,bedrock-runtime]'
# insightface 依赖的是 CPU 版 onnxruntime，会盖掉 GPU 版（人脸识别只能跑 CPU）→ 卸掉它、重装 GPU 版
uv pip uninstall -q --python "$VENV/bin/python" onnxruntime 2>/dev/null || true
uv pip install -q --python "$VENV/bin/python" --reinstall onnxruntime-gpu
"$VENV/bin/python" - <<'PY'
import os
from huggingface_hub import snapshot_download
for m in ['google/siglip2-so400m-patch14-384', 'Qwen/Qwen3-VL-8B-Instruct']:
    print('模型', m, snapshot_download(m, allow_patterns=['*.json', '*.safetensors', '*.txt', '*.model', '*.jinja']), flush=True)
from insightface.app import FaceAnalysis      # 第一次调用时自动下载 buffalo_l
FaceAnalysis(name='buffalo_l', root=os.environ['INSIGHTFACE_HOME'], providers=['CPUExecutionProvider'])
print('人脸模型 buffalo_l ok')
PY
"$VENV/bin/python" -c "import torch, onnxruntime as o; p = o.get_available_providers(); print('GPU', torch.cuda.is_available(), p[:2]); assert 'CUDAExecutionProvider' in p, '人脸模型没认到 GPU'"
# 佳能官方 LUT（Canon Log 3 → 正常观看的颜色，视频新版调色用，见 video.py）。版权归佳能、不进仓库：从佳能下载、对哈希、只解出要用的两张表
LUT=${CANON_LUT_DIR:-/mnt/localssd/photos-cache/lut}
mkdir -p "$LUT"
lut() {   # 下载地址 · sha256 · 要解出来的文件
  local url=$1 sum=$2 file=$3 zip="$LUT/$(basename "$1")"
  [ -s "$LUT/$file" ] && return 0
  [ -s "$zip" ] && echo "$sum  $zip" | sha256sum -c --quiet 2>/dev/null || curl -sSfL --retry 3 -o "$zip" "$url"
  echo "$sum  $zip" | sha256sum -c --quiet || { echo "❌ 佳能 LUT 的哈希对不上：$zip"; exit 1; }
  (cd "$LUT" && unzip -oq "$zip" "$file")
}
# 「Canon 3D LUT for Canon 709 Ver.1.0.0」（Canon Log 2/3 · Cinema Gamut → Canon 709）
lut https://gdlp01.c-wss.com/gds/7/0200007477/01/canon-lut-canon709-202508.zip \
    a2e837414847e0686e7cd9db47f4bb898f6e1730e7dc20c2ded42101de7abdf8 \
    canon-lut-canon709-202508/65grid-3dlut/CinemaGamut_CanonLog3-to-Canon709_65_Ver.1.0.cube
# 「Canon lookup table ver.202510」里 BT.2020 色域那张（R5 的 Canon Log 设成 BT.2020 时用）
lut https://gdlp01.c-wss.com/gds/2/0200007512/01/canon-lut-202510.zip \
    570a47a20504018dad4e5f31869697129a26a069a95616aec9f085e565f63f31 \
    canon-lut-202510/3dlut/65grid-3dlut/full-to-full-range/BT2020_CanonLog3-to-BT709_WideDR_65_FF_Ver.2.0.cube
echo "佳能 LUT ok：$LUT"
echo "✅ 环境就绪：$VENV"
