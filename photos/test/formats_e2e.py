#!/usr/bin/env python3
"""各种格式 + Live Photo 的端到端测试：真文件 → 本地相册 → 真 GPU 端（worker.py 子进程）→ 查结果。

    python test/formats_e2e.py http://localhost:8787

格式：HEIC / AVIF / WebP / PNG / TIFF / GIF（从测试集的风景照转出来，带 EXIF 时间 + GPS），
相机 RAW（CR3 / CR2 / ARW / DNG / NEF，raw.pixls.us 和 rawpy 测试集的样张，放在 localssd 上不进仓库）。
Live Photo 三组：
  A  HEIC（MakerNote 里写配对 ID）+ 名字不一样的 MOV（QuickTime 里写同一个 ID）→ 必须按 ID 配上
  B  JPEG + 同名 MOV，都没有 ID，拍摄时间差 1 秒、视频 3 秒 → 按「同名 + 时间」配上
  C  JPEG + 同名 MOV，但视频 8 秒、时间差 1 分钟 → 不能配（是两个独立的文件）
上传时不带浏览器端读出的任何元数据 —— 全部要靠 GPU 端读出来。结束时把本轮文件和用户删掉。
"""
import io, os, struct, subprocess, sys, time, uuid, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results, upload
import pipe_e2e as PE

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
SRC = os.path.join(PE.SET, 'src')
RAW = os.environ.get('PHOTOS_RAWSET', '/mnt/localssd/photos-cache/rawtest')
OUT = os.path.join(e2e.HERE, 'out', 'formats')
LOG = os.path.join(e2e.HERE, 'out', 'formats-worker.log')
U = f'{e2e.TAG}-FMT'
# 这台机 192 核、容器只给 21 核：x265 按 192 核开线程池会直接卡死，限一下（只影响造测试图，GPU 端不编 HEIC）
HEIF_KW = {'enc_params': {'x265:pools': '4', 'x265:frame-threads': '1'}}


def rational(x):
    d = int(x); m = int((x - d) * 60); s = round(((x - d) * 60 - m) * 60, 2)
    return (d, m, s)


def apple_makernote(cid):
    """最小的 Apple MakerNote：'Apple iOS\\0' + 版本 1 + 'MM' + 一个 IFD，只有 tag 0x11（Live Photo 配对 ID）"""
    v = cid.encode() + b'\0'
    off = 16 + 12 + 4
    return b'Apple iOS\0' + b'\x00\x01' + b'MM' + struct.pack('>H', 1) + struct.pack('>HHII', 0x11, 2, len(v), off) + b'\0\0\0\0' + v


def exif(taken, lat=None, lon=None, make='Apple', model='iPhone 15 Pro Max', cid=None, off=None):
    from PIL import Image
    ex = Image.Exif()
    ex[0x010F], ex[0x0110] = make, model
    sub = ex.get_ifd(0x8769)
    sub[0x9003] = taken
    if off: sub[0x9011] = off
    if cid: sub[0x927C] = apple_makernote(cid)
    if lat is not None:
        g = ex.get_ifd(0x8825)
        g[1], g[2], g[3], g[4] = ('N' if lat >= 0 else 'S'), rational(abs(lat)), ('E' if lon >= 0 else 'W'), rational(abs(lon))
    return ex.tobytes()


def mov(path, src, secs, created, cid=None):
    md = ['-metadata', f'com.apple.quicktime.creationdate={created}', '-metadata', 'com.apple.quicktime.make=Apple',
          '-metadata', 'com.apple.quicktime.model=iPhone 15 Pro Max']
    if cid: md += ['-metadata', f'com.apple.quicktime.content.identifier={cid}']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', src, '-t', str(secs), '-r', '30', '-vf', 'scale=1440:-2,format=yuv420p',
                    '-c:v', 'libx265', '-x265-params', 'pools=4:frame-threads=1:log-level=error', '-tag:v', 'hvc1', *md, '-movflags', 'use_metadata_tags', '-f', 'mov', path], check=True)


