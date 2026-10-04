"""相册的 GPU 分析端 —— 跑在任意一台有 GPU 的机器上，主动连到 Worker（不需要开端口、不怕 pod 漂移）。

    python pipeline/worker.py                         # 默认连 https://nordic.airacle.com，常驻
    python pipeline/worker.py --base http://localhost:8787 --once     # 本地 dev：处理完当前积压就退出

它做四件事：
  1. 轮询 /api/pipe/pending：下载原件 → EXIF/ffprobe → 补缩略图、视频转 720p → 三个模型 → POST /api/pipe/result
  2. 一条 WebSocket 常连着：服务端遇到没见过的搜索词就推过来，这边 ~20 ms 算出向量送回去（搜索最多等 2.5 秒）
  3. 有新结果、或有人在人物页认领了脸 → 全量重新聚类 → POST /api/pipe/clusters
  4. AI 改图（aiedit.py）：有人点了「✨ AI 改图」→ 下载原图 → 经模型网关调 Nano Banana / GPT Image
     → 改好的图作为一张新照片传回去（原图不动）。这部分不用本机 GPU，和上面三件互不阻塞

状态全在服务端（人脸向量、图像向量都存在 Album 里），这边只有可再生的缓存 —— pod 重建后直接重跑就行。
令牌：环境变量 PIPE_TOKEN，否则读 ~/.secrets/nordic-photos.env（本地 dev 读 photos/.dev.vars）。
"""
import argparse
import base64
import io
import json
import os
import sys
import shutil
import threading
import time
import traceback
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clock  # noqa: E402
import video as VID  # noqa: E402
import cluster  # noqa: E402
import media as M  # noqa: E402
from models import face_vec, q8  # noqa: E402  （不加载模型，只是两个小函数）

UP_QUIET = 30                 # 秒：最近这么久内有人上传，就先不做重的后处理（见 run）
MAX_DEFER = 15 * 60           # 一直有人在传，最多推迟这么久
AVER = 1                     # 分析版本：换模型/改提示词后 +1，服务端 aver < 这个的都会被重新分析
BATCH = 8
UA = 'nordic-photos-pipeline/1.0 (github.com/oyzh888/nordic-trip-2026)'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def load_env(base):
    def read(p):
        out = {}
        if p.exists():
            for line in p.read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    k, v = line.split('=', 1)
                    out[k.strip()] = v.strip().strip('"\'')
        return out
    local = 'localhost' in base or '127.0.0.1' in base
    f = read(HERE.parent / '.dev.vars') if local else read(Path.home() / '.secrets/nordic-photos.env')
    tok = os.environ.get('PIPE_TOKEN') or f.get('PIPE_TOKEN')
    if not tok:
        sys.exit('缺 PIPE_TOKEN（环境变量，或 ~/.secrets/nordic-photos.env / photos/.dev.vars）')
    # 模型网关的源码目录（AI 改图用）；本地 dev 的 .dev.vars 里一般没有，就退回 secrets 文件
    gw = os.environ.get('GATEWAY_SRCS') or f.get('GATEWAY_SRCS') or read(Path.home() / '.secrets/nordic-photos.env').get('GATEWAY_SRCS')
    return tok, gw


class Api:
    def __init__(self, base, token):
        self.base = base.rstrip('/') + '/photos'
        self.s = requests.Session()
        self.s.headers.update({'authorization': 'Bearer ' + token, 'user-agent': UA})
        self.token = token

    def req(self, method, path, **kw):
        kw.setdefault('timeout', 120)
        for i in range(5):
            try:
                r = self.s.request(method, self.base + path, **kw)
                if r.status_code < 500:
                    return r
            except requests.RequestException as e:
                r = e
            time.sleep(2 ** i)
        raise RuntimeError(f'{method} {path}: {r}')

    def get(self, p, **kw):
        r = self.req('GET', p, **kw); r.raise_for_status(); return r.json()

    def post(self, p, js):
        r = self.req('POST', p, json=js); r.raise_for_status(); return r.json()

    def aux(self, h, k, data, dims=None):
        q = f'/api/upload/aux?h={h}&k={k}' + ''.join(f'&{a}={b}' for a, b in (dims or {}).items() if b is not None)
        r = self.req('PUT', q, data=data, headers={'content-type': 'application/octet-stream'}, timeout=600)
        r.raise_for_status()

    def put(self, path, data, ctype):
        r = self.req('PUT', path, data=data, headers={'content-type': ctype}, timeout=600)
        r.raise_for_status()
        return r.json()

    def download(self, h, dst):
        with self.s.get(f'{self.base}/f/{h}/o', stream=True, timeout=600) as r:
            r.raise_for_status()
            tmp = dst.with_suffix('.part')
            with open(tmp, 'wb') as f:
                for c in r.iter_content(1 << 20):
                    f.write(c)
            tmp.rename(dst)


