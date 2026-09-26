#!/usr/bin/env python3
"""相册端到端测试：真的走一遍 HTTP，本地 wrangler dev 和线上共用。

    python test/e2e.py http://localhost:8787            # 口令/令牌默认读 photos/.dev.vars
    ALBUM_PASS=… PIPE_TOKEN=… python test/e2e.py https://nordic.airacle.com

测试数据全部用 E2E- 前缀的用户名和随机字节，结束时（包括中途失败）调 /api/pipe/purge 彻底删掉：
行、人脸、向量、R2 里的原件和缩略图都不留。口令和令牌只从环境变量读，从不打印。
"""
import warnings; warnings.filterwarnings('ignore', category=DeprecationWarning)
import base64, hashlib, io, json, os, random, struct, sys, threading, time, zipfile, zlib
import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8787').rstrip('/')
HERE = os.path.dirname(os.path.abspath(__file__))


def dev_vars():
    p = os.path.join(HERE, '..', '.dev.vars')
    out = {}
    if os.path.exists(p):
        for line in open(p):
            if '=' in line and not line.startswith('#'):
                k, v = line.strip().split('=', 1)
                out[k] = v.strip('"')
    return out


DV = dev_vars()
PASS = os.environ.get('ALBUM_PASS') or DV.get('ALBUM_PASS')
PIPE = os.environ.get('PIPE_TOKEN') or DV.get('PIPE_TOKEN')
PART = 8 * 2 ** 20
TAG = f'E2E{random.randrange(10**6):06d}'          # 每次运行唯一，线上并发跑也不会串
UA, UB = f'{TAG}-甲', f'{TAG}-乙'
RUN = {'hs': set(), 'qs': set()}
results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f'  — {detail}' if detail else ''), flush=True)
    return cond


class Client:
    """requests 不会在 http:// 上回传 Secure cookie（本地 dev 就是 http），所以自己管 cookie 头。"""

    def __init__(self, token=None):
        self.s = requests.Session()
        self.cookie = None
        self.token = token

    def h(self, extra=None):
        h = {}
        if self.cookie: h['cookie'] = self.cookie
        if self.token: h['authorization'] = 'Bearer ' + self.token
        h.update(extra or {})
        return h

    def req(self, method, path, **kw):
        kw['headers'] = self.h(kw.get('headers'))
        kw.setdefault('timeout', 60)
        return self.s.request(method, BASE + '/photos' + path, **kw)

    def get(self, p, **kw): return self.req('GET', p, **kw)
    def post(self, p, js=None, **kw): return self.req('POST', p, json=js, **kw)

    def login(self, name):
        r = self.post('/api/login', {'pass': PASS, 'name': name})
        sc = r.headers.get('set-cookie', '')
        self.cookie = sc.split(';', 1)[0] if sc.startswith('np_sess=') else None
        return r


def content_id(b):
    parts = [b[i:i + PART] for i in range(0, max(len(b), 1), PART)]
    return hashlib.sha256(b''.join(hashlib.sha256(p).digest() for p in parts)).hexdigest(), parts


def upload(c, name, b, typ='image/jpeg', meta=None, skip=()):
    """走和浏览器一样的三步：init → 缺哪块传哪块 → complete。skip = 故意不传的块号（模拟断网）"""
    h, parts = content_id(b)
    RUN['hs'].add(h)
    m = {'h': h, 'size': len(b), 'name': name, 'type': typ, 'crc': zlib.crc32(b), **(meta or {})}
    r = c.post('/api/upload/init', m).json()
    if r.get('status') == 'exists': return h, r, 0
    sent = 0
    for n, p in enumerate(parts, 1):
        if n in r.get('done', []) or n in skip: continue
        x = c.req('PUT', f'/api/upload/part?h={h}&n={n}', data=p,
                  headers={'x-part-sha256': hashlib.sha256(p).hexdigest(), 'content-type': 'application/octet-stream'})
        assert x.status_code == 200, x.text
        sent += 1
    return h, c.post('/api/upload/complete', {'h': h}).json(), sent