def fixtures():
    from PIL import Image
    import pillow_heif
    pillow_heif.register_heif_opener()
    os.makedirs(OUT, exist_ok=True)
    im = lambda n: Image.open(os.path.join(SRC, n)).convert('RGB')
    F = {}                                  # 文件名 → (路径, 期望)
    REYK = (64.1417, -21.9266)
    for name, src, fmt, kw in [
        ('IMG_6001.HEIC', 'hallgrims.jpg', 'HEIF', {}), ('IMG_6002.avif', 'puffin.jpg', 'AVIF', {}),
        ('IMG_6003.webp', 'natas.jpg', 'WEBP', {'quality': 85}), ('IMG_6004.png', 'tram28.jpg', 'PNG', {}),
        ('IMG_6005.tif', 'reynisfjara.jpg', 'TIFF', {}), ('IMG_6006.gif', 'skogafoss.jpg', 'GIF', {}),
    ]:
        p = os.path.join(OUT, name); x = im(src)
        if fmt == 'GIF': x = x.resize((800, 600)).quantize(128)
        x.save(p, fmt, exif=exif('2026:09:26 15:0%d:00' % len(F), *REYK), **{**kw, **HEIF_KW} if fmt == 'HEIF' else kw)
        # GIF 格式本身没有 EXIF（写不进去），只验能解码；时间退回上传时浏览器给的
        F[name] = (p, {'taken': '2026-09-26T15:0%d:00' % len(F), 'gps': True} if fmt != 'GIF' else {})
    # DNG 拍在美国佐治亚（东部时间，冬令时 UTC−5）：相机记 14:24 −05:00 → 时间线也要是 14:24，不能按「美国」一个时区算
    for name, exp in [('R5.CR3', 'Canon EOS R5'), ('RAW_CANON_40D_SRAW_V103.CR2', 'Canon EOS 40D'), ('a7m4.ARW', 'SONY ILCE-7M4'),
                      ('ip12.DNG', 'Apple iPhone 12 Pro'), ('iss030e122639.NEF', 'NIKON D3S')]:
        if os.path.exists(os.path.join(RAW, name)): F[name] = (os.path.join(RAW, name), {'cam': exp, 'gps': name == 'ip12.DNG', **({'taken': '2020-12-29T14:24:45'} if name == 'ip12.DNG' else {})})
    # Live Photo
    cid = str(uuid.uuid4()).upper()
    p = os.path.join(OUT, 'IMG_7001.HEIC'); im('aurora1.jpg').save(p, 'HEIF', **HEIF_KW, exif=exif('2026:09:27 22:14:05', 64.2559, -21.1299, cid=cid))
    F['IMG_7001.HEIC'] = (p, {'live': 'A'})
    p = os.path.join(OUT, 'LIVE_A.MOV'); mov(p, os.path.join(SRC, 'aurora1.jpg'), 3, '2026-09-27T22:14:05+0000', cid); F['LIVE_A.MOV'] = (p, {'live': 'A'})
    p = os.path.join(OUT, 'IMG_7002.JPG'); im('jokulsarlon1.jpg').save(p, 'JPEG', exif=exif('2026:09:28 11:30:00', 64.0784, -16.2306)); F['IMG_7002.JPG'] = (p, {'live': 'B'})
    p = os.path.join(OUT, 'IMG_7002.MOV'); mov(p, os.path.join(SRC, 'jokulsarlon1.jpg'), 3, '2026-09-28T11:30:01+0000'); F['IMG_7002.MOV'] = (p, {'live': 'B'})
    p = os.path.join(OUT, 'IMG_7003.JPG'); im('jokulsarlon2.jpg').save(p, 'JPEG', exif=exif('2026:09:28 11:40:00', 64.0784, -16.2306)); F['IMG_7003.JPG'] = (p, {'live': 'C'})
    p = os.path.join(OUT, 'IMG_7003.MOV'); mov(p, os.path.join(SRC, 'jokulsarlon2.jpg'), 8, '2026-09-28T11:41:00+0000'); F['IMG_7003.MOV'] = (p, {'live': 'C'})
    return F, cid


def wait_done(A, P, hs, timeout=900):
    """和 pipe_e2e 的一样，只是配上对的 Live 视频不在列表里 —— 挂在照片的 lv 上也算分析完了"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        items = A.get('/api/list').json()['items']
        done = {x['h'] for x in items if x.get('a')} | {x['lv'] for x in items if x.get('lv')}
        pend = [h for h in hs if h not in done]
        if not pend:
            st = P.get('/api/pipe/status').json()
            if st['cl'] > st['res']:
                return time.time() - t0
        time.sleep(3)
    raise TimeoutError(f'{len(pend)} 个还没分析完')


def live_ui(h):
    """真浏览器（手机尺寸）：缩略图上有 LIVE 角标；点开先动一遍、播完停回照片；按住 LIVE 再动"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        pg = br.new_context(**dev, locale='zh-CN').new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        tl = pg.locator(f'#grid .tl[data-h="{h}"]'); tl.wait_for(timeout=10000)
        check('缩略图上有 ◉ LIVE 角标', tl.locator('.bd.lv').count() == 1)
        tl.click(); pg.wait_for_selector('#lb .live video', timeout=8000)
        played = pg.wait_for_function("() => document.querySelector('#lb .live').classList.contains('play') && document.querySelector('#lb .live video').currentTime > 0.3", timeout=10000)
        pg.screenshot(path=os.path.join(OUT, 'live-playing.png'))
        pg.wait_for_function("() => !document.querySelector('#lb .live').classList.contains('play')", timeout=10000)
        check('点开 Live Photo → 先动一遍，播完停回照片', bool(played))
        b = pg.locator('#lb .livebtn').bounding_box()
        pg.mouse.move(b['x'] + 5, b['y'] + 5); pg.mouse.down(); pg.wait_for_timeout(700)
        again = pg.evaluate("() => document.querySelector('#lb .live').classList.contains('play')")
        pg.mouse.up()
        check('按住「◉ LIVE」再看一遍，松手停', again and not pg.evaluate("() => document.querySelector('#lb .live').classList.contains('play')"))
        check('大图里有「⬇ Live 视频」下载', pg.locator('#lb-info a', has_text='Live 视频').count() == 1)
        check('Live Photo 页面没有 JS 报错', not errs, errs[:2])
        br.close()


