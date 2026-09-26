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
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cluster  # noqa: E402
import media as M  # noqa: E402
from models import face_vec, q8  # noqa: E402  （不加载模型，只是两个小函数）

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
        self.dirty = True                  # 启动时先聚类一次（上一个 worker 可能没跑完）
        self.gpu = threading.Lock()        # WebSocket 线程和主循环共用模型
        log('加载模型 …')
        t = time.time()
        from models import Models
        self.m = Models(vlm=not args.no_vlm)
        log(f'模型就绪 {time.time() - t:.0f}s')
        self.conf_sig = None
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
            except Exception as e:           # noqa: BLE001 —— 断了就重连，不影响主循环
                if not self.stop:
                    log('WebSocket 断开，5 秒后重连:', repr(e)[:160])
                    time.sleep(5)

    # ---------------- AI 改图 ----------------
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
                im, _ = M.open_image(path)
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
        if it['kind'] == 'video':
            vm = M.video_meta(path)
            res.update({k: vm[k] for k in ('w', 'hh', 'dur', 'lat', 'lon', 'cam', 'taken') if vm.get(k) is not None})
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
                im, meta = M.open_image(path)
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
        ok = [(it, im, res) for it, im, res in prepped if im is not None]
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
            if utc and 'taken' not in res:
                # 视频只有 UTC 时间 → 按拍摄地的国家换成当地时间（没 GPS 就按 UTC 存，误差在 0–2 小时）
                res['taken'] = M.utc_to_local(utc, cc)
            for k in [k for k in res if k.startswith('_')]:
                res.pop(k)
            res['aver'] = AVER
            r = self.api.post('/api/pipe/result', {k: v for k, v in res.items() if v is not None})
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

    def recluster(self):
        t = time.time()
        faces = self.api.get('/api/pipe/faces')
        media = self.api.get('/api/pipe/media')
        for m in media:
            m['tags'] = json.loads(m['tags']) if m.get('tags') else {}
        E = {}
        for r in self.api.get('/api/pipe/embs'):
            v = np.frombuffer(base64.b64decode(r['vec']), dtype=np.int8).astype(np.float32) * r['scale']
            E[r['h']] = v / (np.linalg.norm(v) or 1)
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

    # ---------------- 主循环 ----------------
    def run(self):
        self.stop = False
        threading.Thread(target=self.ws_loop, daemon=True).start()
        if self.edit_keys:
            threading.Thread(target=self.edit_loop, daemon=True).start()
        last_check = 0
        while True:
            pend = self.api.get(f'/api/pipe/pending?aver={AVER}&limit={BATCH}')
            if pend['queries']:
                self.api.post('/api/pipe/vecs', {'items': self.embed_qs(pend['queries'])})
                log(f'补算了 {len(pend["queries"])} 个排队的搜索词向量')
            if pend['items']:
                log(f'待分析 {len(pend["items"])} 个（相册共 {pend["total"]}）')
                self.process(pend['items'])
                self.dirty = True
                continue                    # 积压没处理完就不聚类，全部处理完再做一次
            if not self.dirty and time.time() - last_check > 60:
                # 认领是在页面上发生的：服务端会推 recluster，但万一 WS 断着就靠这里兜底
                last_check = time.time()
                if self.confirmed_sig(self.api.get('/api/pipe/faces')) != self.conf_sig:
                    self.dirty = True
            if self.dirty:
                self.dirty = False
                self.recluster()
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
    # 语义搜索的两道门（SigLIP2 余弦）：绝对下限 + 离最高分多近。在 36 个中英文查询上量的，见 README
    ap.add_argument('--sem-floor', type=float, default=0.05)
    ap.add_argument('--sem-win', type=float, default=0.04)
    a = ap.parse_args()
    os.environ.setdefault('HF_HOME', '/mnt/localssd/.cache/huggingface')
    Worker(a).run()


if __name__ == '__main__':
    main()
