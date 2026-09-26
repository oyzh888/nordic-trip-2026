#!/usr/bin/env python3
"""GPU 分析端的端到端测试：真照片 + 真模型 + 真 HTTP，本地 wrangler dev 和线上共用。

    python test/pipe_e2e.py http://localhost:8787                  # 自己起一个 worker.py 子进程
    python test/pipe_e2e.py https://nordic.airacle.com --external  # 线上已经有常驻 worker 在跑，只看结果

素材（不进仓库，localssd 上）：Wikimedia Commons 的冰岛/里斯本风景 + 公众人物的公开照片（当「同行的人」），
按一条假行程注入 EXIF（相机、时间、GPS）。上传时**不带**浏览器端读出的元数据、也不传缩略图 ——
等于最坏情况（HEIC、浏览器解不了的格式），全部要靠 GPU 端补齐。

两轮：第一轮传完 → 分析 + 聚类 → 用户认领「这是我」、给另一个簇起名 → 第二轮再传两张同一批人的新照片
→ 检查它们被自动归到认领过的人名下。结束时（包括失败）把本轮的文件、用户、人物、搜索词全部删掉。
"""
import io, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results, upload

BASE = e2e.BASE
EXTERNAL = '--external' in sys.argv
EDITS = '--no-edit' not in sys.argv
SET = os.environ.get('PHOTOS_TESTSET', '/mnt/localssd/photos-testset')
FX = os.path.join(SET, 'fx')
PY = '/mnt/localssd/venvs/photos/bin/python'
WORKER = os.path.join(e2e.HERE, '..', 'pipeline', 'worker.py')
LOG = os.path.join(e2e.HERE, 'out', f"pipe-worker-{'local' if 'localhost' in BASE else 'prod'}.log")
TAG = e2e.TAG
UA, UB = e2e.UA, e2e.UB
PERSONS = []