class Geo:
    """GPS → 中文地名。两步，按 ~100 米取整缓存到磁盘：
    1. Overpass 找附近 500 米内有名字的景点（瀑布 / 冰川 / 海滩 / 名胜 / 教堂）—— 冰岛很多照片拍在荒郊野外，
       Nominatim 只会给出「某条公路 · 某个县」，而大家想看到的是「塞里雅兰瀑布」
    2. Nominatim 反查所在的村镇城市 + 国家
    OSM 里的中文名很多是繁体（雷克雅維克），统一转成简体。网络问题不缓存，下次再试。"""
    NATURAL = 'waterfall|glacier|beach|volcano|peak|bay|cape|hot_spring|geyser|cliff'

    def __init__(self, path):
        self.path = path
        self.c = json.loads(path.read_text()) if path.exists() else {}
        self.last = 0
        try:
            import opencc
            self.t2s = opencc.OpenCC('t2s').convert
        except ImportError:
            self.t2s = lambda s: s

    def _get(self, url, **kw):
        time.sleep(max(0, 1.1 - (time.time() - self.last)))    # 两个服务都要求 ≤ 1 次/秒
        self.last = time.time()
        r = requests.request(kw.pop('method', 'GET'), url, timeout=30, headers={'user-agent': UA}, **kw)
        r.raise_for_status()
        return r.json()

    def poi(self, lat, lon):
        q = f"""[out:json][timeout:20];(
          nwr(around:500,{lat},{lon})[natural~"^({self.NATURAL})$"][name];
          nwr(around:500,{lat},{lon})[waterway=waterfall][name];
          nwr(around:300,{lat},{lon})[tourism~"^(attraction|viewpoint)$"][name];
          nwr(around:300,{lat},{lon})[historic~"^(castle|monument|ruins|church|fort|palace)$"][name];
          nwr(around:200,{lat},{lon})[building~"^(church|cathedral)$"][name];
          nwr(around:800,{lat},{lon})[water~"^(lagoon|lake)$"][name];
        );out tags center 20;"""
        best = None
        for e in self._get('https://overpass-api.de/api/interpreter', method='POST', data={'data': q}).get('elements', []):
            tg = e.get('tags') or {}
            zh = tg.get('name:zh-Hans') or tg.get('name:zh-CN') or tg.get('name:zh')
            c = e.get('center') or e
            d = cluster.km((lat, lon), (c.get('lat', lat), c.get('lon', lon)))
            kind = 0 if (tg.get('natural') or tg.get('waterway')) else 1 if tg.get('historic') or tg.get('building') else 2
            # 有中文名的优先（没有中文名的多半是小地方），然后是自然景观 > 古迹教堂 > 其他景点，最后看远近
            key = (zh is None, kind, d)
            if best is None or key < best[0]:
                best = (key, zh or tg.get('name'))
        return self.t2s(best[1]) if best else None

    def __call__(self, lat, lon):
        if lat is None or lon is None:
            return None, None
        k = f'{lat:.3f},{lon:.3f}'
        if k not in self.c:
            try:
                d = self._get('https://nominatim.openstreetmap.org/reverse', params={
                    'format': 'jsonv2', 'lat': lat, 'lon': lon, 'zoom': 16, 'accept-language': 'zh-Hans,zh-CN,zh,en'})
                poi = False                                # Overpass 经常 429 / 504（公共服务限流）：重试两次，还不行就这次先只用城镇名、不缓存
                for wait in (0, 4, 12):
                    time.sleep(wait)
                    try:
                        poi = self.poi(lat, lon)
                        break
                    except (requests.RequestException, ValueError):
                        pass
            except (requests.RequestException, ValueError):
                return None, None
            a = d.get('address') or {}
            town = next((a[k2] for k2 in ('village', 'town', 'city', 'hamlet', 'suburb', 'municipality', 'county', 'state') if a.get(k2)), None)
            country = (a.get('country') or '').split(' / ')[0].strip() or None
            if poi and town and not any('\u4e00' <= ch <= '\u9fff' for ch in town):
                town = None                                # 有景点名时，没有中文名的乡镇（Rangárþing eystra）只是噪音
            parts = [self.t2s(x) for x in (poi or None, town, country) if x]
            place = ' · '.join(dict.fromkeys(parts)) or None
            if poi is False:
                return place, a.get('country_code')
            self.c[k] = [place, a.get('country_code')]
            self.path.write_text(json.dumps(self.c, ensure_ascii=False))
        return tuple(self.c[k])