def jpeg(color, text='', size=(640, 480)):
    from PIL import Image, ImageDraw
    im = Image.new('RGB', size, color)
    d = ImageDraw.Draw(im)
    for i in range(0, size[0], 40): d.line([(i, 0), (size[0] - i, size[1])], fill=tuple(255 - v for v in color), width=3)
    d.text((20, 20), text + ' ' + TAG, fill=(255, 255, 255))
    bio = io.BytesIO(); im.save(bio, 'JPEG', quality=85); return bio.getvalue()


def b64(x): return base64.b64encode(x).decode()


def i8vec(v):
    s = max(abs(t) for t in v) / 127 or 1
    return b64(struct.pack(f'{len(v)}b', *[round(t / s) for t in v])), s


def f32vec(v): return b64(struct.pack(f'<{len(v)}f', *v))


def unit(v):
    n = sum(t * t for t in v) ** .5
    return [t / n for t in v]


def main():
    assert PASS and PIPE, '需要 ALBUM_PASS 和 PIPE_TOKEN（环境变量或 photos/.dev.vars）'
    print(f'目标 {BASE}  · 本轮标记 {TAG}  · 口令 {len(PASS)} 位 · 令牌 {len(PIPE)} 位\n')
    anon, A, B, P = Client(), Client(), Client(), Client(PIPE)

    # ---------- 页面 + 鉴权 ----------
    r = anon.get('/')
    check('相册页面可打开', r.status_code == 200 and 'id="gate"' in r.text, f'{r.status_code}')
    r = anon.s.get(BASE + '/photos', allow_redirects=False)
    check('/photos 跳转到 /photos/', r.status_code in (301, 307, 308) and r.headers.get('location', '').endswith('/photos/'))
    check('没登录调接口 → 401', anon.get('/api/list').status_code == 401)
    check('没登录拿原图 → 401', anon.get('/f/' + '0' * 64 + '/o').status_code == 401)
    r = anon.post('/api/login', {'pass': 'wrong-' + TAG})
    check('口令错 → 403', r.status_code == 403, r.json().get('error'))
    r = anon.post('/api/login', {'pass': PASS})
    check('口令对、没报名字 → 让选名字', r.status_code == 200 and r.json().get('need') == 'name')
    r = A.login(UA); check('用户甲登录发 cookie', r.status_code == 200 and A.cookie, r.headers.get('set-cookie', '')[:0])
    sc = r.headers.get('set-cookie', '')
    check('cookie 是 HttpOnly+Secure+Path=/photos', all(k in sc for k in ('HttpOnly', 'Secure', 'Path=/photos')))
    B.login(UB)
    uidA = A.get('/api/me').json()['user']['id']
    check('/api/me 认得出是谁', A.get('/api/me').json()['user']['name'] == UA)
    forged = Client(); forged.cookie = f'np_sess={uidA}.9999999999.AAAA'
    check('伪造 cookie → 401', forged.get('/api/list').status_code == 401)
    check('普通用户调 GPU 端接口 → 403', A.get('/api/pipe/pending').status_code == 403)
    check('GPU 令牌不能冒充用户上传', P.post('/api/upload/init', {}).status_code == 403)

    # ---------- GPU 端 WebSocket：上线、收「新文件」通知、按需算搜索向量 ----------
    import websockets.sync.client as wsc
    ws_url = BASE.replace('http', 'ws', 1) + '/photos/api/pipe/ws'
    got, stop = [], threading.Event()
    QV = unit([1.0] + [0.0] * 15)        # 「会被 GPU 端算出来」的那个查询向量
    ws = wsc.connect(ws_url, additional_headers={'authorization': 'Bearer ' + PIPE}, open_timeout=20)

    def pump():
        while not stop.is_set():
            try: m = json.loads(ws.recv(timeout=1))
            except TimeoutError: continue
            except Exception: return
            got.append(m)
            if m.get('t') == 'embed':
                # 只回答本轮的测试新词。真实的词（瀑布、sony…）不回 —— 查询向量是永久缓存，
                # 在线上给它们写一个假向量会一直污染真实搜索；不回答它们就走「等 2.5 秒超时 → 进待算队列」
                mine = [q for q in m['q'] if TAG.lower() in q]
                if mine: ws.send(json.dumps({'t': 'vecs', 'items': [{'q': q, 'vec': f32vec(QV)} for q in mine]}))
    th = threading.Thread(target=pump, daemon=True); th.start()
    time.sleep(1)
    check('GPU 端连上后列表显示「在线」', A.get('/api/list').json().get('pipe') is True)

    # ---------- 上传：单块 ----------
    img = {k: jpeg(c, k) for k, c in [('aurora1', (20, 120, 90)), ('aurora2', (22, 118, 92)), ('aurora3', (18, 125, 88)),
                                        ('falls', (60, 90, 140)), ('group', (140, 80, 60))]}
    meta = {'taken': '2026-09-27T22:14:05', 'lat': 64.14, 'lon': -21.94, 'cam': 'Apple iPhone 15 Pro Max'}
    H = {}
    for i, (k, b) in enumerate(img.items()):
        mm = dict(meta, taken=f'2026-09-27T22:14:0{5 + i}') if k.startswith('aurora') else dict(meta, taken='2026-09-28T13:02:00', cam='SONY ILCE-7M4')
        h, r, sent = upload(A, f'IMG_{k}.JPG', b, meta=mm)
        H[k] = h
        if k == 'aurora1': check('单块照片上传完成', r['status'] == 'done' and sent == 1, r)
    time.sleep(.5)
    check('GPU 端收到「新文件」推送', any(m.get('t') == 'new' and m.get('h') == H['aurora1'] for m in got), f'{len(got)} 条消息')

    # ---------- 秒传（去重） ----------
    h, r, sent = upload(B, 'copy-of-aurora1.jpg', img['aurora1'])
    check('乙传同一张 → 秒传，一个字节都不传', r.get('status') == 'exists' and sent == 0, r)
    lst = A.get('/api/list').json()
    it = next(x for x in lst['items'] if x['h'] == H['aurora1'])
    check('秒传后这张记在两个人名下', sorted(it['u']) == sorted([uidA, B.get('/api/me').json()['user']['id']]), it['u'])
    check('上传时带的 EXIF（时间/GPS/设备）进了列表', it['t'] == '2026-09-27T22:14:05' and it['cam'] == meta['cam'] and abs(it['la'] - 64.14) < 1e-6)
    et = A.get('/api/list').headers.get('etag')
    check('列表没变化 → 304（手机轮询零流量）', A.get('/api/list', headers={'if-none-match': et}).status_code == 304, et)

    # ---------- 断点续传：20 MB 视频 = 3 块，第一次只传第 1、3 块 ----------
    vid = os.urandom(20 * 2 ** 20 + 12345)
    vh, parts = content_id(vid)
    h, r, sent = upload(A, 'MVI_aurora.MOV', vid, typ='video/quicktime', meta={'taken': '2026-09-27T22:20:00', 'cam': 'Apple iPhone 15 Pro Max'}, skip=(2,))
    check('断网（少一块）时 complete 报缺哪块', r.get('status') == 'missing' and r.get('done') == [1, 3], r)
    r = B.post('/api/upload/init', {'h': vh, 'size': len(vid), 'name': 'x.mov', 'type': 'video/quicktime'}).json()
    check('换人/换设备 init → 告诉它已经有 1、3 块', r.get('status') == 'upload' and sorted(r['done']) == [1, 3], r)
    bad = bytearray(parts[1]); bad[0] ^= 1
    x = A.req('PUT', f'/api/upload/part?h={vh}&n=2', data=bytes(bad), headers={'x-part-sha256': hashlib.sha256(parts[1]).hexdigest()})
    check('传坏的块（哈希对不上）→ 422 拒收', x.status_code == 422, x.text)
    x = A.req('PUT', f'/api/upload/part?h={vh}&n=2', data=parts[1][:-1])
    check('长度不对的块 → 400 拒收', x.status_code == 400, x.text)
    x = A.req('PUT', f'/api/upload/part?h={vh}&n=9', data=b'x')
    check('块号越界 → 400', x.status_code == 400)
    h, r, sent = upload(A, 'MVI_aurora.MOV', vid, typ='video/quicktime')
    check('续传只补第 2 块，然后完成', r.get('status') == 'done' and sent == 1, f'{r} sent={sent}')
    H['vid'] = vh

    # ---------- 内容 ID 造假：声称的 h 和字节对不上 ----------
    junk = os.urandom(1000); fake = hashlib.sha256(os.urandom(8)).hexdigest(); RUN['hs'].add(fake)
    A.post('/api/upload/init', {'h': fake, 'size': 1000, 'name': 'fake.jpg', 'type': 'image/jpeg'})
    A.req('PUT', f'/api/upload/part?h={fake}&n=1', data=junk)
    r = A.post('/api/upload/complete', {'h': fake}).json()
    check('字节和内容 ID 对不上 → corrupt，不入库', r.get('status') == 'corrupt', r)

    # ---------- 下载：原图、Range（视频拖进度条）、缓存头 ----------
    r = A.get(f'/f/{vh}/o')
    check('原视频下载字节完全一致', r.status_code == 200 and hashlib.sha256(r.content).digest() == hashlib.sha256(vid).digest(), f'{len(r.content)} B')
    check('原图带永久缓存头（内容寻址）', 'immutable' in r.headers.get('cache-control', ''))
    r = A.get(f'/f/{vh}/o', headers={'range': 'bytes=10000000-10000099'})
    check('Range 请求 → 206 且内容正确', r.status_code == 206 and r.content == vid[10000000:10000100] and r.headers.get('content-range') == f'bytes 10000000-10000099/{len(vid)}', r.headers.get('content-range'))
    r = A.get(f'/f/{vh}/o', headers={'range': 'bytes=-50'})
    check('后缀 Range（最后 50 字节）', r.status_code == 206 and r.content == vid[-50:])
    r = A.get(f"/f/{H['falls']}/o?dl=1")
    check('?dl=1 → 附件下载，文件名保留', 'attachment' in r.headers.get('content-disposition', '') and 'IMG_falls.JPG' in r.headers.get('content-disposition', ''))

    # ---------- 缩略图（浏览器端生成的那份） ----------
    th_ = jpeg((20, 120, 90), 't', (360, 270))
    x = A.req('PUT', f"/api/upload/aux?h={H['aurora1']}&k=t&w=640&hh=480", data=th_)
    check('上传者可以补缩略图', x.status_code == 200)
    x = B.req('PUT', f"/api/upload/aux?h={H['falls']}&k=t", data=th_)
    check('不是自己传的照片不能改缩略图 → 403', x.status_code == 403)
    x = A.req('PUT', f"/api/upload/aux?h={H['vid']}&k=v", data=b'x')
    check('视频预览只有 GPU 端能写 → 403', x.status_code == 403)
    r = A.get(f"/f/{H['aurora1']}/t")
    check('缩略图能取回', r.status_code == 200 and r.content == th_ and r.headers['content-type'] == 'image/jpeg')
    it = next(x for x in A.get('/api/list').json()['items'] if x['h'] == H['aurora1'])
    check('flags 标记已有缩略图、尺寸已填', it['f'] & 1 and it['w'] == 640 and it['hh'] == 480, it)

    # ---------- 模拟 GPU 端分析结果 ----------
    FACE_ME = [(.30, .25, .12, .16)]
    def face(x, y, w, hh): return {'x': x, 'y': y, 'w': w, 'hh': hh, 'score': .9, 'emb': 'e2e'}
    vec_a = unit([1.0, .1] + [0.0] * 14)        # 极光三张：和查询向量几乎一致
    vec_o = unit([0.0, 1.0] + [.2] * 14)        # 其他：不像
    fids = {}
    for k, h in H.items():
        aur = k.startswith('aurora') or k == 'vid'
        tags = {'objects': ['极光', '夜空'] if aur else (['瀑布'] if k == 'falls' else ['合影', '人']),
                'en': ['aurora', 'northern lights'] if aur else (['waterfall'] if k == 'falls' else ['group photo']),
                'special': ['极光'] if aur else (['合影'] if k == 'group' else []), 'memo': 5 if aur else 2}
        ev, es = i8vec(vec_a if aur else vec_o)
        r = P.post('/api/pipe/result', {
            'h': h, 'caption': f'{"绿色极光" if aur else k} {TAG}', 'tags': tags, 'place': '雷克雅未克 · 冰岛' if aur else '塞里雅兰瀑布 · 冰岛',
            'score': {'aurora1': .61, 'aurora2': .83, 'aurora3': .55}.get(k, .7), 'aver': 1,
            'faces': [face(*f) for f in FACE_ME] if k in ('group', 'falls') else [], 'emb': ev, 'emb_scale': es}).json()
        fids[k] = r.get('faces', [])
    check('GPU 端写回分析结果（描述/标签/人脸/向量）', len(fids['group']) == 1 and len(fids['falls']) == 1)
    burst = f'{TAG}-b1'
    r = P.post('/api/pipe/clusters', {
        'faces': {str(fids['group'][0]): 9001, str(fids['falls'][0]): 9001},
        'bursts': {H['aurora1']: [burst, False], H['aurora2']: [burst, True], H['aurora3']: [burst, False]},
        'moments': {'labels': [{'id': 1, 'title': f'第一晚的极光 {TAG}', 'start': '2026-09-27T22:14', 'end': '2026-09-27T22:20', 'place': '雷克雅未克', 'n': 4, 'memo': 5, 'cover': H['aurora2']},
                               {'id': 2, 'title': '瀑布', 'start': '2026-09-28T13:02', 'end': '2026-09-28T13:02', 'n': 2, 'memo': 3}],
                    'items': {H['aurora1']: 1, H['aurora2']: 1, H['aurora3']: 1, H['vid']: 1, H['falls']: 2, H['group']: 2}},
        'scenes': {'labels': [{'id': 1, 'label': '极光', 'n': 4}], 'items': {H['aurora1']: 1}}}).json()
    check('GPU 端下发聚类（人脸簇/连拍组/时刻/场景）', r.get('ok'))
    lst = A.get('/api/list').json()
    by = {x['h']: x for x in lst['items']}
    check('连拍组：AI 选分最高的那张（aurora2）当封面', by[H['aurora2']]['bc'] == 1 and by[H['aurora1']]['bc'] == 0 and by[H['aurora1']]['b'] == burst)
    check('时刻（moment）标题和归属进了列表', any(m['title'].startswith('第一晚的极光') for m in lst['moments']) and by[H['vid']]['mo'] == 1)
    check('特殊场景标签（极光/合影）进了列表', '极光' in by[H['aurora1']]['tg']['special'] and '合影' in by[H['group']]['tg']['special'])
    check('按设备：两台相机都在', {by[H['aurora1']]['cam'], by[H['falls']]['cam']} == {'Apple iPhone 15 Pro Max', 'SONY ILCE-7M4'})

    # ---------- 挑最好的：人改了封面之后，机器重新聚类也不会改回去 ----------
    r = A.post('/api/pick', {'h': H['aurora3']}).json()
    by = {x['h']: x for x in A.get('/api/list').json()['items']}
    check('手动把 aurora3 设为封面', r.get('ok') and by[H['aurora3']]['bc'] == 1 and by[H['aurora2']]['bc'] == 0 and by[H['aurora3']]['pn'] == 1)
    P.post('/api/pipe/clusters', {'bursts': {H['aurora1']: [burst, False], H['aurora2']: [burst, True], H['aurora3']: [burst, False]}})
    by = {x['h']: x for x in A.get('/api/list').json()['items']}
    check('重新聚类后人挑的封面保持不变', by[H['aurora3']]['bc'] == 1 and by[H['aurora2']]['bc'] == 0)
    check('不在连拍组里的照片不能 pick', 'error' in A.post('/api/pick', {'h': H['falls']}).json())

    # ---------- 人物：认领「这是我」，之后「与我相关」包含别人拍到我的照片 ----------
    ppl = A.get('/api/people').json()
    cl = next((c for c in ppl['clusters'] if c['id'] == 9001), None)
    check('人物页出现待认领的人脸簇（2 张照片）', cl and cl['n'] == 2 and len(cl['faces']) == 2, cl and cl['n'])
    r = B.post('/api/people/claim', {'cluster': 9001, 'me': True}).json()
    pid = r.get('person')
    lst = A.get('/api/list').json(); by = {x['h']: x for x in lst['items']}
    check('乙点「这是我」→ 两张照片都标上乙', pid and pid in by[H['group']]['p'] and pid in by[H['falls']]['p'])
    check('乙成了一个「人物」且关联到账号', any(p['id'] == pid and p['uid'] for p in lst['persons']))
    r = B.post('/api/people/unassign', {'face': fids['falls'][0]})
    by = {x['h']: x for x in A.get('/api/list').json()['items']}
    check('「这张不是我」→ 从那张照片上摘掉', pid not in by[H['falls']]['p'] and pid in by[H['group']]['p'])
    B.post('/api/people/rename', {'person': pid, 'name': UB + '改'})
    check('人物改名', any(p['name'] == UB + '改' for p in A.get('/api/list').json()['persons']))
    # 重新分析同一张照片：人工确认过的脸按位置继承，不会丢
    ev, es = i8vec(vec_o)
    r = P.post('/api/pipe/result', {'h': H['group'], 'faces': [face(.31, .25, .12, .16)], 'emb': ev, 'emb_scale': es}).json()
    by = {x['h']: x for x in A.get('/api/list').json()['items']}
    check('重新分析后已确认的人脸归属保留', pid in by[H['group']]['p'])

    # ---------- 搜索 + 查询缓存 ----------
    r1 = A.get('/api/search', params={'q': '极光'}).json()
    check('关键词搜「极光」命中 3 张照片 + 1 个视频', set(r1['ids']) >= {H['aurora1'], H['aurora2'], H['aurora3'], H['vid']} and H['falls'] not in r1['ids'], f"{len(r1['ids'])} 张, {r1.get('took')} ms")
    r2 = A.get('/api/search', params={'q': '极光 '}).json()
    check('同一个查询第二次 → 命中结果缓存', r2.get('cached') is True, f"{r2.get('took')} ms")
    r = A.get('/api/search', params={'q': 'Waterfall'}).json()
    check('英文别名搜索（Waterfall → 瀑布）', H['falls'] in r['ids'] and len(r['ids']) == 1, f"{[k for k, h in H.items() if h in r['ids']]} sem={r.get('sem')} terms={r.get('terms')}")
    r = A.get('/api/search', params={'q': '极光视频'}).json()
    check('中文无空格自动分词：「极光视频」→ 极光 + 视频', r['ids'][:1] == [H['vid']], r.get('terms'))
    r = A.get('/api/search', params={'q': UB + '改'}).json()
    check('按人名搜', H['group'] in r['ids'])
    r = A.get('/api/search', params={'q': '冰岛'}).json()
    check('按地点搜', len(r['ids']) >= 6)
    r = A.get('/api/search', params={'q': 'sony'}).json()
    check('按相机搜（sony）', set(r['ids']) == {H['falls'], H['group']}, f"{[k for k, h in H.items() if h in r['ids']]} sem={r.get('sem')}")
    newq = f'绿光天空{TAG.lower()}'; RUN['qs'].add(newq)
    r = A.get('/api/search', params={'q': newq}).json()
    check('没见过的词 → 现问 GPU 端要向量，语义搜索命中极光', r.get('sem') is True and r['ids'][:1] and r['ids'][0] in (H['aurora1'], H['aurora2'], H['aurora3'], H['vid']), f"{len(r['ids'])} 张, {r.get('took')} ms")
    n_embed = sum(1 for m in got if m.get('t') == 'embed')
    r = A.get('/api/search', params={'q': newq}).json()
    check('同一个新词第二次：不再问 GPU（向量已永久缓存）', sum(1 for m in got if m.get('t') == 'embed') == n_embed and r.get('cached'))
    s = A.get('/api/suggest').json()
    check('搜索建议词里有「极光」', any(x['t'] == '极光' for x in s))

    # GPU 端下线：关键词搜索照常，没见过的词进队列
    stop.set(); ws.close(); th.join(3); time.sleep(1)
    check('GPU 端断开后列表显示离线', A.get('/api/list').json().get('pipe') is False)
    offq = f'离线词{TAG.lower()}'; RUN['qs'].add(offq)
    r = A.get('/api/search', params={'q': offq}).json()
    check('GPU 离线时搜新词不卡住', r.get('sem') is False and r.get('took', 9999) < 2000, f"{r.get('took')} ms")
    check('没见过的词记进待算队列', offq in P.get('/api/pipe/pending').json()['queries'])
    check('GPU 离线时关键词搜索照常', H['falls'] in A.get('/api/search', params={'q': '瀑布'}).json()['ids'])

    # ---------- 打包下载 ----------
    ids = [H['aurora1'], H['vid'], H['falls']]
    r = A.post('/api/zip', {'ids': ids, 'name': f'{TAG} 极光'}).json()
    t0 = time.time(); z = A.get(r['url'][len('/photos'):]); dt = time.time() - t0
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    names = zf.namelist()
    ok = zf.testzip() is None and len(names) == 3 and hashlib.sha256(zf.read(next(n for n in names if n.endswith('.MOV')))).digest() == hashlib.sha256(vid).digest()
    check('打包下载：zip 能解开、CRC 全对、视频字节一致', ok, f'{len(z.content) / 2**20:.1f} MB · {dt:.1f}s · {names}')
    check('zip 的 content-length 预先算准（浏览器能显示进度）', int(z.headers.get('content-length', 0)) == len(z.content))
    check('过期/伪造的 zip 链接 → 404', A.get('/api/zip/00000000-0000-0000-0000-000000000000/x.zip').status_code == 404)

    # ---------- 撤回：别人也传过的不会被我删掉 ----------
    r = A.post('/api/delete', {'h': H['aurora1']}).json()
    check('甲撤回一张乙也传过的 → 相册里还在', r.get('hidden') is False and any(x['h'] == H['aurora1'] for x in A.get('/api/list').json()['items']))
    r = B.post('/api/delete', {'h': H['aurora1']}).json()
    check('乙也撤回 → 从相册隐藏', r.get('hidden') is True and not any(x['h'] == H['aurora1'] for x in A.get('/api/list').json()['items']))
    check('隐藏后搜不到', H['aurora1'] not in A.get('/api/search', params={'q': '极光'}).json()['ids'])
    h, r, sent = upload(A, 'again.jpg', img['aurora1'])
    check('再传一次同一张 → 秒传并恢复显示', r.get('status') == 'exists' and any(x['h'] == H['aurora1'] for x in A.get('/api/list').json()['items']))

    st = A.get('/api/stats').json()
    print(f"\n统计：{st['items']['c']} 个文件 · 已分析 {st['analyzed']} · 人脸 {st['faces']} · 查询向量 {st['qvecs']} · 结果缓存 {st['rcache']} 条")


def cleanup():
    if not PIPE: return
    P = Client(PIPE)
    r = P.post('/api/pipe/purge', {'hs': sorted(RUN['hs']), 'users': [UA, UB], 'qs': sorted(RUN['qs'])})
    left = Client(); left.login(UA)
    rest = [x for x in left.get('/api/list').json()['items'] if x['h'] in RUN['hs']]
    P.post('/api/pipe/purge', {'users': [UA]})
    check('收尾：测试数据全部删除（行 + R2 字节）', r.status_code == 200 and not rest and P.get(f"/f/{sorted(RUN['hs'])[0]}/t").status_code == 404, r.text[:80])


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
              open(os.path.join(HERE, 'out', f"e2e-{'local' if 'localhost' in BASE else 'prod'}.json"), 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)