# 假行程：(文件名, 素材, 相机, 当地时间, 纬度, 经度)
REYK, KIRK = (64.1417, -21.9266), (64.9429, -23.3065)
PLAN = [
    ('IMG_5001.JPG', 'hallgrims', 'Apple|iPhone 15 Pro Max', '2026:09:26 15:00:00', *REYK),
    ('IMG_5002.JPG', 'group', 'Apple|iPhone 15 Pro Max', '2026:09:26 15:20:00', *REYK),
    ('IMG_5003.JPG', 'fishchips', 'Apple|iPhone 13', '2026:09:26 18:30:00', 64.1466, -21.9426),
    ('IMG_5004.JPG', 'merkel_0', 'Apple|iPhone 13', '2026:09:26 20:00:00', 64.1466, -21.9426),
    ('IMG_5005.JPG', 'merkel_1', 'Apple|iPhone 13', '2026:09:26 20:04:00', 64.1466, -21.9426),
    ('IMG_5006.JPG', 'merkel_2', 'Apple|iPhone 13', '2026:09:26 20:09:00', 64.1466, -21.9426),
    ('PXL_0001.jpg', 'macron_0', 'Google|Pixel 8', '2026:09:27 12:00:00', 64.9250, -23.2600),
    ('PXL_0002.jpg', 'macron_2', 'Google|Pixel 8', '2026:09:27 12:03:00', 64.9250, -23.2600),
    # 同一个机位 7 秒内 4 张（原图 + 轻糊 + 重糊 + 裁一点）→ 应该成一组，封面是原图
    ('DSC01001.JPG', 'aurora2', 'SONY|ILCE-7M4', '2026:09:27 22:14:05', *KIRK),
    ('DSC01002.JPG', 'aurora2:b2', 'SONY|ILCE-7M4', '2026:09:27 22:14:07', *KIRK),
    ('DSC01003.JPG', 'aurora2:b6', 'SONY|ILCE-7M4', '2026:09:27 22:14:09', *KIRK),
    ('DSC01004.JPG', 'aurora2:crop', 'SONY|ILCE-7M4', '2026:09:27 22:14:12', *KIRK),
    ('IMG_5010.JPG', 'seljalandsfoss', 'Apple|iPhone 15 Pro Max', '2026:09:28 10:00:00', 63.6156, -19.9886),
    ('IMG_5011.JPG', 'group:flip', 'Apple|iPhone 15 Pro Max', '2026:09:28 10:05:00', 63.6156, -19.9886),
    ('IMG_5012.JPG', 'skogafoss', 'Apple|iPhone 15 Pro Max', '2026:09:28 11:30:00', 63.5321, -19.5114),
    ('IMG_5014.JPG', 'reynisfjara', 'Apple|iPhone 15 Pro Max', '2026:09:28 14:00:00', 63.4044, -19.0450),
    ('IMG_5015.JPG', 'aurora1', 'Apple|iPhone 15 Pro Max', '2026:09:28 23:00:00', 63.4194, -19.0060),
    # 同一个冰河湖、同一分钟、两个机位（余弦 0.85）→ 不该被当成连拍藏掉一张
    ('DSC01101.JPG', 'jokulsarlon1', 'SONY|ILCE-7M4', '2026:09:29 12:00:00', 64.0784, -16.2306),
    ('DSC01102.JPG', 'jokulsarlon2', 'SONY|ILCE-7M4', '2026:09:29 12:01:00', 64.0790, -16.2290),
    ('IMG_5020.JPG', 'puffin', 'Apple|iPhone 15 Pro Max', '2026:10:01 10:00:00', 65.5445, -13.7555),
    ('IMG_5030.JPG', 'natas', 'Apple|iPhone 13', '2026:10:14 16:00:00', 38.6975, -9.2032),
    ('IMG_5031.JPG', 'tram28', 'Apple|iPhone 13', '2026:10:15 14:00:00', 38.7115, -9.1300),
]
ROUND2 = [
    ('IMG_5040.HEIC', 'merkel_4', 'Apple|iPhone 15 Pro Max', '2026:10:02 19:00:00', 65.2600, -14.4000),
    ('PXL_0003.jpg', 'macron_4', 'Google|Pixel 8', '2026:10:02 19:05:00', 65.2600, -14.4000),
]


def src_image(spec):
    from PIL import Image, ImageFilter, ImageOps
    name, _, fx = spec.partition(':')
    if name == 'group':
        import insightface
        im = Image.fromarray(insightface.data.get_image('t1')[:, :, ::-1])      # 自带的 6 人合影（BGR → RGB）
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    else:
        p = os.path.join(SET, 'people' if '_' in name else 'src', name + '.jpg')
        im = ImageOps.exif_transpose(Image.open(p)).convert('RGB')
    if fx == 'b2': im = im.filter(ImageFilter.GaussianBlur(2))
    if fx == 'b6': im = im.filter(ImageFilter.GaussianBlur(6))
    if fx == 'crop':
        w, h = im.size
        im = im.crop((int(w * .04), int(h * .04), int(w * .96), int(h * .96))).filter(ImageFilter.GaussianBlur(1))
    if fx == 'flip': im = ImageOps.mirror(im)
    return im


