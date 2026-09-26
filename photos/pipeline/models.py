"""三个模型，都常驻在一张 GPU 上（合计 ~22 GB 显存）：

· Qwen3-VL-8B —— 看图写中文描述 + 结构化标签（物体 / 英文别名 / 特殊场景 / 纪念价值 / 观感分）
· SigLIP2 so400m —— 图文同一个向量空间：图存 int8 向量，搜索词实时算向量，点积就是「像不像」
· InsightFace buffalo_l —— 人脸检测 + 512 维身份向量（同一个人不同照片余弦 0.41–0.76，不同的人 ≤ 0.23）
"""
import base64
import json
import re

import numpy as np
import torch
from PIL import Image

QWEN = 'Qwen/Qwen3-VL-8B-Instruct'
SIGLIP = 'google/siglip2-so400m-patch14-384'

# 「特殊场景」是一张封闭的词表 —— 前端按它做筛选 chip，词表开放的话同一件事会冒出三种说法
SPECIAL = ['极光', '合影', '自拍', '日落', '日出', '星空', '瀑布', '冰川', '冰河湖', '黑沙滩', '火山', '温泉', '雪山',
           '峡湾', '彩虹', '野生动物', '海鹦', '鲸鱼', '驯鹿', '教堂', '城堡', '城市夜景', '美食', '游船', '自驾', '机场']

PROMPT = f"""你在给一本旅行相册（北欧：冰岛 / 挪威 / 丹麦 / 英国 / 葡萄牙 / 法国）整理照片。看这张图，只输出一个 JSON，不要别的文字：
{{
 "caption": "一句自然的中文描述，20–40 字，说清楚拍的是什么、在干什么、什么氛围",
 "objects": ["图里看得见的主要东西，中文名词，3–8 个"],
 "scene": ["场景类型，中文，1–3 个，比如 夜景 / 海边 / 山路 / 餐厅 / 街道 / 室内 / 车内"],
 "en": ["同样内容的英文关键词，3–8 个，小写"],
 "alias": ["别人搜这张照片时可能用的其他中文说法，0–5 个，比如 北极光 / 冰山 / 大巴"],
 "special": ["只能从这个列表里选，符合的才选，可以为空：{' / '.join(SPECIAL)}"],
 "people": 画面里能看清的人数（整数）,
 "memo": 1–5 的整数，这张照片的纪念价值（5 = 极光、全员合影、壮观地标这种以后一定会翻出来看的；1 = 票据、截图、拍糊的随手拍）,
 "quality": 1–5 的整数，单纯从摄影角度的观感（清晰度、构图、曝光）
}}"""

TITLE_PROMPT = """下面是旅行中同一段时间、同一个地方拍的 {n} 张照片的描述。给这段经历起一个中文小标题（4–12 个字，像相册里的章节名，
可以带地名，不要标点和引号），再给它的纪念价值打 1–5 分。只输出 JSON：{{"title": "...", "memo": 整数}}

地点：{place}
时间：{when}
照片：
{caps}"""


def _json(s):
    m = re.search(r'\{.*\}', s, re.S)
    if not m:
        return {}
    t = m.group(0)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        t = re.sub(r',\s*([}\]])', r'\1', t)        # 模型偶尔会多一个逗号
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            return {}


def _strs(x, n):
    if isinstance(x, str):
        x = re.split(r'[,，、/]', x)
    return [str(s).strip()[:24] for s in (x or []) if str(s).strip()][:n]


def clean_tags(d):
    """模型输出 → 存进 media.tags 的结构（字段和 album.js buildIndex / app.js 对得上）"""
    sp = [s for s in _strs(d.get('special'), 8) if s in SPECIAL]
    def i15(k, dflt):
        try:
            return int(min(5, max(1, round(float(d.get(k))))))
        except (TypeError, ValueError):
            return dflt
    return {
        'caption': str(d.get('caption') or '').strip()[:120],
        'tags': {'objects': _strs(d.get('objects'), 8), 'scene': _strs(d.get('scene'), 3),
                 'en': [s.lower() for s in _strs(d.get('en'), 8)], 'alias': _strs(d.get('alias'), 5),
                 'special': sp, 'memo': i15('memo', 2)},
        'people': d.get('people') if isinstance(d.get('people'), int) else None,
        'quality': i15('quality', 3),
    }