def main():
    A, P = Client(), Client(e2e.PIPE)
    A.login(U)
    F, cid = fixtures()
    print(f'格式测试 {BASE} · {len(F)} 个文件（{sum(os.path.getsize(p) for p, _ in F.values()) / 2**20:.0f} MB）\n')
    H = {}
    for name, (p, _) in F.items():
        typ = 'video/quicktime' if name.endswith('.MOV') else ''
        h, r, _ = upload(A, name, open(p, 'rb').read(), typ=typ)
        H[name] = h
    check('全部上传完成', len(H) == len(F))
    PE.LOG = LOG
    worker = subprocess.Popen([PE.PY, PE.WORKER, '--base', BASE, '--no-edit', '--no-vlm'], stdout=open(LOG, 'w'), stderr=subprocess.STDOUT,
                              env={**os.environ, 'PYTHONWARNINGS': 'ignore'})
    try:
        dt = wait_done(A, P, list(H.values()))
        time.sleep(4)                                   # 配对后会推 recluster，等聚类落地
        check('GPU 端全部处理完', True, f'{dt:.0f}s')
    finally:
        worker.terminate()
        try: worker.wait(20)
        except subprocess.TimeoutExpired: worker.kill()

    I = {x['h']: x for x in A.get('/api/list').json()['items']}
    M = {x['h']: x for x in P.get('/api/pipe/media').json()}
    for name, (p, exp) in F.items():
        if exp.get('live'): continue
        x = I.get(H[name]); m = M.get(H[name]) or {}
        ok = x and x['f'] & 3 == 3 and x.get('w')
        ok = ok and (exp.get('taken') is None or x['t'] == exp['taken']) and (exp.get('cam') is None or x['cam'] == exp['cam'])
        ok = ok and (not exp.get('gps') or m.get('lat') is not None)
        check(f'{name}：解码出缩略图 + 预览，读出拍摄时间 / 相机{" / GPS" if exp.get("gps") else ""}', ok,
              x and f"{x.get('w')}×{x.get('hh')} · {x['t']} · {x.get('cam')} · gps={m.get('lat') is not None} · f={x['f']}")
    a, av = I.get(H['IMG_7001.HEIC']), H['LIVE_A.MOV']
    check('Live Photo A（HEIC + 名字不同的 MOV，同一个配对 ID）→ 配成一张', a and a.get('lv') == av and av not in I, a and a.get('lv'))
    b, bv = I.get(H['IMG_7002.JPG']), H['IMG_7002.MOV']
    check('Live Photo B（没有 ID：同名 + 时间差 1 秒 + 3 秒视频）→ 配成一张', b and b.get('lv') == bv and bv not in I, b and b.get('lv'))
    c, cv = I.get(H['IMG_7003.JPG']), H['IMG_7003.MOV']
    check('C（同名但视频 8 秒、差 1 分钟）→ 不配，两个都单独在', c and not c.get('lv') and cv in I)
    check('Live 视频不进聚类 / 搜索（GPU 端看到的列表里没有它）', av not in M and bv not in M and cv in M)
    check('Live 视频没有单独的人脸和向量', not any(f['h'] in (av, bv) for f in P.get('/api/pipe/faces').json())
          and not any(e['h'] in (av, bv) for e in P.get('/api/pipe/embs').json()))
    live_ui(H['IMG_7001.HEIC'])
    r = A.post('/api/zip', {'ids': [H['IMG_7001.HEIC']]}).json()
    z = zipfile.ZipFile(io.BytesIO(A.get(r['url'].replace('/photos', '', 1)).content))
    names = sorted(os.path.basename(n) for n in z.namelist())
    check('打包下载 Live Photo → 照片和视频都在包里', names == ['IMG_7001.HEIC', 'LIVE_A.MOV'], names)
    A.post('/api/delete', {'h': H['IMG_7002.JPG']})
    # 预查只认「没删的」，正好用来看视频是不是也被撤了
    r = A.post('/api/upload/probe', {'items': [['IMG_7002.JPG', os.path.getsize(F['IMG_7002.JPG'][0])], ['IMG_7002.MOV', os.path.getsize(F['IMG_7002.MOV'][0])],
                                               ['LIVE_A.MOV', os.path.getsize(F['LIVE_A.MOV'][0])]]}).json()
    check('撤回 Live Photo → 视频跟着一起撤（另一张不受影响）', r.get('hit') == [2], r)
    PE_H.update(H)


PE_H = {}


def cleanup():
    P = Client(e2e.PIPE)
    r = P.post('/api/pipe/purge', {'hs': sorted(PE_H.values()), 'users': [U]})
    check('收尾：测试文件和用户全部删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