def make_fixtures():
    from PIL import Image
    import pillow_heif
    from ui import rational
    os.makedirs(FX, exist_ok=True)
    out = []
    for fn, spec, cam, taken, lat, lon in PLAN + ROUND2:
        p = os.path.join(FX, fn)
        out.append(p)
        if os.path.exists(p): continue
        im = src_image(spec)
        ex = Image.Exif()
        ex[0x010F], ex[0x0110] = cam.split('|')
        ex.get_ifd(0x8769)[0x9003] = taken
        g = ex.get_ifd(0x8825)
        g[1], g[2], g[3], g[4] = ('N' if lat >= 0 else 'S'), rational(abs(lat)), ('E' if lon >= 0 else 'W'), rational(abs(lon))
        if fn.endswith('.HEIC'):
            pillow_heif.from_pillow(im).save(p, quality=80, exif=ex.tobytes(), enc_params={'x265:pools': '8'})
        else:
            im.save(p, 'JPEG', quality=92, exif=ex.tobytes())
    # 视频 1：普通相机/安卓那种 H.264 mp4 —— 只有 UTC 的 creation_time + ©xyz 位置 → GPU 端要按葡萄牙换成当地时间
    v1 = os.path.join(FX, 'VID_5032.mp4')
    if not os.path.exists(v1):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', os.path.join(SET, 'src', 'tram28.jpg'), '-t', '4', '-r', '30',
                        '-vf', 'scale=1280:-2,format=yuv420p', '-c:v', 'libx264', '-metadata', 'creation_time=2026-10-15T13:05:00Z',
                        '-metadata', 'location=+38.7115-009.1300/', v1], check=True)
    # 视频 2：iPhone 的 HEVC .mov —— 带时区的 com.apple.quicktime.creationdate；Windows Chrome 放不了 → 必须转出 H.264 预览
    v2 = os.path.join(FX, 'IMG_5013.MOV')
    if not os.path.exists(v2):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', os.path.join(SET, 'src', 'skogafoss.jpg'), '-t', '4', '-r', '30',
                        '-vf', 'scale=1280:-2,format=yuv420p', '-c:v', 'libx265', '-x265-params', 'pools=8:log-level=error', '-tag:v', 'hvc1',
                        '-movflags', 'use_metadata_tags',
                        '-metadata', 'com.apple.quicktime.creationdate=2026-09-28T11:35:00+0000',
                        '-metadata', 'com.apple.quicktime.location.ISO6709=+63.5321-019.5114+020.000/',
                        '-metadata', 'com.apple.quicktime.make=Apple', '-metadata', 'com.apple.quicktime.model=iPhone 15 Pro Max',
                        '-metadata', 'creation_time=2026-09-28T11:35:00Z', v2], check=True)
    return out[:len(PLAN)] + [v2, v1], out[len(PLAN):]


TYPES = {'.jpg': 'image/jpeg', '.heic': 'image/heic', '.mov': 'video/quicktime', '.mp4': 'video/mp4'}


def up(c, paths, H):
    for p in paths:
        fn = os.path.basename(p)
        h, r, _ = upload(c, fn, open(p, 'rb').read(), TYPES[os.path.splitext(fn)[1].lower()])
        assert r.get('status') in ('exists', 'done'), (fn, r)
        H[fn] = h


class Log:
    """盯 worker 日志：等「全部分析完」之后的下一行「聚类」—— 那一刻服务端的结果才是完整的"""

    def __init__(self, path):
        self.path, self.pos = path, 0

    def mark(self):
        self.pos = os.path.getsize(self.path) if os.path.exists(self.path) else 0

    def new(self):
        if not os.path.exists(self.path): return ''
        with open(self.path, encoding='utf-8', errors='replace') as f:
            f.seek(self.pos); return f.read()