class Models:
    def __init__(self, device='cuda', vlm=True):
        from transformers import AutoModel, AutoProcessor
        self.dev = device
        self.sig = AutoModel.from_pretrained(SIGLIP, dtype=torch.bfloat16).to(device).eval()
        self.sigp = AutoProcessor.from_pretrained(SIGLIP)
        self.siglip_ab = (float(self.sig.logit_scale.exp()), float(self.sig.logit_bias))
        self.vlm = self.vlmp = None
        if vlm:
            from transformers import AutoModelForImageTextToText
            self.vlm = AutoModelForImageTextToText.from_pretrained(QWEN, dtype=torch.bfloat16, device_map=device).eval()
            self.vlmp = AutoProcessor.from_pretrained(QWEN)
            self.vlmp.tokenizer.padding_side = 'left'
        from insightface.app import FaceAnalysis
        import os
        self.face = FaceAnalysis(name='buffalo_l', root=os.environ.get('INSIGHTFACE_HOME', '/mnt/localssd/.cache/insightface'),
                                 providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
                                 allowed_modules=['detection', 'recognition'])
        self.face.prepare(ctx_id=0, det_size=(960, 960))

    # ---------- SigLIP2 ----------
    @torch.no_grad()
    def embed_images(self, ims):
        x = self.sigp(images=ims, return_tensors='pt').to(self.dev)
        f = self.sig.get_image_features(**x)
        f = f.pooler_output if hasattr(f, 'pooler_output') else f
        return torch.nn.functional.normalize(f.float(), dim=-1).cpu().numpy()

    @torch.no_grad()
    def embed_texts(self, qs):
        # SigLIP 训练时文本是小写、补齐到 64 —— 不这样做向量会偏
        x = self.sigp(text=[q.lower() for q in qs], padding='max_length', max_length=64, truncation=True,
                      return_tensors='pt').to(self.dev)
        f = self.sig.get_text_features(**x)
        f = f.pooler_output if hasattr(f, 'pooler_output') else f
        return torch.nn.functional.normalize(f.float(), dim=-1).cpu().numpy()

    # ---------- Qwen3-VL ----------
    @torch.no_grad()
    def _gen(self, msgs, max_new):
        x = self.vlmp.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True,
                                          return_tensors='pt', processor_kwargs={'padding': True}).to(self.dev)
        o = self.vlm.generate(**x, max_new_tokens=max_new, do_sample=False)
        return self.vlmp.batch_decode(o[:, x['input_ids'].shape[1]:], skip_special_tokens=True)

    def describe(self, ims):
        """一批图 → [clean_tags 结果]。图先缩到长边 896（约 600 个视觉 token），标签质量几乎不掉、速度快 3 倍"""
        small = []
        for im in ims:
            im = im.copy()
            im.thumbnail((896, 896), Image.LANCZOS)
            small.append(im)
        msgs = [[{'role': 'user', 'content': [{'type': 'image', 'image': im}, {'type': 'text', 'text': PROMPT}]}] for im in small]
        return [clean_tags(_json(s)) for s in self._gen(msgs, 360)]

    def title(self, caps, place, when):
        msg = [{'role': 'user', 'content': [{'type': 'text', 'text': TITLE_PROMPT.format(
            n=len(caps), place=place or '未知', when=when, caps='\n'.join(f'- {c}' for c in caps[:24]))}]}]
        d = _json(self._gen([msg], 60)[0])
        t = re.sub(r'[「」"“”《》。，,!！]', '', str(d.get('title') or '')).strip()[:16]
        try:
            memo = int(min(5, max(1, round(float(d.get('memo'))))))
        except (TypeError, ValueError):
            memo = None
        return t, memo

    # ---------- InsightFace ----------
    def faces(self, im):
        """RGB 图 → [{x,y,w,hh（0–1 相对坐标）, score, emb（base64 float16）, _v（numpy，本地聚类用）, _px（像素边长）}]"""
        W, H = im.size
        s = min(1, 1920 / max(W, H))
        small = im.resize((round(W * s), round(H * s))) if s < 1 else im
        bgr = np.asarray(small)[:, :, ::-1].copy()
        out = []
        for f in self.face.get(bgr):
            x0, y0, x1, y1 = [float(v) for v in f.bbox]
            sw, sh = small.size
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(sw, x1), min(sh, y1)
            px = min(x1 - x0, y1 - y0)
            if f.det_score < 0.55 or px < 20:
                continue
            v = f.normed_embedding.astype(np.float32)
            out.append({'x': round(x0 / sw, 5), 'y': round(y0 / sh, 5), 'w': round((x1 - x0) / sw, 5), 'hh': round((y1 - y0) / sh, 5),
                        'score': round(float(f.det_score), 4), 'emb': base64.b64encode(v.astype(np.float16).tobytes()).decode(),
                        '_v': v, '_px': px})
        return out


def q8(v):
    """float 向量 → int8 + 比例（相册服务端按 dot(query, int8) * scale 打分）"""
    scale = float(np.abs(v).max() / 127) or 1e-8
    return base64.b64encode(np.round(v / scale).clip(-127, 127).astype(np.int8).tobytes()).decode(), scale


def face_vec(b64):
    return np.frombuffer(base64.b64decode(b64), dtype=np.float16).astype(np.float32)
