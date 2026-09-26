"""读原件：EXIF / ffprobe 元数据、解码成图、生成缩略图和 720p 视频预览、画质打分。

这里全是 CPU 活（PIL / OpenCV / ffmpeg），不碰模型。输出的字段名和 Album.result() 对得上：
taken（当地墙上时间，无时区，"2026-09-27T22:14:05"）· lat/lon · w/hh（转正后的尺寸）· dur · cam。
"""
import io
import json
import math
import re
import subprocess
from datetime import datetime, timedelta

import cv2
import numpy as np
from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()
Image.MAX_IMAGE_PIXELS = 400_000_000

# 视频的 creation_time 是 UTC，照片的 EXIF 是当地时间 —— 为了两者排在同一条时间线上，视频要换成当地时间。
# iPhone 的 com.apple.quicktime.creationdate 自带时区，优先用它；没有时按国家估（本次行程 9 月底–10 月中）。
TZ = {'is': 0, 'gb': 1, 'ie': 1, 'pt': 1, 'no': 2, 'se': 2, 'dk': 2, 'de': 2, 'fr': 2, 'nl': 2, 'be': 2,
      'es': 2, 'it': 2, 'ch': 2, 'at': 2, 'mc': 2, 'fi': 3, 'ee': 3, 'us': -7}
DST_END = datetime(2026, 10, 25, 1)          # 欧洲夏令时结束（UTC 时间）；之后除冰岛外都少 1 小时


def cam_name(make, model):
    """和浏览器端 parseTiff 同一个规则：「Apple iPhone 15 Pro Max」「SONY ILCE-7M4」"""
    make, model = (make or '').strip(), (model or '').strip()
    if not model:
        return None
    m0 = make.split(' ')[0]
    return model if not make or model.lower().startswith(m0.lower()) else f'{m0} {model}'


def _rat(x):
    try:
        return float(x[0]) / float(x[1]) if isinstance(x, tuple) else float(x)
    except (TypeError, ZeroDivisionError, ValueError):
        return None


def image_meta(im):
    """PIL 图（JPEG/HEIC/PNG）的 EXIF → 拍摄时间、GPS、相机"""
    out = {}
    try:
        ex = im.getexif()
    except Exception:
        return out
    cam = cam_name(ex.get(0x010F), ex.get(0x0110))
    if cam:
        out['cam'] = cam[:60]
    sub = ex.get_ifd(0x8769)
    dt = sub.get(0x9003) or sub.get(0x9004) or ex.get(0x0132)
    m = re.match(r'(\d{4}):(\d\d):(\d\d)[ T](\d\d):(\d\d):(\d\d)', str(dt or ''))
    if m and m.group(1) != '0000':
        out['taken'] = '{}-{}-{}T{}:{}:{}'.format(*m.groups())
    g = ex.get_ifd(0x8825)
    if g.get(2) and g.get(4):
        dms = lambda a: sum(_rat(v) / d for v, d in zip(a, (1, 60, 3600))) if len(a) == 3 else None
        la, lo = dms(g[2]), dms(g[4])
        if la is not None and lo is not None and (la or lo):
            out['lat'] = -la if g.get(1) == 'S' else la
            out['lon'] = -lo if g.get(3) == 'W' else lo
    return out


def open_image(path):
    """解码 + 按 EXIF 方向转正。返回 (RGB 图, 元数据)"""
    im = Image.open(path)
    meta = image_meta(im)
    im = ImageOps.exif_transpose(im)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    meta['w'], meta['hh'] = im.size
    return im, meta


def ffprobe(path):
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', str(path)],
                       capture_output=True, text=True, timeout=120)
    return json.loads(r.stdout or '{}')


def _iso6709(s):
    m = re.match(r'([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)', s or '')
    return (float(m.group(1)), float(m.group(2))) if m else (None, None)


def video_meta(path):
    info = ffprobe(path)
    fmt = info.get('format', {})
    tags = {k.lower(): v for k, v in (fmt.get('tags') or {}).items()}
    vs = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), None)
    out = {'probe_ok': bool(vs)}
    if not vs:
        return out
    w, h = vs.get('width'), vs.get('height')
    rot = 0
    for sd in vs.get('side_data_list') or []:
        if 'rotation' in sd:
            rot = int(sd['rotation'])
    rot = rot or int((vs.get('tags') or {}).get('rotate', 0) or 0)
    if abs(rot) % 180 == 90:
        w, h = h, w
    out.update(w=w, hh=h, codec=vs.get('codec_name'))
    try:
        out['dur'] = round(float(fmt.get('duration') or vs.get('duration')), 2)
    except (TypeError, ValueError):
        pass
    la, lo = _iso6709(tags.get('com.apple.quicktime.location.iso6709') or tags.get('location'))
    if la is not None and (la or lo):
        out['lat'], out['lon'] = la, lo
    cam = cam_name(tags.get('com.apple.quicktime.make') or tags.get('make'),
                   tags.get('com.apple.quicktime.model') or tags.get('model'))
    if cam:
        out['cam'] = cam[:60]
    local = tags.get('com.apple.quicktime.creationdate')       # "2026-09-27T22:14:05+0000"（当地时间 + 偏移）
    m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', local or '')
    if m:
        out['taken'] = m.group(1)
    elif tags.get('creation_time'):
        m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', tags['creation_time'])
        if m and not m.group(1).startswith('1970'):
            out['taken_utc'] = m.group(1)                      # worker 拿到国家后再换成当地时间
    return out


