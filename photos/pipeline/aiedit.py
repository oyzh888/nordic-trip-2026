"""AI 改图：一句话改照片（Nano Banana / GPT Image）。

模型不在本机跑 —— 这台 GPU 机通过公司的模型网关（foundry_aws_gateway）去调 Google Vertex 和 OpenAI 官方接口，
所以只有「GPU 端在线、而且拿得到网关凭证」时这个功能才出现。网关的 Python 包不在这个仓库里：
用环境变量 GATEWAY_SRCS 指向它的源码目录（或写在 ~/.secrets/nordic-photos.env 里）。

    key        实际模型 id                  实测（一张 1536 px 的风景）
    nano       gemini-3.1-flash-image       ~10 s   Nano Banana 2
    pro        gemini-3-pro-image           ~17 s   Nano Banana Pro
    gpt        gpt-image-2                  ~33 s   OpenAI 官方
"""
import base64
import io
import os
import sys

from PIL import Image

MODELS = {
    'nano': ('google', 'gemini-3.1-flash-image'),
    'pro': ('google', 'gemini-3-pro-image'),
    'gpt': ('openai', 'gpt-image-2'),
}
MAX_IN = 2048          # 送给模型的图长边上限：再大模型也会自己缩，只是白白多传


class EditError(Exception):
    """给用户看的失败原因（中文）"""


class Editor:
    def __init__(self, srcs=None):
        self.g = self.oa = None
        self.why = None
        srcs = srcs or os.environ.get('GATEWAY_SRCS')
        if srcs and srcs not in sys.path:
            sys.path.insert(0, srcs)
        try:
            from foundry_aws_gateway.llm import get_google_genai, get_openai
        except ImportError as e:
            self.why = f'没有模型网关的包（GATEWAY_SRCS）：{e}'
            return
        try:
            self.g = get_google_genai(location='global')
        except Exception as e:  # noqa: BLE001
            self.why = f'Vertex 凭证拿不到：{e!r:.120}'
        try:
            self.oa = get_openai()
        except Exception as e:  # noqa: BLE001
            self.why = (self.why or '') + f' OpenAI 凭证拿不到：{e!r:.120}'

    def available(self):
        return [k for k, (v, _) in MODELS.items() if (self.g if v == 'google' else self.oa) is not None]

    @staticmethod
    def prep(im):
        im = im.copy()
        im.thumbnail((MAX_IN, MAX_IN), Image.LANCZOS)
        b = io.BytesIO()
        im.save(b, 'JPEG', quality=90)
        return b.getvalue()

    def edit(self, im, prompt, key):
        """RGB 图 + 一句话 → (新图 PIL.Image, 实际模型 id)"""
        vendor, mid = MODELS[key]
        data = self.prep(im)
        if vendor == 'google':
            from google.genai import types
            r = self.g.models.generate_content(
                model=mid, contents=[types.Part.from_bytes(data=data, mime_type='image/jpeg'), prompt],
                config=types.GenerateContentConfig(response_modalities=['IMAGE']))
            if not r.candidates:
                raise EditError(f'模型拒绝了这个请求（{getattr(r.prompt_feedback, "block_reason", None) or "内容审核"}）')
            c = r.candidates[0]
            parts = c.content.parts if c.content and c.content.parts else []
            img = next((p.inline_data for p in parts if p.inline_data and p.inline_data.data), None)
            if not img:
                fr = str(c.finish_reason or '')
                if any(x in fr for x in ('SAFETY', 'PROHIBITED', 'BLOCK', 'RECITATION')):
                    raise EditError('模型因为内容审核没改这张（换个说法，或者换 GPT Image 试试）')
                txt = ' '.join(p.text for p in parts if getattr(p, 'text', None))[:80]
                raise EditError('模型没有返回图片' + (f'：「{txt}」' if txt else '，换个说法试试'))
            out = img.data
        else:
            import openai
            try:
                r = self.oa.images.edit(model=mid, image=('in.jpg', data, 'image/jpeg'), prompt=prompt)
            except openai.BadRequestError as e:
                if 'moderation' in str(e).lower() or 'safety' in str(e).lower():
                    raise EditError('被 OpenAI 的内容审核拦下了（换个说法，或者换 Nano Banana 试试）') from e
                raise EditError(f'OpenAI 拒绝了请求：{str(e)[:100]}') from e
            out = base64.b64decode(r.data[0].b64_json)
        return Image.open(io.BytesIO(out)).convert('RGB'), mid


def encode(im, taken=None, lat=None, lon=None, software=None):
    """改好的图 → JPEG q92，带上原图的拍摄时间和位置（这样下载回去在手机相册里也排在原图旁边）。
    不写相机型号 —— 这张不是相机拍的。"""
    ex = Image.Exif()
    if software:
        ex[0x0131] = software[:60]
    if taken:
        ex.get_ifd(0x8769)[0x9003] = str(taken)[:19].replace('-', ':', 2).replace('T', ' ')
    if lat is not None and lon is not None:
        def rat(x):
            d = int(x); m = int((x - d) * 60)
            return (d, m, round(((x - d) * 60 - m) * 60, 2))
        g = ex.get_ifd(0x8825)
        g[1], g[2], g[3], g[4] = ('N' if lat >= 0 else 'S'), rat(abs(lat)), ('E' if lon >= 0 else 'W'), rat(abs(lon))
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=92, exif=ex.tobytes())
    return b.getvalue()
