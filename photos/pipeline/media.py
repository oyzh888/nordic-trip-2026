"""读原件：EXIF / ffprobe 元数据、解码成图、生成缩略图和 720p 视频预览、画质打分。

这里全是 CPU 活（PIL / OpenCV / ffmpeg），不碰模型。输出的字段名和 Album.result() 对得上：
taken（当地墙上时间，无时区，"2026-09-27T22:14:05"）· lat/lon · w/hh（转正后的尺寸）· dur · cam · cid。

能解的格式：JPEG / HEIC / HEIF / AVIF / PNG / WebP / GIF / TIFF（Pillow + pillow-heif），
相机 RAW（DNG / CR2 / CR3 / NEF / ARW / RAF / ORF / RW2…，rawpy = LibRaw），视频交给 ffmpeg。
cid = Live Photo 的配对 ID：照片在 Apple MakerNote 里，视频在 QuickTime 元数据里，两边一样就是同一张 Live Photo。
"""
import struct
import io
import json
import math
import re
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from PIL import Image, ImageOps
import pillow_heif
import exifread
import rawpy
from timezonefinder import TimezoneFinder

pillow_heif.register_heif_opener()
Image.MAX_IMAGE_PIXELS = 400_000_000

# 视频的 creation_time 是 UTC，照片的 EXIF 是当地时间 —— 为了两者排在同一条时间线上，视频要换成当地时间。
# iPhone 的 com.apple.quicktime.creationdate 自带时区，优先用它；没有时按国家估（本次行程 9 月底–10 月中）。
TZ = {'is': 0, 'gb': 1, 'ie': 1, 'pt': 1, 'no': 2, 'se': 2, 'dk': 2, 'de': 2, 'fr': 2, 'nl': 2, 'be': 2,
      'es': 2, 'it': 2, 'ch': 2, 'at': 2, 'mc': 2, 'fi': 3, 'ee': 3, 'us': -7}
DST_END = datetime(2026, 10, 25, 1)          # 欧洲夏令时结束（UTC 时间）；之后除冰岛外都少 1 小时
TZ['cn'] = 8
# 没 GPS 的照片（单反、相机）按行程判断当时在哪个国家：(从这个 UTC 时刻起, 国家)。只写全员同行的那几天 ——
# 10/6 之后大家分头走（有人回北京、有人去尼斯），不知道是谁拍的，就不猜，保留相机自己的时间。
TRIP = [('2026-09-23T19:20', 'cn'), ('2026-09-24T04:45', 'no'), ('2026-09-25T04:15', 'is'),
        ('2026-09-29T20:05', 'no'), ('2026-10-06T15:20', None)]


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


RAW_EXT = {'dng', 'cr2', 'cr3', 'crw', 'nef', 'nrw', 'arw', 'srf', 'sr2', 'raf', 'orf', 'rw2', 'pef', 'srw', 'raw', 'rwl', '3fr', 'iiq', 'x3f', 'erf', 'mef', 'mos', 'kdc', 'dcr'}


def apple_cid(mk):
    """Apple MakerNote（EXIF 0x927C）里的 Live Photo 配对 ID（tag 0x11）。
    格式：'Apple iOS\\0' + 2 字节版本 + 字节序 'MM' + IFD；值的偏移相对 MakerNote 开头"""
    if not isinstance(mk, (bytes, bytearray)) or not mk.startswith(b'Apple iOS') or len(mk) < 16:
        return None
    bo = '>' if mk[12:14] == b'MM' else '<'
    n = struct.unpack(bo + 'H', mk[14:16])[0]
    for i in range(min(n, 200)):
        e = 16 + i * 12
        if e + 12 > len(mk):
            break
        tag, typ, cnt = struct.unpack(bo + 'HHI', mk[e:e + 8])
        if tag == 0x11 and typ == 2:
            off = struct.unpack(bo + 'I', mk[e + 8:e + 12])[0] if cnt > 4 else e + 8
            v = bytes(mk[off:off + cnt]).split(b'\0')[0].decode('ascii', 'ignore').strip()
            return v[:64] or None
    return None


