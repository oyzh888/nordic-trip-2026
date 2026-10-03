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
echo "✅ 环境就绪：$VENV"