class Worker:
    def __init__(self, args):
        self.args = args
        tok, gw = load_env(args.base)
        self.api = Api(args.base, tok)
        self.cache = Path(args.cache)
        (self.cache / 'o').mkdir(parents=True, exist_ok=True)
        self.geo = Geo(self.cache / 'geo2.json')        # geo.json 是旧格式（繁体 / 没有景点名），不再读
        self.titles_p = self.cache / 'titles.json'
        self.titles = json.loads(self.titles_p.read_text()) if self.titles_p.exists() else {}
        self.wake = threading.Event()
        self.wake_transcode = threading.Event()
        self.dirty = True                  # 启动时先聚类一次（上一个 worker 可能没跑完）
        self.gpu = threading.Lock()        # WebSocket 线程和主循环共用模型
        log('加载模型 …')
        t = time.time()
        from models import Models
        self.m = Models(vlm=not args.no_vlm)
        log(f'模型就绪 {time.time() - t:.0f}s')
        self.conf_sig = None
        self.conf_srv = None
        self.editor, self.edit_keys = None, []
        if not args.no_edit:
            import aiedit
            self.editor = aiedit.Editor(gw)
            self.edit_keys = self.editor.available()
            log(f'AI 改图：{"可用 " + "/".join(self.edit_keys) if self.edit_keys else "不可用 —— " + str(self.editor.why)}')
        self.edit_wake = threading.Event()
        self.edit_busy = set()
        self.edit_pool = ThreadPoolExecutor(3, thread_name_prefix='edit')

    # ---------------- WebSocket：搜索词向量 ----------------
    def embed_qs(self, qs):
        with self.gpu:
            V = self.m.embed_texts(qs)
        return [{'q': q, 'vec': base64.b64encode(v.astype('<f4').tobytes()).decode()} for q, v in zip(qs, V)]

    def ws_loop(self):
        from websockets.sync.client import connect
        url = self.api.base.replace('http', 'ws', 1) + '/api/pipe/ws'
        while not self.stop:
            try:
                with connect(url, additional_headers={'authorization': 'Bearer ' + self.api.token, 'user-agent': UA},
                             open_timeout=20, ping_interval=None) as ws:
                    log('WebSocket 已连上 —— 页面上显示「AI 在线」')
                    ws.send(json.dumps({'t': 'hello', 'edit': self.edit_keys}))
                    last = time.time()
                    while not self.stop:
                        try:
                            msg = ws.recv(timeout=5)
                        except TimeoutError:
                            msg = None
                        if time.time() - last > 25:          # Cloudflare 会掐掉 100 秒没动静的连接
                            ws.send('ping'); last = time.time()
                        if not msg or msg == 'pong':
                            continue
                        m = json.loads(msg)
                        if m.get('t') == 'embed':
                            t = time.time()
                            ws.send(json.dumps({'t': 'vecs', 'items': self.embed_qs(m['q'])})); last = time.time()
                            log(f'搜索词向量 {m["q"]} {1000 * (time.time() - t):.0f} ms')
                        elif m.get('t') == 'edit':
                            self.edit_wake.set()
                        elif m.get('t') in ('new', 'recluster'):
                            if m['t'] == 'recluster':
                                self.dirty = True
                            self.wake.set()
                            if m['t'] == 'new':
                                self.wake_transcode.set()       # 新传的视频不用等 60 秒轮询
            except Exception as e:           # noqa: BLE001 —— 断了就重连，不影响主循环
                if not self.stop:
                    log('WebSocket 断开，5 秒后重连:', repr(e)[:160])
                    time.sleep(5)

    # ---------------- AI 改图 ----------------
    # ---------------- 视频：转成 H.264 新版 + 调色（见 video.py）----------------
    def transcode_loop(self):
        """后台一个线程、一次一个：不挡照片分析。原片先照常上传、照常分析，这里再补一份「谁都能放、颜色正常」的新版"""
        while not self.stop:
            try:
                todo = self.api.get('/api/pipe/transcode')
            except Exception as e:   # noqa: BLE001
                log('取转码任务失败:', repr(e)[:160]); todo = []
            for it in todo:
                if self.stop:
                    return
                self.transcode_one(it)
            self.wake_transcode.wait(60 if not todo else 1)
            self.wake_transcode.clear()

    def canon_name(self, it):
        """文件名像不像这个人传过的佳能照片（同一前缀，比如 _I6A / _63A），或者佳能默认的 MVI_"""
        n = (it.get('name') or '').upper()
        if n.startswith('MVI_'):
            return True
        try:
            pre = {(m.get('name') or '')[:4].upper() for m in self.api.get('/api/pipe/media')
                   if (m.get('cam') or '').lower().startswith('canon') and m.get('up') == it.get('up')}
        except Exception:        # noqa: BLE001
            return False
        return bool(n[:4]) and n[:4] in pre and n[:4] not in ('IMG_', 'DSC_', 'DSC0')

    def transcode_one(self, it):
        h, t0 = it['h'], time.time()
        src = self.cache / 'o' / f'tc-{h}'
        out = self.cache / f'tc-{h}.mp4'
        try:
            self.api.download(h, src)
            info, vs, aus = VID.probe(src)
            plan, why = VID.plan_for(src, vs, info, cam=it.get('cam'), canon_name=self.canon_name(it))
            if plan == 'none':
                self.api.post('/api/pipe/gplan', {'h': h, 'plan': 'none'})
                log(f'🎬 {it["name"]}: 不用转（{why}）')
                return
            log(f'🎬 {it["name"]}: {VID.LABEL[plan]} · {why} · 开始转（{it["size"] / 1e6:.0f} MB）')
            sec = VID.convert(src, out, plan, vs, aus)
            size, crc = out.stat().st_size, 0
            with open(out, 'rb') as f:
                while b := f.read(8 << 20):
                    crc = zlib.crc32(b, crc)
            up = self.api.post('/api/pipe/gmp/init', {'h': h})
            parts = []
            with open(out, 'rb') as f:
                n = 0
                while b := f.read(8 << 20):
                    n += 1
                    r = self.api.req('PUT', f'/api/pipe/gmp/part?h={h}&id={up["id"]}&n={n}', data=b,
                                     headers={'content-type': 'application/octet-stream'}, timeout=600)
                    r.raise_for_status()
                    parts.append({'n': n, 'etag': r.json()['etag']})
            self.api.post('/api/pipe/gmp/complete', {'h': h, 'id': up['id'], 'parts': parts, 'plan': plan, 'size': size, 'crc': crc & 0xFFFFFFFF})
            if plan != 'transcode':
                # 调过色的：时间线上的缩略图和 720p 预览也换成新版的颜色（原来是从灰蒙蒙的 Log 原片截的）
                _, vo, _ = VID.probe(out)
                im = M.video_frame(out, min(1.0, float(vo.get('duration') or 3) / 3))
                if im is not None:
                    tb, pv, _ = M.thumbs(im)
                    self.api.aux(h, 't', tb); self.api.aux(h, 'p', pv)
                prev = self.cache / f'tc-{h}-720.mp4'
                M.video_preview(out, prev)
                self.api.aux(h, 'v', prev.read_bytes()); prev.unlink(missing_ok=True)
            log(f'🎬 {it["name"]}: 好了 · {VID.LABEL[plan]} · {it["size"] / 1e6:.0f} MB → {size / 1e6:.0f} MB · 转码 {sec:.0f}s · 共 {time.time() - t0:.0f}s')
        except Exception as e:       # noqa: BLE001 —— 记下失败原因，不再自动重试（不然一个坏文件每分钟转一遍）
            log(f'🎬 {it.get("name")}: 转码失败\n' + traceback.format_exc(limit=3))
            try: self.api.post('/api/pipe/gplan', {'h': h, 'plan': f'fail:{str(e)[:150]}'})
            except Exception: pass   # noqa: BLE001
        finally:
            src.unlink(missing_ok=True); out.unlink(missing_ok=True)

    def edit_loop(self):
        """服务端推 {t:'edit'} 就来取；WS 断着的时候每 20 秒兜底查一次"""
        while not self.stop:
            try:
                for i in self.api.get('/api/pipe/edits'):
                    if i not in self.edit_busy:
                        self.edit_busy.add(i)
                        self.edit_pool.submit(self.edit_one, i)
            except Exception as e:   # noqa: BLE001
                log('取改图任务失败:', repr(e)[:160])
            self.edit_wake.wait(20)
            self.edit_wake.clear()

    def edit_one(self, eid):
        import aiedit
        t0 = time.time()
        try:
            job = self.api.post('/api/pipe/edit/start', {'id': eid})
            if job.get('skip'):
                return
            if job['model'] not in self.edit_keys:
                raise aiedit.EditError('这个模型现在用不了')
            path = self.cache / 'o' / f'edit-{eid}-{job["h"]}'
            self.api.download(job['h'], path)
            try:
                im, _ = M.open_image(path, job.get('name', ''))
            finally:
                path.unlink(missing_ok=True)
            out, mid = self.editor.edit(im, job['prompt'], job['model'])
            data = aiedit.encode(out, job.get('taken'), job.get('lat'), job.get('lon'), mid)
            r = self.api.put(f'/api/pipe/edit/out?id={eid}&w={out.width}&hh={out.height}&mid={mid}', data, 'image/jpeg')
            if r.get('error'):
                raise RuntimeError(r['error'])
            tb, pv, _ = M.thumbs(out)                   # 缩略图马上补上，页面不用等下一轮分析
            self.api.aux(r['h'], 't', tb, {'w': out.width, 'hh': out.height})
            self.api.aux(r['h'], 'p', pv)
            log(f'✨ 改图 #{eid} {mid} {time.time() - t0:.1f}s 「{job["prompt"][:30]}」→ {r["name"]}')
            self.wake.set()                             # 新照片进了分析队列
        except aiedit.EditError as e:
            log(f'✨ 改图 #{eid} 被拒 {time.time() - t0:.1f}s: {e}')
            self.api.post('/api/pipe/edit/fail', {'id': eid, 'err': str(e)})
        except Exception as e:       # noqa: BLE001
            log(f'✨ 改图 #{eid} 失败:\n' + traceback.format_exc(limit=4))
            self.api.post('/api/pipe/edit/fail', {'id': eid, 'err': f'出错了：{str(e)[:120]}'})
        finally:
            self.edit_busy.discard(eid)

    # ---------------- 单个文件 ----------------
    def prepare(self, it):
        """CPU 部分：下载、元数据、解码、补缩略图/视频预览。返回 (分析用的 RGB 图 或 None, 要回写的字段)"""
        h = it['h']
        path = self.cache / 'o' / h
        if not path.exists():
            self.api.download(h, path)
        res, im = {'h': h}, None
        if not it.get('crc'):                           # 一步上传接口为了省 CPU 不算 CRC（打包下载要用），这里补上
            crc = 0
            with open(path, 'rb') as f:
                while b := f.read(8 << 20):
                    crc = zlib.crc32(b, crc)
            res['crc'] = crc & 0xFFFFFFFF
        if it['kind'] == 'video':
            vm = M.video_meta(path)
            res.update({k: vm[k] for k in ('w', 'hh', 'dur', 'lat', 'lon', 'cam', 'taken', 'cid') if vm.get(k) is not None})
            res['_utc'] = vm.get('taken_utc')
            if vm.get('probe_ok'):
                im = M.video_frame(path, min(1.0, (vm.get('dur') or 0) / 3))
                if not it['flags'] & 4:
                    out = self.cache / f'{h}.mp4'
                    M.video_preview(path, out)
                    self.api.aux(h, 'v', out.read_bytes())
                    res['_v'] = out.stat().st_size
                    out.unlink()
        else:
            try:
                im, meta = M.open_image(path, it['name'])
                res.update({k: v for k, v in meta.items() if v is not None})
            except Exception as e:   # noqa: BLE001 —— RAW 等解不了的格式：照样入库，只是没有 AI 标签
                log(f'  {it["name"]} 解码失败: {e!r:.120}')
        if im is not None and (not it['flags'] & 1 or not it['flags'] & 2):
            t, p, _ = M.thumbs(im)
            dims = {'w': res.get('w'), 'hh': res.get('hh'), 'dur': res.get('dur')}
            if not it['flags'] & 1:
                self.api.aux(h, 't', t, dims)
            if not it['flags'] & 2:
                self.api.aux(h, 'p', p)
            res['_thumb'] = True
        if not self.args.keep:
            path.unlink(missing_ok=True)
        return im, res

    @staticmethod
    def local_time(utc, cc, res):
        """时间线按「拍摄地当时的钟点」排：有 UTC（相机记了时区 / 视频）就换成拍摄地时间。
        拍摄地按 GPS 经纬度查时区；没 GPS 按行程表猜国家；都不知道就保留相机/手机自己的钟点，再不行才存 UTC"""
        tz = M.tz_at(res.get('lat'), res.get('lon'))
        if tz:
            return M.utc_to_tz(utc, tz)
        if cc is None and res.get('lat') is None:
            cc = M.trip_country(utc)
        return M.utc_to_local(utc, cc) or res.get('taken') or utc

    @staticmethod
    def clock_fields(meta, kind):
        """存下相机表盘原始钟点 / 机身序列号 / 时间从哪来 —— 时钟对齐（clock.py）每次都从原始钟点重算，结果可重复"""
        out = {'ctime': meta.get('_raw') or '', 'cser': meta.get('_ser')}
        out['tzsrc'] = 'video' if kind == 'video' else 'gps' if meta.get('lat') is not None else meta.get('_tzsrc') or 'none'
        return {k: v for k, v in out.items() if v is not None}

    def backfill_clock(self):
        """已经分析过、但还没记原始钟点的照片：只读原件开头的 EXIF 补上（一张一次，补过的 ctime 不再是 NULL）"""
        # 只补已经分析过的：result 接口会顺手把 aver 写成当前版本，没分析过的照片要留给正常流程（它自己会记原始钟点）
        todo = [m for m in self.api.get('/api/pipe/media') if m.get('ctime') is None and not m.get('src') and (m.get('aver') or 0) >= AVER]
        if not todo:
            return 0
        log(f'补记 {len(todo)} 个文件的相机原始钟点 / 机身序列号（只读 EXIF，不重跑模型）')

        def one(m):
            out = {'ctime': '', 'tzsrc': 'video' if m['kind'] == 'video' else 'gps' if m.get('lat') is not None else 'none'}
            try:
                return read(m, out)
            except Exception as e:   # noqa: BLE001
                log(f'  {m["h"][:10]} 补原始钟点失败: {e!r:.80}'); return {'h': m['h'], **out, 'aver': AVER}

        def read(m, out):
            if m['kind'] == 'image':
                raw = (m.get('name') or '').rsplit('.', 1)[-1].lower() in M.RAW_EXT
                try:
                    r = self.api.req('GET', f'/f/{m["h"]}/o', headers={'range': f'bytes=0-{(4 << 20 if raw else 256 << 10) - 1}'}, timeout=120)
                    if raw:
                        p = self.cache / f'hdr-{m["h"]}'
                        p.write_bytes(r.content)
                        try: meta = M.raw_meta(p)
                        finally: p.unlink(missing_ok=True)
                    else:
                        meta = M.image_meta(Image.open(io.BytesIO(r.content)))
                    out = self.clock_fields({**meta, 'lat': m.get('lat')}, 'image')
                except Exception as e:   # noqa: BLE001 —— 读不了就记成空，免得每次启动都重试
                    log(f'  {m["h"][:10]} 读不了 EXIF: {e!r:.80}')
            return {'h': m['h'], **out, 'aver': AVER}
        with ThreadPoolExecutor(8) as ex:
            rows = list(ex.map(one, todo))
        self.post_results(rows)                         # 一次写回，不是一千个请求
        return len(todo)

    def align_clocks(self, media, E):
        """相机时钟对齐（见 clock.py）：没时区标签、没 GPS 的相机照片，按同场景的手机照片把时间对齐过来。
        只改变化 ≥ 5 分钟的；返回改过的 h → 新时间（聚类要用新时间）"""
        trip = lambda utc: M.CC_TZ.get(M.trip_country(utc) or '')
        changes, report = clock.align(media, E, M.tz_at, M.utc_to_tz, trip)
        for line in report:
            log('  时钟对齐 ' + line)
        self.post_results([{'h': h, 'taken': taken, 'tzsrc': how, 'aver': AVER} for h, taken, how in changes])
        return {h: t for h, t, _ in changes}

    def retime(self):
        """一次性：把已经分析过的照片按上面的规则重算拍摄时间（只读原件开头的 EXIF，不重跑模型）"""
        n = 0
        for m in self.api.get('/api/pipe/media'):
            if m['kind'] != 'image' or m.get('src'):            # 视频 / AI 改图出来的新图不动
                continue
            r = self.api.req('GET', f'/f/{m["h"]}/o', headers={'range': 'bytes=0-1048575'}, timeout=120)
            try:
                meta = M.image_meta(Image.open(io.BytesIO(r.content)))
            except Exception as e:   # noqa: BLE001
                log(f'  {m["h"][:10]} 读不了 EXIF: {e!r:.80}')
                continue
            if not meta.get('_utc'):
                continue
            _, cc = self.geo(m.get('lat'), m.get('lon'))
            t = self.local_time(meta['_utc'], cc, {'lat': m.get('lat'), 'lon': m.get('lon'), 'taken': meta.get('taken')})
            if t != m['taken']:
                self.api.post('/api/pipe/result', {'h': m['h'], 'taken': t, 'aver': AVER})
                log(f'  {m["h"][:10]} {m.get("cam")}  {m["taken"]} → {t}')
                n += 1
        log(f'重算拍摄时间：改了 {n} 张')
        return n

    def process(self, items):
        prepped = []
        for it in items:
            t = time.time()
            try:
                im, res = self.prepare(it)
                prepped.append((it, im, res))
                log(f'  {it["name"]}: 预处理 {time.time() - t:.1f}s' + (' · 补了缩略图' if res.get('_thumb') else '') +
                    (f' · 视频预览 {res["_v"] / 1e6:.1f} MB' if res.get('_v') else ''))
            except Exception:        # noqa: BLE001 —— 一张坏文件不能卡住整条队列
                log(f'  {it["name"]} 失败:\n' + traceback.format_exc(limit=3))
                self.api.post('/api/pipe/result', {'h': it['h'], 'aver': AVER})
        # Live Photo 的那 3 秒视频（带 cid 的视频）不跑模型：描述、人脸、向量都算在配对的那张照片上
        ok = [(it, im, res) for it, im, res in prepped if im is not None and not (it['kind'] == 'video' and res.get('cid'))]
        t = time.time()
        if ok:
            ims = [im for _, im, _ in ok]
            with self.gpu:
                E = self.m.embed_images(ims)
                D = self.m.describe(ims) if self.m.vlm else [None] * len(ims)
                F = [self.m.faces(im) for im in ims]
            log(f'  模型 {len(ims)} 张 {time.time() - t:.1f}s')
            for (it, im, res), e, d, fs in zip(ok, E, D, F):
                res['emb'], res['emb_scale'] = q8(e)
                if d:
                    res['caption'], res['tags'] = d['caption'], d['tags']
                res['faces'] = [{k: v for k, v in f.items() if not k.startswith('_')} for f in fs]
                res.update(M.quality(im, fs, d and d['quality']))
        for it, im, res in prepped:
            place, cc = self.geo(res.get('lat'), res.get('lon'))
            if place:
                res['place'] = place
            utc = res.pop('_utc', None)
            if utc:
                res['taken'] = self.local_time(utc, cc, res)
            res.update(self.clock_fields(res, it['kind']))
            for k in [k for k in res if k.startswith('_')]:
                res.pop(k)
            res['aver'] = AVER
            r = self.api.post('/api/pipe/result', {k: v for k, v in res.items() if v is not None})
            if r.get('ok') and res.get('faces') and im is not None:
                try: self.api.aux(it['h'], 'f', M.face_sprite(im, res['faces']))
                except Exception as e: log(f'  人脸小图条失败 {it["name"]}: {e}')  # noqa: BLE001 —— 不影响分析结果
            tg = res.get('tags') or {}
            log(f'  ✓ {it["name"]}  {res.get("taken", "")}  {place or ""}  人脸 {len(res.get("faces", []))}  '
                f'分 {res.get("score", "-")}  {"/".join(tg.get("special") or [])}  「{res.get("caption", "")[:30]}」'
                + ('' if r.get('ok') else f'  !! {r}'))
        return len(prepped)

    # ---------------- 聚类 ----------------
    def titler(self, caps, place, when, key):
        key = f'{key}|{place or ""}'                   # 地名变了（比如换了地名来源）标题也要重起
        if key in self.titles:
            return tuple(self.titles[key])
        if not self.m.vlm:
            return None, None
        with self.gpu:
            t, memo = self.m.title(caps, place, when)
        t = self.geo.t2s(t) if t else t                # 模型照抄地名时会带进繁体
        self.titles[key] = t = (t, memo)
        self.titles_p.write_text(json.dumps(self.titles, ensure_ascii=False))
        return t

    # ---------------- 增量读：图像向量 / 人脸特征在本机留一份，每次只拉新增的 ----------------
    def load_embs(self):
        """h → 单位化的图像向量。全量一次 8 MB、占着数据库近 1 秒；增量只拉 rowid 变大的（新写的 / 重写的）"""
        if not hasattr(self, 'E'):
            self.E, self.emb_max = {}, 0
        while True:
            r = self.api.get(f'/api/pipe/embs?since={self.emb_max}')
            for x in r['rows']:
                v = np.frombuffer(base64.b64decode(x['vec']), dtype=np.int8).astype(np.float32) * x['scale']
                self.E[x['h']] = v / (np.linalg.norm(v) or 1)
            self.emb_max = r['max']
            if not r.get('more'):
                return self.E

    def load_faces(self):
        """全部人脸：位置 / 归属每次全量（小），特征向量只拉 id 变大的（id 只增不改）"""
        if not hasattr(self, 'FE'):
            self.FE, self.fe_max = {}, 0
        light = self.api.get('/api/pipe/faces?light=1')
        for x in self.api.get(f'/api/pipe/faceemb?since={self.fe_max}'):
            self.FE[x['id']] = x['emb']
            self.fe_max = max(self.fe_max, x['id'])
        live = {f['id'] for f in light}
        for k in [k for k in self.FE if k not in live]:   # 删掉的脸（重新分析 / 删照片）别一直留在内存里
            del self.FE[k]
        return [{**f, 'emb': self.FE.get(f['id'])} for f in light if self.FE.get(f['id'])]

    def post_results(self, items):
        """成百上千条写回：50 条一个请求（服务端每批只刷新一次缓存）"""
        for i in range(0, len(items), 50):
            self.api.post('/api/pipe/results', {'items': items[i:i + 50]})

    def recluster(self):
        t = time.time()
        faces = self.load_faces()
        self.backfill_clock()                           # 先补原始钟点，下面取的列表才带得上
        media = self.api.get('/api/pipe/media')
        for m in media:
            m['tags'] = json.loads(m['tags']) if m.get('tags') else {}
        E = self.load_embs()
        moved = self.align_clocks(media, E)
        for m in media:                                 # 时刻 / 连拍按对齐后的时间切
            if m['h'] in moved:
                m['taken'] = moved[m['h']]
        def unit(s):
            v = face_vec(s)
            return v / (np.linalg.norm(v) or 1)
        fc, auto = cluster.faces(faces, unit)
        body = {
            'faces': {str(k): v for k, v in fc.items()}, 'auto': {str(k): v for k, v in auto.items()},
            'bursts': cluster.bursts(media, E), 'scenes': cluster.scenes(media, E),
            'moments': cluster.moments(media, self.titler),
            'siglip': {'a': self.m.siglip_ab[0], 'b': self.m.siglip_ab[1]},
            'sem_floor': self.args.sem_floor, 'sem_win': self.args.sem_win,
        }
        self.api.post('/api/pipe/clusters', body)
        self.conf_sig = self.confirmed_sig(faces)
        nb = len({v[0] for v in body['bursts'].values()})
        log(f'聚类 {time.time() - t:.1f}s · {len(media)} 个文件 · 人脸 {len(faces)}（{len({v for v in fc.values() if v is not None})} 簇，'
            f'自动归人 {len(auto)}）· 相似组 {nb} · 场景 {len(body["scenes"]["labels"])} · 时刻 {len(body["moments"]["labels"])}')

    @staticmethod
    def confirmed_sig(faces):
        return hash(tuple(sorted((f['id'], f['person']) for f in faces if f['confirmed'])))

    # ---------------- 磁盘用量 ----------------
    def disk_loop(self):
        """相册自己跑在本机时（--store 指向它的存储目录）：每分钟量一次真实占用和整块盘的剩余空间，报给服务端，
        服务端据此拒绝新上传（上限 MAX_BYTES / 最少剩余 MIN_FREE_BYTES，见 album.js quota）"""
        root = self.args.store
        while not self.stop:
            try:
                used, seen = 0, set()
                for d, _, fs in os.walk(root):
                    for f in fs:
                        try: st = os.lstat(os.path.join(d, f))
                        except OSError: continue
                        if (st.st_dev, st.st_ino) in seen: continue     # 硬链接（换存储时导出的文件）只算一次
                        seen.add((st.st_dev, st.st_ino)); used += st.st_blocks * 512
                q = self.api.post('/api/pipe/disk', {'used': used, 'free': shutil.disk_usage(root).free})
                if q.get('cap') and q['used'] > 0.9 * q['cap']:
                    log(f'⚠️ 相册存储 {q["used"] / 1e9:.1f} GB，上限 {q["cap"] / 1e9:.0f} GB')
            except Exception as e:  # noqa: BLE001 —— 量不到就下一分钟再量，别拖垮主循环
                log(f'磁盘用量上报失败：{e}')
            time.sleep(60)

    # ---------------- 人脸小图条补生成 ----------------
    def backfill_sprites(self):
        """有人脸、还没有小图条（flags 第 8 位）的照片：从预览图（没有就用原图）裁出来补上。之前分析过的老照片走这里"""
        items = [i for i in self.api.get('/api/list')['items'] if i.get('nf') and not i['f'] & 8]
        if not items: return 0
        by = {}
        for f in self.api.get('/api/pipe/faces?light=1'): by.setdefault(f['h'], []).append(f)
        n = 0
        for it in items:
            fs = sorted(by.get(it['h'], []), key=lambda f: f['id'])
            if not fs: continue
            try:
                r = self.api.req('GET', f"/f/{it['h']}/{'p' if it['f'] & 2 else 'o'}", timeout=300); r.raise_for_status()
                if it['f'] & 2:
                    im = Image.open(io.BytesIO(r.content)).convert('RGB')     # 预览图生成时已经按 EXIF 转正，和人脸坐标同一个方向
                else:                                                         # 原图（HEIC / RAW…）要走同一套解码 + 转正
                    tmp = Path(self.args.cache) / f'sprite-{it["h"]}'
                    tmp.write_bytes(r.content)
                    try: im = M.open_image(str(tmp), it['n'])[0]
                    finally: tmp.unlink(missing_ok=True)
                self.api.aux(it['h'], 'f', M.face_sprite(im, fs)); n += 1
            except Exception as e:  # noqa: BLE001
                log(f'  补人脸小图条失败 {it["n"]}: {e}')
        log(f'补了 {n} 张照片的人脸小图条（共 {len(items)} 张缺）')
        return n

    # ---------------- 主循环 ----------------
    def run(self):
        self.stop = False
        if self.args.retime and self.retime():
            self.dirty = True                           # 时间变了 → 时刻 / 连拍要重新切
        threading.Thread(target=self.ws_loop, daemon=True).start()
        if self.args.store:
            threading.Thread(target=self.disk_loop, daemon=True).start()
        if self.edit_keys:
            threading.Thread(target=self.edit_loop, daemon=True).start()
        if not self.args.no_transcode:
            threading.Thread(target=self.transcode_loop, daemon=True).start()
        last_check, defer_since = 0, None
        while True:
            pend = self.api.get(f'/api/pipe/pending?aver={AVER}&limit={BATCH}')
            # 上传和后处理分开：相册的数据库同一时间只处理一个请求，聚类 / 对齐时间 / 补小图条这些重活
            # 一次要占着它零点几秒到几秒（读 8 MB 向量、写几百行），这时候用户的上传请求就得排队（实测 p95 120 → 400 ms）。
            # 所以有人在上传（最近 UP_QUIET 秒内有上传动作）就先不做，等上传停了再做；一直有人传也最多推迟 MAX_DEFER。
            # 逐张分析新照片（看图、认脸）照常做 —— 它对数据库很轻，而且大家想尽快看到描述和人脸
            busy = pend.get('upAgo') is not None and pend['upAgo'] < UP_QUIET
            if busy and defer_since is None:
                defer_since = time.time()
                log(f'有人在上传 —— 聚类 / 对齐时间 / 补小图条先等上传停 {UP_QUIET} 秒（最多推迟 {MAX_DEFER // 60} 分钟）')
            if not busy:
                defer_since = None
            hold = busy and time.time() - defer_since < MAX_DEFER
            if pend['queries']:
                self.api.post('/api/pipe/vecs', {'items': self.embed_qs(pend['queries'])})
                log(f'补算了 {len(pend["queries"])} 个排队的搜索词向量')
            if pend['items']:
                log(f'待分析 {len(pend["items"])} 个（相册共 {pend["total"]}）')
                self.process(pend['items'])
                self.dirty = True
                continue                    # 积压没处理完就不聚类，全部处理完再做一次
            if not hold and not self.dirty and time.time() - last_check > 60:
                # 认领是在页面上发生的：服务端会推 recluster，但万一 WS 断着就靠这里兜底。
                # 比服务端给的「已确认人脸」小签名，不再每分钟拉 3 MB 的全部人脸回来比
                last_check = time.time()
                if pend.get('conf') is not None and pend['conf'] != self.conf_srv:
                    self.dirty = True
            if self.dirty and not hold:
                self.dirty = False
                self.conf_srv = pend.get('conf')
                self.recluster()
            if not hold and time.time() - getattr(self, 'last_sprites', 0) > 600:
                self.last_sprites = time.time()
                self.backfill_sprites()
            if self.args.once:
                self.edit_pool.shutdown(wait=True)
                self.stop = True
                return
            self.wake.wait(15)
            self.wake.clear()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='https://nordic.airacle.com')
    ap.add_argument('--cache', default=os.environ.get('PHOTOS_CACHE', '/mnt/localssd/photos-cache'))
    ap.add_argument('--once', action='store_true', help='处理完积压、聚类一次就退出（测试用）')
    ap.add_argument('--keep', action='store_true', help='保留下载的原件（默认分析完就删）')
    ap.add_argument('--no-vlm', action='store_true', help='不加载 Qwen（只做向量/人脸，调试用）')
    ap.add_argument('--no-edit', action='store_true', help='不开 AI 改图（不连模型网关）')
    ap.add_argument('--store', default=os.environ.get('PHOTOS_STORE', ''), help='相册存储目录（本机部署时）：每分钟上报磁盘用量')
    ap.add_argument('--no-transcode', action='store_true', help='不转视频（H.264 新版 + 调色，见 video.py）')
    ap.add_argument('--retime', action='store_true', help='开工前把已分析的照片按拍摄地重算一遍拍摄时间（幂等）')
    # 语义搜索的两道门（SigLIP2 余弦）：绝对下限 + 离最高分多近。在 36 个中英文查询上量的，见 README
    ap.add_argument('--sem-floor', type=float, default=0.05)
    ap.add_argument('--sem-win', type=float, default=0.04)
    a = ap.parse_args()
    os.environ.setdefault('HF_HOME', '/mnt/localssd/.cache/huggingface')
    Worker(a).run()


if __name__ == '__main__':
    main()