def _set_taken(out, dt, off):
    """EXIF 的 "2026:09:27 22:14:05" + 可选的时区 "+08:00" → taken（相机钟点）+ _utc（换成 UTC，worker 再按拍摄地换回）"""
    m = re.match(r'(\d{4}):(\d\d):(\d\d)[ T](\d\d):(\d\d):(\d\d)', str(dt or ''))
    if not m or m.group(1) == '0000':
        return
    out['taken'] = '{}-{}-{}T{}:{}:{}'.format(*m.groups())
    # 相机自己记的时区（「+08:00」）：相机没改时区时它和拍摄地不一样 → 先换成 UTC，worker 再按拍摄地换回当地时间
    o = re.match(r'([+-])(\d\d):(\d\d)$', str(off or '').strip())
    if o:
        mins = (1 if o.group(1) == '+' else -1) * (int(o.group(2)) * 60 + int(o.group(3)))
        out['_utc'] = (datetime.fromisoformat(out['taken']) - timedelta(minutes=mins)).strftime('%Y-%m-%dT%H:%M:%S')


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
    _set_taken(out, sub.get(0x9003) or sub.get(0x9004) or ex.get(0x0132), sub.get(0x9011) or sub.get(0x9010))
    cid = apple_cid(sub.get(0x927C))
    if cid:
        out['cid'] = cid
    g = ex.get_ifd(0x8825)
    if g.get(2) and g.get(4):
        dms = lambda a: sum(_rat(v) / d for v, d in zip(a, (1, 60, 3600))) if len(a) == 3 else None
        la, lo = dms(g[2]), dms(g[4])
        if la is not None and lo is not None and (la or lo):
            out['lat'] = -la if g.get(1) == 'S' else la
            out['lon'] = -lo if g.get(3) == 'W' else lo
    return out


def cr3_meta(path):
    """佳能 CR3（R5 / R6 / R3…）：EXIF 不在 TIFF 头里，而是分散在 moov 里的 CMT1（IFD0）/ CMT2（EXIF）/ CMT4（GPS）
    三个盒子里，每个盒子本身是一段完整的 TIFF。exifread 读不了，自己拆"""
    with open(path, 'rb') as f:
        head = f.read(4 << 20)
    if head[4:8] != b'ftyp' or b'crx ' not in head[8:24]:
        return None
    box = {}
    for k in (b'CMT1', b'CMT2', b'CMT4'):
        i = head.find(k)
        if i >= 4:
            n = struct.unpack('>I', head[i - 4:i])[0]
            box[k] = head[i + 4:i - 4 + n]
    if b'CMT1' not in box:
        return None
    def load(k):
        e = Image.Exif()
        try:
            e.load(box[k])
        except Exception:        # noqa: BLE001
            return {}
        return dict(e)
    i0, ex, gps = load(b'CMT1'), load(b'CMT2') if b'CMT2' in box else {}, load(b'CMT4') if b'CMT4' in box else {}
    out = {}
    cam = cam_name(i0.get(0x010F), i0.get(0x0110))
    if cam:
        out['cam'] = cam[:60]
    _set_taken(out, ex.get(0x9003) or ex.get(0x9004) or i0.get(0x0132), ex.get(0x9011) or ex.get(0x9010))
    if gps.get(2) and gps.get(4):
        dms = lambda a: sum(_rat(v) / d for v, d in zip(a, (1, 60, 3600))) if len(a) == 3 else None
        la, lo = dms(gps[2]), dms(gps[4])
        if la is not None and lo is not None and (la or lo):
            out['lat'] = -la if gps.get(1) == 'S' else la
            out['lon'] = -lo if gps.get(3) == 'W' else lo
    return out


def raw_meta(path):
    """RAW 的 EXIF：TIFF 系（DNG / CR2 / NEF / ARW / ORF / RW2…）交给 exifread，CR3 自己拆"""
    try:
        m = cr3_meta(path)
        if m is not None:
            return m
    except Exception:            # noqa: BLE001
        pass
    out = {}
    try:
        with open(path, 'rb') as f:
            t = exifread.process_file(f, details=False)
    except Exception:            # noqa: BLE001
        return out
    g = lambda k: str(t[k]) if k in t else None
    cam = cam_name(g('Image Make'), g('Image Model'))
    if cam:
        out['cam'] = cam[:60]
    _set_taken(out, g('EXIF DateTimeOriginal') or g('EXIF DateTimeDigitized') or g('Image DateTime'),
               g('EXIF OffsetTimeOriginal') or g('EXIF OffsetTime'))
    def dms(k):
        v = t.get(k)
        try:
            a = [float(x.num) / float(x.den or 1) for x in v.values]
            return a[0] + a[1] / 60 + a[2] / 3600
        except Exception:        # noqa: BLE001
            return None
    la, lo = dms('GPS GPSLatitude'), dms('GPS GPSLongitude')
    if la is not None and lo is not None and (la or lo):
        out['lat'] = -la if g('GPS GPSLatitudeRef') == 'S' else la
        out['lon'] = -lo if g('GPS GPSLongitudeRef') == 'W' else lo
    return out