def utc_to_local(utc, country):
    t = datetime.fromisoformat(utc)
    off = TZ.get((country or '').lower())
    if off is None:
        return utc
    if country.lower() != 'is' and off > -5 and t >= DST_END:
        off -= 1
    return (t + timedelta(hours=off)).strftime('%Y-%m-%dT%H:%M:%S')


def video_frame(path, t):
    """抽一帧（ffmpeg 默认按旋转元数据转正）。t 和浏览器端取封面的时间点一致：min(1s, 时长/3)"""
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.2f}', '-i', str(path), '-frames:v', '1',
                        '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, timeout=120)
    if not r.stdout:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-frames:v', '1',
                            '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, timeout=120)
    return Image.open(io.BytesIO(r.stdout)).convert('RGB') if r.stdout else None


def video_preview(src, dst):
    """720p H.264 + AAC，faststart —— 所有浏览器都能边下边播（iPhone 的 HEVC .mov 在 Windows Chrome 上放不了）"""
    vf = "scale='if(lt(iw,ih),min(720,iw),-2)':'if(lt(iw,ih),-2,min(720,ih))',format=yuv420p"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(src), '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast',
                        '-crf', '26', '-profile:v', 'high', '-c:a', 'aac', '-b:a', '128k', '-ac', '2',
                        '-movflags', '+faststart', '-map_metadata', '-1', str(dst)], capture_output=True, text=True, timeout=3600)
    if r.returncode:
        raise RuntimeError('ffmpeg: ' + r.stderr[-300:])


def jpeg(im, q):
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=q, optimize=True)
    return b.getvalue()


def thumbs(im):
    """和浏览器端 makeAux 同规格：预览图长边 1600（q82），缩略图短边 360（q75）"""
    W, H = im.size
    s = min(1, 1600 / max(W, H))
    p = im.resize((max(1, round(W * s)), max(1, round(H * s))), Image.LANCZOS) if s < 1 else im
    s2 = min(1, 360 / min(p.size))
    t = p.resize((max(1, round(p.size[0] * s2)), max(1, round(p.size[1] * s2))), Image.LANCZOS) if s2 < 1 else p
    return jpeg(t, 75), jpeg(p, 82), p


def sharpness(gray):
    """拉普拉斯方差（越糊越低）→ 对数映射到 0–1。同一组连拍里分辨糊片最管用的单个信号"""
    v = cv2.Laplacian(gray, cv2.CV_64F).var()
    return float(np.clip((math.log10(v + 1) - 0.8) / 2.4, 0, 1))


def quality(im, faces, vlm_q):
    """综合分 0–1：清晰度 40% · 曝光 10% · 人脸清晰度 20%（没人脸时用整体清晰度）· 模型给的观感 30%。
    只在「几张几乎一样的」之间比较才有意义 —— 所以绝对值不重要，相对顺序要对。"""
    small = im.copy()
    small.thumbnail((1024, 1024))
    g = cv2.cvtColor(np.asarray(small), cv2.COLOR_RGB2GRAY)
    sh = sharpness(g)
    clip = float(((g > 250) | (g < 4)).mean())
    expo = float(np.clip(1 - clip * 3, 0, 1))
    fs = []
    W, H = small.size
    for f in faces:
        x0, y0 = int(f['x'] * W), int(f['y'] * H)
        x1, y1 = int((f['x'] + f['w']) * W), int((f['y'] + f['hh']) * H)
        crop = g[max(0, y0):y1, max(0, x0):x1]
        if crop.size >= 64:
            fs.append(f['score'] * sharpness(cv2.resize(crop, (96, 96))))
    face = float(np.mean(fs)) if fs else sh
    vq = (float(vlm_q) - 1) / 4 if vlm_q else 0.5
    return {'sharp': round(sh, 4), 'score': round(0.4 * sh + 0.1 * expo + 0.2 * face + 0.3 * vq, 4)}