def wait_done(A, P, hs, timeout=900):
    """等到这批文件都分析完，并且在最后一条分析结果之后又聚类过一次。
    看服务端的两个序号，不看日志 —— worker 在别的机器上（--external）也成立；
    worker 是串行的（分析一批 → 聚类 → 下一批），所以聚类号大于结果号 = 那次聚类已经看到了全部结果"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        items = {x['h']: x for x in A.get('/api/list').json()['items']}
        pend = [h for h in hs if not items.get(h, {}).get('a')]
        if not pend:
            st = P.get('/api/pipe/status').json()
            if st['cl'] > st['res']:
                return time.time() - t0
        time.sleep(3)
    raise TimeoutError(f'{len(pend)} 个还没分析完')


def main():
    A, B, P = Client(), Client(), Client(e2e.PIPE)
    A.login(UA); B.login(UB)
    r1, r2 = make_fixtures()
    worker = None
    logw = Log(LOG)
    if not EXTERNAL:
        logw.mark()
        worker = subprocess.Popen([PY, WORKER, '--base', BASE], stdout=open(LOG, 'a'), stderr=subprocess.STDOUT,
                                  env={**os.environ, 'PYTHONWARNINGS': 'ignore'})
    try:
        run(A, B, P, r1, r2, logw)
    finally:
        if worker:
            worker.terminate()
            try: worker.wait(20)
            except subprocess.TimeoutExpired: worker.kill()


def run(A, B, P, r1, r2, logw):
    H = {}
    t = time.time()
    up(A, r1[:14], H); up(B, r1[14:], H)
    print(f'第一轮上传 {len(r1)} 个 {time.time() - t:.1f}s（不带任何浏览器端元数据/缩略图）', flush=True)
    dt = wait_done(A, P, [H[os.path.basename(p)] for p in r1])
    check('第一轮：全部分析完并聚类', True, f'{dt:.0f}s · {len(r1)} 个文件')

    L = A.get('/api/list').json()
    I = {x['h']: x for x in L['items']}
    M = {x['h']: x for x in P.get('/api/pipe/media').json()}
    by = {fn: I.get(h) for fn, h in H.items()}
    missing = [fn for fn, x in by.items() if not x or not x.get('a')]
    check('每个文件都标记为已分析', not missing, missing)
    thumbs = {fn: x['f'] & 3 for fn, x in by.items() if x}
    check('缩略图 + 预览图全部由 GPU 端补齐（包括视频）', all(v == 3 for v in thumbs.values()), {k: v for k, v in thumbs.items() if v != 3})
    for k in ('t', 'p'):
        r = A.get(f"/f/{H['IMG_5013.MOV']}/{k}")
        check(f'HEVC 视频的 {k} 图能取到', r.status_code == 200 and r.content[:2] == b'\xff\xd8', r.status_code)

    # ---- 元数据
    tk = {fn: (by[fn] or {}).get('t') for fn in ('IMG_5001.JPG', 'DSC01001.JPG', 'VID_5032.mp4', 'IMG_5013.MOV')}
    check('照片拍摄时间来自 EXIF', tk['IMG_5001.JPG'] == '2026-09-26T15:00:00' and tk['DSC01001.JPG'] == '2026-09-27T22:14:05', tk)
    check('mp4 只有 UTC 时间 → 按葡萄牙换成当地时间（13:05Z → 14:05）', tk['VID_5032.mp4'] == '2026-10-15T14:05:00', tk['VID_5032.mp4'])
    check('iPhone .mov 用自带的当地时间', tk['IMG_5013.MOV'] == '2026-09-28T11:35:00', tk['IMG_5013.MOV'])
    cams = {fn: (by[fn] or {}).get('cam') for fn in ('IMG_5001.JPG', 'DSC01001.JPG', 'PXL_0001.jpg', 'IMG_5013.MOV')}
    check('相机型号', cams == {'IMG_5001.JPG': 'Apple iPhone 15 Pro Max', 'DSC01001.JPG': 'SONY ILCE-7M4',
                              'PXL_0001.jpg': 'Google Pixel 8', 'IMG_5013.MOV': 'Apple iPhone 15 Pro Max'}, cams)
    vd = by['VID_5032.mp4'] or {}
    check('视频时长和尺寸', abs((vd.get('d') or 0) - 4) < 0.3 and vd.get('w') == 1280, (vd.get('d'), vd.get('w'), vd.get('hh')))
    pl = {fn: (by[fn] or {}).get('pl') for fn in ('IMG_5001.JPG', 'IMG_5010.JPG', 'DSC01101.JPG', 'IMG_5030.JPG', 'VID_5032.mp4')}
    check('地名是中文（按 GPS 反查）', all(v and ('冰岛' in v or '葡萄牙' in v) for v in pl.values()), pl)

    # ---- 视频预览
    for fn in ('IMG_5013.MOV', 'VID_5032.mp4'):
        r = A.get(f'/f/{H[fn]}/v')
        codec = None
        if r.status_code == 200:
            tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), f'pv-{TAG}.mp4')
            open(tmp, 'wb').write(r.content)
            pr = json.loads(subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', tmp],
                                           capture_output=True, text=True).stdout or '{}')
            codec = next((s['codec_name'] for s in pr.get('streams', []) if s['codec_type'] == 'video'), None)
            os.unlink(tmp)
        check(f'{fn} 有 720p H.264 预览（所有浏览器能放）', codec == 'h264', f'{r.status_code} {codec} {len(r.content) / 1e3:.0f} KB')

    # ---- 描述 / 标签
    sp = lambda fn: set(((by[fn] or {}).get('tg') or {}).get('special') or [])
    caps = {fn: (by[fn] or {}).get('cap') for fn in H}
    check('每张图都有中文描述', all(c and any('一' <= ch <= '鿿' for ch in c) for c in caps.values()),
          [fn for fn, c in caps.items() if not c])
    want = {'DSC01001.JPG': {'极光'}, 'IMG_5015.JPG': {'极光'}, 'IMG_5010.JPG': {'瀑布'}, 'IMG_5012.JPG': {'瀑布'},
            'DSC01101.JPG': {'冰川', '冰河湖'}, 'IMG_5020.JPG': {'海鹦', '野生动物'}, 'IMG_5030.JPG': {'美食'},
            'IMG_5003.JPG': {'美食'}, 'IMG_5014.JPG': {'黑沙滩'}}
    got = {fn: sorted(sp(fn)) for fn in want}
    hit = [fn for fn, w in want.items() if sp(fn) & w]
    check('特殊场景标签（极光/瀑布/冰川/海鹦/美食/黑沙滩）', len(hit) >= len(want) - 1, f'{len(hit)}/{len(want)} {got}')
    print('  描述样例：', {fn: caps[fn] for fn in ('DSC01001.JPG', 'IMG_5010.JPG', 'IMG_5020.JPG', 'IMG_5031.JPG')})

    # ---- 连拍 / 相似只留最好
    bu = {fn: ((by[fn] or {}).get('b'), (by[fn] or {}).get('bc')) for fn in ('DSC01001.JPG', 'DSC01002.JPG', 'DSC01003.JPG', 'DSC01004.JPG')}
    check('同机位 7 秒内 4 张 → 同一组', len({b for b, _ in bu.values()}) == 1 and None not in {b for b, _ in bu.values()}, bu)
    check('组封面 = 没糊的原图', bu['DSC01001.JPG'][1] and not any(c for fn, (_, c) in bu.items() if fn != 'DSC01001.JPG'),
          {fn: M[H[fn]]['score'] for fn in bu})
    j1, j2 = (by['DSC01101.JPG'] or {}).get('b'), (by['DSC01102.JPG'] or {}).get('b')
    check('同一个冰河湖两个机位 → 不算重复（都显示）', not j1 or j1 != j2, (j1, j2))
    g1, g2 = (by['IMG_5002.JPG'] or {}).get('b'), (by['IMG_5011.JPG'] or {}).get('b')
    check('不同地点/时间的相似合影 → 不算重复', not g1 or g1 != g2, (g1, g2))

    # ---- 时刻 / 场景
    mo = L.get('moments') or []
    ours = {(by[fn] or {}).get('mo') for fn in H} - {None}
    mine = [m for m in mo if m['id'] in ours]
    check('按时间+地点切成时刻，每段都有标题', len(mine) >= 8 and all(m.get('title') for m in mine),
          [f"{'★' if (m.get('memo') or 0) >= 4 else ''}{m['title']}({m['n']})" for m in mine])
    au = next((m for m in mine if m['id'] == (by['DSC01001.JPG'] or {}).get('mo')), {})
    check('极光那段被标成值得纪念（memo ≥ 4）', (au.get('memo') or 0) >= 4, au)
    sc = L.get('scenes') or []
    check('按画面内容自动分出场景，并起了中文名', len(sc) >= 2 and all(s.get('label') for s in sc), [(s['label'], s['n']) for s in sc])

    # ---- 人脸
    faces = [f for f in P.get('/api/pipe/faces').json() if f['h'] in H.values()]
    fh = {fn: [f for f in faces if f['h'] == h] for fn, h in H.items()}
    check('合影里的 6 张脸都检测到', len(fh['IMG_5002.JPG']) == 6 and len(fh['IMG_5011.JPG']) == 6,
          (len(fh['IMG_5002.JPG']), len(fh['IMG_5011.JPG'])))
    mk = {f['cluster'] for fn in ('IMG_5004.JPG', 'IMG_5005.JPG', 'IMG_5006.JPG') for f in fh[fn]}
    mc = {f['cluster'] for fn in ('PXL_0001.jpg', 'PXL_0002.jpg') for f in fh[fn]}
    check('同一个人的 3 张不同照片 → 同一簇', len(mk) == 1 and None not in mk, mk)
    check('另一个人 → 另一簇', len(mc) == 1 and None not in mc and not (mk & mc), mc)
    gp = {}
    for f in fh['IMG_5002.JPG'] + fh['IMG_5011.JPG']:
        gp.setdefault(f['cluster'], []).append(f['h'])
    pairs = sum(1 for c, hs in gp.items() if c is not None and len(set(hs)) == 2)
    check('合影和它的镜像：6 个人各自配成对', pairs == 6, f'{pairs} 对')
    ppl = A.get('/api/people').json()
    check('人物页列出待认领的簇', len(ppl['clusters']) >= 8, f"{len(ppl['clusters'])} 簇")

    # ---- 认领 → 第二轮自动归人
    logw.mark()
    r = A.post('/api/people/claim', {'cluster': mk.pop(), 'me': True}).json()
    PERSONS.append(r['person'])
    r2_ = B.post('/api/people/claim', {'cluster': mc.pop(), 'name': f'{TAG}-朋友'}).json()
    PERSONS.append(r2_['person'])
    me, friend = r['person'], r2_['person']
    t = time.time()
    up(B, r2, H)
    dt = wait_done(A, P, [H[os.path.basename(p)] for p in r2])
    faces = [f for f in P.get('/api/pipe/faces').json() if f['h'] in (H['IMG_5040.HEIC'], H['PXL_0003.jpg'])]
    got = {fn: [(f['person'], f['confirmed']) for f in faces if f['h'] == H[fn]] for fn in ('IMG_5040.HEIC', 'PXL_0003.jpg')}
    check('第二轮（别人传的 HEIC）里的脸自动归到「我」', (me, 0) in got['IMG_5040.HEIC'], f'{got} · {dt:.0f}s')
    check('另一个人也自动归到起了名的那位', (friend, 0) in got['PXL_0003.jpg'], got)
    L = A.get('/api/list').json()
    I = {x['h']: x for x in L['items']}
    mine = [fn for fn, h in H.items() if h in I and (L_uid(L, UA) in I[h]['u'] or me in I[h]['p'])]
    check('「与我相关」= 我传的 14 个 + 别人拍到我的', H['IMG_5040.HEIC'] in {H[f] for f in mine} and len(mine) >= 15, len(mine))
    hx = I.get(H['IMG_5040.HEIC'], {})
    check('HEIC：GPU 端补出缩略图，EXIF 也读到了', hx.get('f', 0) & 3 == 3 and hx.get('cam') == 'Apple iPhone 15 Pro Max'
          and hx.get('t') == '2026-10-02T19:00:00', (hx.get('f'), hx.get('cam'), hx.get('t')))

    # ---- 搜索（关键词 + 语义）
    def s(q):
        e2e.RUN['qs'].add(q)
        return A.get('/api/search', params={'q': q}).json()
    def ids(fns): return {H[f] for f in fns}
    au_fns = ids(['DSC01001.JPG', 'IMG_5015.JPG'])
    r = s('极光')
    check('搜「极光」→ 两个地方的极光都在', au_fns <= set(r['ids']), f"{len(r['ids'])} 个 · 语义 {r['sem']}")
    r = s('green lights dancing in the night sky')
    check('英文整句（标签里没有的说法）→ 语义搜索命中极光', r['sem'] and set(r['ids'][:2]) & au_fns, f"sem={r['sem']} top={[k for k, v in H.items() if v in r['ids'][:3]]}")
    r = s('海边的小鸟')
    check('中文描述式搜索「海边的小鸟」→ 海鹦在前三', H['IMG_5020.JPG'] in r['ids'][:3], [k for k, v in H.items() if v in r['ids'][:3]])
    r = s('ice floating on water')
    check('「ice floating on water」→ 冰河湖', set(r['ids'][:3]) & ids(['DSC01101.JPG', 'DSC01102.JPG']), [k for k, v in H.items() if v in r['ids'][:3]])
    neg = {q: s(q)['ids'] for q in ('长颈鹿', 'giraffe', '沙漠骆驼')}
    check('搜不相干的东西（长颈鹿 / giraffe / 沙漠骆驼）→ 不乱给结果', all(not v for v in neg.values()),
          {q: [k for k, v in H.items() if v in x] for q, x in neg.items()})
    r2c = s('极光')
    check('同一个搜索第二次命中结果缓存', r2c.get('cached'), f"{r2c.get('took')} ms")

    # ---- AI 改图（经模型网关；三个模型同时各改一张，顺便测 GPU 端的并发）
    if EDITS:
        ai_edits(A, B, P, H)


def ai_edits(A, B, P, H):
    L = A.get('/api/list').json()
    check('分析端报了可用的改图模型', set(L.get('ai') or []) >= {'nano', 'pro', 'gpt'}, L.get('ai'))
    src = H['IMG_5001.JPG']
    bad = {
        '空提示词': A.post('/api/edit', {'h': src, 'prompt': '  ', 'model': 'nano'}),
        '视频': A.post('/api/edit', {'h': H['VID_5032.mp4'], 'prompt': '变成黑白', 'model': 'nano'}),
        '不存在的模型': A.post('/api/edit', {'h': src, 'prompt': '变成黑白', 'model': 'dalle'}),
    }
    check('不合法的改图请求 → 400 + 中文原因', all(r.status_code == 400 and r.json().get('error') for r in bad.values()),
          {k: (r.status_code, r.json().get('error')) for k, r in bad.items()})
    P_ = '把天空换成绚丽的绿色极光，建筑保持不变'
    t0 = time.time()
    jobs = {m: A.post('/api/edit', {'h': src, 'prompt': P_, 'model': m}).json() for m in ('nano', 'pro', 'gpt')}
    check('三个模型的改图都排上队', all(j.get('id') for j in jobs.values()), jobs)
    r4 = A.post('/api/edit', {'h': src, 'prompt': P_, 'model': 'nano'})
    check('同时第 4 张 → 拒绝（每人同时最多 3 张）', r4.status_code == 400, r4.json().get('error'))
    check('别人查不到我的改图任务', B.get('/api/edit', params={'id': jobs['nano']['id']}).status_code == 404)
    done, took = {}, {}
    while len(done) < len(jobs) and time.time() - t0 < 240:
        for m, j in jobs.items():
            if m in done: continue
            r = A.get('/api/edit', params={'id': j['id']}).json()
            if r['status'] in ('done', 'error'):
                done[m], took[m] = r, round(time.time() - t0)
                if r.get('out_h'): e2e.RUN['hs'].add(r['out_h'])
        time.sleep(2)
    check('三个模型都改好了', all(d.get('status') == 'done' for d in done.values()) and len(done) == 3,
          {m: (d.get('status'), d.get('err'), f'{took.get(m)}s') for m, d in done.items()})
    outs = {m: d['out_h'] for m, d in done.items() if d.get('out_h')}
    t1 = time.time()
    while time.time() - t1 < 300:                  # 新照片也要走一遍分析（描述、人脸、向量）
        I = {x['h']: x for x in A.get('/api/list').json()['items']}
        if all(I.get(h, {}).get('a') for h in outs.values()): break
        time.sleep(3)
    L = A.get('/api/list').json()
    I = {x['h']: x for x in L['items']}
    S0 = I.get(src, {})
    for m, h in outs.items():
        x = I.get(h, {})
        ok = (x.get('src') == src and (x.get('ai') or {}).get('m') == m and (x.get('ai') or {}).get('p') == P_
              and x.get('t') == S0.get('t') and x.get('pl') == S0.get('pl') and (x.get('cam') or '').startswith('AI 编辑')
              and x.get('f', 0) & 3 == 3 and x.get('a') and L_uid(L, UA) in x.get('u', []))
        check(f'{m}：新照片（沿用原图时间/地点、标了来源和提示词、有缩略图、分析过、记在请求人名下）', ok,
              {k: x.get(k) for k in ('n', 'cam', 't', 'pl', 'f', 'a', 'ai', 'w', 'hh')} | {'mid': (x.get('ai') or {}).get('id')})
        r = A.get(f'/f/{h}/o')
        check(f'{m}：原图字节能下载、是 JPEG', r.status_code == 200 and r.content[:2] == b'\xff\xd8', f'{len(r.content) / 1e3:.0f} KB')
    o = A.get(f'/f/{src}/o').content
    check('原图没被动过（内容 ID 不变、还在相册里）', src in I and e2e.content_id(o)[0] == src)
    check('改过的图不会和原图并成「相似组」被藏掉', all(not I.get(h, {}).get('b') or I[h]['b'] != S0.get('b') for h in outs.values()),
          {m: I.get(h, {}).get('b') for m, h in outs.items()} | {'src': S0.get('b')})
    print('  改图耗时（排队到完成）：', took, ' 模型 id：', {m: (I.get(h, {}).get('ai') or {}).get('id') for m, h in outs.items()})


def L_uid(L, name):
    return next((u['id'] for u in L['users'] if u['name'] == name), None)


def cleanup():
    if not e2e.PIPE: return
    P = Client(e2e.PIPE)
    r = P.post('/api/pipe/purge', {'hs': sorted(e2e.RUN['hs']), 'users': [UA, UB], 'persons': PERSONS, 'qs': sorted(e2e.RUN['qs'])})
    left = [x for x in P.get('/api/pipe/media').json() if x['h'] in e2e.RUN['hs']]
    lf = [f for f in P.get('/api/pipe/faces').json() if f['h'] in e2e.RUN['hs']]
    check('收尾：测试文件、人脸、人物、搜索词全部删除', r.status_code == 200 and not left and not lf, r.text[:80])


if __name__ == '__main__':
    t0 = time.time()
    try:
        main()
    except Exception as e:
        import traceback; traceback.print_exc()
        check('脚本跑完', False, repr(e))
    finally:
        cleanup()
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} 通过 · {time.time() - t0:.0f}s · {BASE}")
    json.dump({'base': BASE, 'tag': TAG, 'results': [{'name': n, 'ok': o, 'detail': str(d)} for n, o, d in results]},
              open(os.path.join(e2e.HERE, 'out', f"pipe-{'local' if 'localhost' in BASE else 'prod'}.json"), 'w'),
              ensure_ascii=False, indent=1, default=str)
    sys.exit(1 if bad else 0)