def open_raw(path):
    """相机 RAW → RGB。优先用文件里内嵌的全尺寸 JPEG 预览（相机自己渲染的，快、颜色和机背一致）；
    太小或没有才真正解马赛克（half_size：长边一半，够做预览和分析）"""
    with rawpy.imread(str(path)) as r:
        flip = r.sizes.flip
        try:
            th = r.extract_thumb()
            if th.format == rawpy.ThumbFormat.JPEG:
                im = Image.open(io.BytesIO(th.data)); im.load()
                if max(im.size) >= 1600:
                    im = {3: im.rotate(180, expand=True), 5: im.rotate(90, expand=True), 6: im.rotate(-90, expand=True)}.get(flip, im)
                    return im.convert('RGB')
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError, OSError):
            pass
        return Image.fromarray(r.postprocess(half_size=True, use_camera_wb=True, output_bps=8))   # postprocess 自己会按 flip 转正


def open_image(path, name=''):
    """解码 + 按 EXIF 方向转正。返回 (RGB 图, 元数据)。name 用来认 RAW（缓存里的原件没有扩展名）"""
    ext = (name or '').rsplit('.', 1)[-1].lower() if '.' in (name or '') else ''
    if ext in RAW_EXT:
        meta = raw_meta(path)
        im = open_raw(path)
        meta['w'], meta['hh'] = im.size
        return im, meta
    try:
        im = Image.open(path)
    except Exception:            # noqa: BLE001 —— 扩展名没写对的 RAW 也试一下
        im = open_raw(path)
        meta = raw_meta(path)
        meta['w'], meta['hh'] = im.size
        return im, meta
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
    if tags.get('com.apple.quicktime.content.identifier'):
        out['cid'] = tags['com.apple.quicktime.content.identifier'][:64]
    local = tags.get('com.apple.quicktime.creationdate')       # "2026-09-27T22:14:05+0000"（当地时间 + 偏移）
    m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', local or '')
    if m:
        out['taken'] = m.group(1)
    elif tags.get('creation_time'):
        m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', tags['creation_time'])
        if m and not m.group(1).startswith('1970'):
            out['taken_utc'] = m.group(1)                      # worker 拿到国家后再换成当地时间
    return out


# 有 GPS 就按经纬度查真正的时区（离线库，含夏令时）—— 美国、澳大利亚这种一个国家好几个时区的，
# 按国家查表会差几个小时；没 GPS 才退回按国家
CC_TZ = {'is': 'Atlantic/Reykjavik', 'no': 'Europe/Oslo', 'se': 'Europe/Stockholm', 'dk': 'Europe/Copenhagen', 'fi': 'Europe/Helsinki',
         'gb': 'Europe/London', 'ie': 'Europe/Dublin', 'pt': 'Europe/Lisbon', 'es': 'Europe/Madrid', 'fr': 'Europe/Paris', 'mc': 'Europe/Monaco',
         'it': 'Europe/Rome', 'de': 'Europe/Berlin', 'nl': 'Europe/Amsterdam', 'be': 'Europe/Brussels', 'ch': 'Europe/Zurich', 'at': 'Europe/Vienna',
         'ee': 'Europe/Tallinn', 'cn': 'Asia/Shanghai', 'hk': 'Asia/Hong_Kong', 'jp': 'Asia/Tokyo'}
_TF = None


def tz_at(lat, lon):
    global _TF
    if lat is None or lon is None:
        return None
    _TF = _TF or TimezoneFinder()
    try:
        return _TF.timezone_at(lng=float(lon), lat=float(lat))
    except Exception:            # noqa: BLE001
        return None


def utc_to_tz(utc, tz):
    t = datetime.fromisoformat(utc).replace(tzinfo=timezone.utc)
    return t.astimezone(ZoneInfo(tz)).strftime('%Y-%m-%dT%H:%M:%S')


def trip_country(utc):
    """按行程表猜某个 UTC 时刻人在哪个国家；行程之外返回 None"""
    cc = None
    for t, c in TRIP:
        if utc >= t:
            cc = c
    return cc


def utc_to_local(utc, country):
    """UTC → 该国当地墙上时间；不认识的国家返回 None（调用方自己决定退路）"""
    if (country or '').lower() in CC_TZ:
        return utc_to_tz(utc, CC_TZ[country.lower()])
    t = datetime.fromisoformat(utc)
    off = TZ.get((country or '').lower())
    if off is None:
        return None
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
