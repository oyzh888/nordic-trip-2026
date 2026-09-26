#!/usr/bin/env python3
"""相册 UI 测试：真浏览器（Chrome）点一遍 —— 登录、真上传（带 EXIF 的 JPEG / H.264 视频 / HEIC）、
四种分组、精选、相似只留最好、搜索、大图里换封面、认人、分析页、选择 + 打包下载、重复上传秒传。
桌面和手机两种尺寸各截一套图到 test/out/ui/。

    python test/ui.py http://localhost:8787
    ALBUM_PASS=… PIPE_TOKEN=… python test/ui.py https://nordic.airacle.com

GPU 端用 /api/pipe/* 模拟（人脸框、连拍组、时刻、特殊场景），这样 UI 测试不依赖 GPU 机在线。
结束时（包括失败）把本轮上传的文件和测试用户彻底删掉。
"""
import io, json, os, random, subprocess, sys, time, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
OUT = os.path.join(e2e.HERE, 'out', 'ui', 'local' if 'localhost' in BASE else 'prod')
FIX = os.path.join(e2e.HERE, 'out', 'fixtures')
TAG = e2e.TAG
U = f'{TAG}-UI'
U2 = f'{TAG}-UI2'
hashes = set()


BAR_JS = """() => { const q = document.querySelector('#q').getBoundingClientRect(),
  f = document.querySelector('#quick').getBoundingClientRect(), s = document.querySelector('#sum').getBoundingClientRect();
  return {qh: Math.round(q.height), fh: Math.round(f.height), gap: Math.round(s.top - f.bottom)}; }"""
def bar_ok(pg):
    # 全站 style.css 有同名类会把筛选区压扁（出过一次：.bar 撞了行程甘特条）→ 量真实几何
    r = pg.evaluate(BAR_JS); return r['qh'] >= 36 and r['fh'] >= 24 and r['gap'] >= 0, r

def rational(x):
    d = int(x); m = int((x - d) * 60); s = round(((x - d) * 60 - m) * 60, 2)
    return (d, m, s)


def make_fixtures():
    """几张「像旅行照片」的合成图：极光连拍 ×3（几乎一样）、瀑布、合影、单反拍的冰川；一段视频；一张 HEIC"""
    from PIL import Image, ImageDraw, ImageFilter
    os.makedirs(FIX, exist_ok=True)
    rnd = random.Random(7)
    out = []

    def save(name, im, make, model, taken, lat, lon):
        ex = Image.Exif()
        ex[0x010F], ex[0x0110] = make, model
        ex.get_ifd(0x8769)[0x9003] = taken
        g = ex.get_ifd(0x8825)
        g[1], g[2], g[3], g[4] = ('N' if lat >= 0 else 'S'), rational(abs(lat)), ('E' if lon >= 0 else 'W'), rational(abs(lon))
        p = os.path.join(FIX, name); im.save(p, 'JPEG', quality=88, exif=ex.tobytes()); out.append(p)

    def aurora(seed, shift):
        im = Image.new('RGB', (1600, 1200), (6, 10, 22)); d = ImageDraw.Draw(im)
        for i in range(260): d.point((rnd.randrange(1600), rnd.randrange(700)), fill=(230, 230, 255))
        for k in range(5):
            y0 = 300 + k * 60 + shift
            d.polygon([(0, y0 + 200), (400, y0 - 80 + k * 20), (900, y0 + 60), (1600, y0 - 150), (1600, y0 + 20), (900, y0 + 220), (0, y0 + 330)],
                      fill=(30 + k * 10, 200 - k * 20, 120 + k * 15))
        im = im.filter(ImageFilter.GaussianBlur(18)); d = ImageDraw.Draw(im)
        d.polygon([(0, 1200), (0, 980), (300, 900), (700, 1010), (1100, 880), (1600, 990), (1600, 1200)], fill=(4, 6, 8))
        d.text((40, 40), f'aurora {seed} {TAG}', fill=(200, 200, 200))
        return im

    for i, sh in enumerate([0, 6, -5]):
        save(f'IMG_40{i + 1}.JPG', aurora(i, sh), 'Apple', 'iPhone 15 Pro Max', f'2026:09:27 22:14:0{5 + i}', 64.2559, -21.1299)
    im = Image.new('RGB', (1200, 1600), (70, 90, 80)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 500], fill=(150, 175, 200)); d.polygon([(0, 500), (1200, 420), (1200, 1600), (0, 1600)], fill=(60, 72, 60))
    d.rectangle([520, 420, 700, 1400], fill=(225, 235, 245)); d.ellipse([380, 1300, 840, 1560], fill=(210, 225, 235))
    save('IMG_410.JPG', im.filter(ImageFilter.GaussianBlur(3)), 'Apple', 'iPhone 15 Pro Max', '2026:09:28 13:02:00', 63.6156, -19.9886)
    im = Image.new('RGB', (1600, 1067), (120, 160, 200)); d = ImageDraw.Draw(im)
    d.rectangle([0, 700, 1600, 1067], fill=(90, 80, 60))
    for j, x in enumerate([330, 640, 950, 1260]):
        d.ellipse([x - 70, 330, x + 70, 510], fill=(224, 186, 150)); d.rectangle([x - 110, 510, x + 110, 900], fill=[(180, 40, 40), (40, 80, 160), (60, 140, 70), (200, 160, 40)][j])
        d.ellipse([x - 35, 390, x - 15, 410], fill=(30, 30, 30)); d.ellipse([x + 15, 390, x + 35, 410], fill=(30, 30, 30))
    save('IMG_411.JPG', im, 'Apple', 'iPhone 15 Pro Max', '2026:09:28 13:10:00', 63.6156, -19.9886)
    im = Image.new('RGB', (2000, 1333), (190, 210, 230)); d = ImageDraw.Draw(im)
    d.polygon([(0, 1333), (0, 700), (500, 520), (1000, 640), (1500, 480), (2000, 620), (2000, 1333)], fill=(170, 215, 235))
    d.polygon([(0, 1333), (0, 1050), (2000, 1000), (2000, 1333)], fill=(50, 60, 70))
    save('DSC09001.JPG', im, 'SONY', 'ILCE-7M4', '2026:09:29 11:30:00', 64.0784, -16.2306)
    v = os.path.join(FIX, 'IMG_420.MOV')
    if not os.path.exists(v):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=size=1280x720:rate=30', '-t', '4',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-metadata', 'creation_time=2026-09-27T22:20:00Z', v], check=True)
    out.append(v)
    import pillow_heif
    hp = os.path.join(FIX, 'IMG_430.HEIC')
    # x265 默认按核数建线程池，192 核的机器上会死锁（不报错，永远不返回）→ 限到 8
    pillow_heif.from_pillow(aurora(9, 12)).save(hp, quality=70, enc_params={'x265:pools': '8'}); out.append(hp)
    return out


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    files = make_fixtures()
    P = Client(e2e.PIPE)
    print(f'UI 测试 {BASE} · {len(files)} 个测试文件 · 截图 → {OUT}\n')

    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        errs = []

        def watch(page, label):
            page.on('pageerror', lambda e: errs.append(f'[{label}] pageerror {e}'))
            # 「Failed to load resource」只是下面 response 事件的重复；那里能看到是哪个请求、才好判断是不是预期的
            page.on('console', lambda m: m.type == 'error' and 'Failed to load resource' not in m.text and errs.append(f'[{label}] console {m.text[:200]}'))
            # 唯一预期的 4xx：没登录时开页面先问一次 /api/me → 401 → 显示登录框
            page.on('response', lambda r: (r.status >= 500 or (r.status >= 400 and not (r.status == 401 and r.url.endswith('/api/me'))))
                    and errs.append(f'[{label}] {r.status} {r.request.method} {r.url}'))

        def shot(page, name, full=False):
            page.wait_for_timeout(350)
            page.screenshot(path=os.path.join(OUT, name + '.png'), full_page=full)

        # ================= 桌面 =================
        ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1, accept_downloads=True, locale='zh-CN')
        pg = ctx.new_page(); watch(pg, 'desktop')
        pg.goto(BASE + '/photos/#k=' + e2e.PASS)
        pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        check('邀请链接 #k= 自动填口令，直接到「你是谁」', pg.is_visible('#name') and '#k=' not in pg.url)
        shot(pg, 'd01-login-name')
        pg.fill('#name', U); pg.click('#f-name button.pri')
        pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        check('登录后进入相册，全站导航也在', pg.is_visible('.tabs') and pg.locator('.nav').count() > 0)
        shot(pg, 'd02-after-login')
        ok, r = bar_ok(pg); check('搜索框和筛选 chip 正常显示（没被全站样式压扁）', ok, r)

        pg.click('#btn-up')
        pg.set_input_files('#file', files)
        t0 = time.time()
        pg.wait_for_function("__album.UQ.length && __album.UQ.every(t => ['ok','dup','failed'].includes(t.state))", timeout=180000)
        dt = time.time() - t0
        st = pg.evaluate("__album.UQ.map(t => [t.f.name, t.state, t.msg, t.h])")
        for _, _, _, h in st: hashes.add(h)
        check(f'真上传 {len(files)} 个文件全部成功', all(s[1] == 'ok' for s in st), f'{dt:.1f}s · ' + '; '.join(f'{s[0]}:{s[1]}' for s in st if s[1] != 'ok'))
        shot(pg, 'd03-upload-sheet')
        pg.click('#up-close')
        pg.evaluate('__album.refresh(true)'); pg.wait_for_timeout(1500)

        lst = P.get('/api/list').json()
        by = {x['n']: x for x in lst['items'] if x['h'] in hashes}
        a1 = by.get('IMG_401.JPG', {})
        check('浏览器读出 EXIF：拍摄时间', a1.get('t') == '2026-09-27T22:14:05', a1.get('t'))
        check('浏览器读出 EXIF：相机型号', a1.get('cam') == 'Apple iPhone 15 Pro Max' and by.get('DSC09001.JPG', {}).get('cam') == 'SONY ILCE-7M4', f"{a1.get('cam')} / {by.get('DSC09001.JPG', {}).get('cam')}")
        check('浏览器读出 EXIF：GPS', a1.get('la') and abs(a1['la'] - 64.2559) < 1e-3 and abs(a1['lo'] + 21.1299) < 1e-3, f"{a1.get('la')},{a1.get('lo')}")
        check('浏览器生成了缩略图（JPEG + 视频）', by['IMG_401.JPG']['f'] & 1 and by['IMG_420.MOV']['f'] & 1, {k: v['f'] for k, v in by.items()})
        check('视频时长和尺寸由浏览器量出', by['IMG_420.MOV'].get('w') == 1280 and abs((by['IMG_420.MOV'].get('d') or 0) - 4) < .2, f"{by['IMG_420.MOV'].get('w')} {by['IMG_420.MOV'].get('d')}")
        check('HEIC 浏览器解不了 → 不报错，等 GPU 端补缩略图', by['IMG_430.HEIC']['f'] & 1 == 0)
        n_img = pg.locator('.tl img').count()
        check('照片墙显示缩略图', n_img >= 5, f'{n_img} 张有图')
        shot(pg, 'd04-grid-before-ai')

        # ---------- 模拟 GPU 端 ----------
        H = {k: v['h'] for k, v in by.items()}
        def face(x, y, w, hh): return {'x': x, 'y': y, 'w': w, 'hh': hh, 'score': .9, 'emb': 'ui'}
        aur = ['IMG_401.JPG', 'IMG_402.JPG', 'IMG_403.JPG', 'IMG_420.MOV', 'IMG_430.HEIC']
        faces = {}
        for n, h in H.items():
            is_a = n in aur
            tags = {'objects': ['极光', '夜空', '星星'] if is_a else ({'IMG_410.JPG': ['瀑布', '草地'], 'IMG_411.JPG': ['合影', '人'], 'DSC09001.JPG': ['冰川', '雪山']}[n]),
                    'en': ['aurora', 'northern lights'] if is_a else ({'IMG_410.JPG': ['waterfall'], 'IMG_411.JPG': ['group photo'], 'DSC09001.JPG': ['glacier']}[n]),
                    'special': ['极光'] if is_a else ({'IMG_411.JPG': ['合影'], 'DSC09001.JPG': ['冰川']}.get(n, [])), 'memo': 5 if is_a else 3}
            place = {'IMG_410.JPG': '塞里雅兰瀑布 · 冰岛', 'IMG_411.JPG': '塞里雅兰瀑布 · 冰岛', 'DSC09001.JPG': '杰古沙龙冰河湖 · 冰岛'}.get(n, '辛格维利尔 · 冰岛')
            fs = [face(.21 - .07, .31, .088, .17), face(.40 - .044, .31, .088, .17), face(.59 - .044, .31, .088, .17), face(.79 - .044, .31, .088, .17)] if n == 'IMG_411.JPG' else []
            r = P.post('/api/pipe/result', {'h': h, 'caption': f'{"夜空里的绿色极光，地平线上是山的剪影" if is_a else n}', 'tags': tags, 'place': place,
                                           'score': {'IMG_401.JPG': .62, 'IMG_402.JPG': .81, 'IMG_403.JPG': .57}.get(n, .7), 'faces': fs, 'aver': 1}).json()
            faces[n] = r['faces']
        fid = faces['IMG_411.JPG']
        bur = f'{TAG}-b'
        P.post('/api/pipe/clusters', {
            'faces': {str(fid[0]): 7001, str(fid[1]): 7002, str(fid[2]): 7003, str(fid[3]): 7004},
            'bursts': {H['IMG_401.JPG']: [bur, False], H['IMG_402.JPG']: [bur, True], H['IMG_403.JPG']: [bur, False]},
            'moments': {'labels': [{'id': 11, 'title': '辛格维利尔的第一场极光', 'start': '2026-09-27T22:14', 'end': '2026-09-27T22:20', 'place': '辛格维利尔', 'n': 5, 'memo': 5, 'cover': H['IMG_402.JPG']},
                                   {'id': 12, 'title': '塞里雅兰瀑布', 'start': '2026-09-28T13:02', 'end': '2026-09-28T13:10', 'place': '塞里雅兰瀑布', 'n': 2, 'memo': 3},
                                   {'id': 13, 'title': '冰河湖', 'start': '2026-09-29T11:30', 'end': '2026-09-29T11:30', 'place': '杰古沙龙', 'n': 1, 'memo': 4}],
                        'items': {**{H[n]: 11 for n in aur}, H['IMG_410.JPG']: 12, H['IMG_411.JPG']: 12, H['DSC09001.JPG']: 13}}})
        # 人物页要 ≥2 张照片才显示一个簇 —— 把瀑布那张也算进 7001，模拟「同一个人出现在两张照片里」
        r = P.post('/api/pipe/result', {'h': H['IMG_410.JPG'], 'faces': [face(.45, .2, .1, .08)]}).json()
        P.post('/api/pipe/clusters', {'faces': {str(r['faces'][0]): 7001}})
        pg.evaluate('__album.refresh(true)'); pg.wait_for_timeout(1200)

        vis = lambda: pg.locator('#grid .tl').count()
        n_col = vis()
        check('「相似只留最好」默认开：3 张连拍只显示 1 张', n_col == len(files) - 2, f'{n_col} 个瓦片')
        cover_shown = pg.locator(f'#grid .tl[data-h="{H["IMG_402.JPG"]}"]').count() == 1 and pg.locator(f'#grid .tl[data-h="{H["IMG_401.JPG"]}"]').count() == 0
        check('显示的是 AI 分最高的那张（IMG_402）', cover_shown)
        check('连拍封面带 ▣3 角标', '3' in (pg.locator(f'#grid .tl[data-h="{H["IMG_402.JPG"]}"] .bd.br').text_content() or ''))
        shot(pg, 'd05-grid-by-day')
        pg.click('#burst'); check('关掉「相似只留最好」→ 全部显示', vis() == len(files)); pg.click('#burst')

        gh = lambda: [x.strip() for x in pg.locator('#grid .gh h3').all_text_contents()]
        pg.click('[data-gp=place]'); g = gh()
        check('按地点分组', any('塞里雅兰' in x for x in g) and any('杰古沙龙' in x for x in g), g); shot(pg, 'd06-by-place')
        pg.click('[data-gp=moment]'); g = gh()
        check('按时刻分组（AI 起的标题）', any('第一场极光' in x for x in g), g); shot(pg, 'd07-by-moment')
        pg.click('[data-gp=cam]'); g = gh()
        check('按设备分组', any('iPhone' in x for x in g) and any('ILCE' in x or 'SONY' in x.upper() for x in g), g); shot(pg, 'd08-by-cam')
        pg.click('[data-gp=day]'); g1 = gh(); pg.click('#order'); g2 = gh()
        check('时间顺序可以反过来', g1 and g1 == g2[::-1], f'{g1} → {g2}'); pg.click('#order')

        pg.click('[data-f=hl]')
        check('★ 精选：只剩极光/合影/冰川这类有纪念意义的', 0 < vis() < len(files) - 1 and pg.locator(f'#grid .tl[data-h="{H["IMG_410.JPG"]}"]').count() == 0, f'{vis()} 张'); shot(pg, 'd09-highlights')
        pg.click('[data-f=all]')
        pg.click('#specials [data-sp="冰川"]')
        check('按特殊场景（冰川）筛', vis() == 1); pg.click('#specials [data-sp="冰川"]')
        pg.locator('#cams [data-cam]').filter(has_text='ILCE').first.click()
        check('按设备 chip 筛（索尼）', vis() == 1); pg.locator('#cams [data-cam]').filter(has_text='ILCE').first.click()

        pg.fill('#q', '极光'); pg.wait_for_function("document.querySelector('#sum').textContent.includes('极光') && !document.querySelector('#sum').textContent.includes('正在找')", timeout=10000)
        check('搜「极光」', vis() >= 3 and pg.locator(f'#grid .tl[data-h="{H["IMG_410.JPG"]}"]').count() == 0, f'{vis()} 张 · {pg.text_content("#sum")[:60]}')
        shot(pg, 'd10-search')
        pg.fill('#q', 'glacier'); pg.wait_for_timeout(1200)
        check('英文也能搜（glacier → 冰川）', vis() == 1)
        pg.fill('#q', ''); pg.wait_for_timeout(700)

        # ---------- 大图 + 换封面 ----------
        pg.click(f'#grid .tl[data-h="{H["IMG_402.JPG"]}"]')
        pg.wait_for_selector('#lb:not([hidden])')
        check('大图里显示这组连拍（3 张，按分数排）', pg.locator('#lb-info .st').count() == 3)
        shot(pg, 'd11-lightbox-burst')
        pg.locator(f'#lb-info .st[data-goto="{H["IMG_403.JPG"]}"]').click(); pg.wait_for_timeout(300)
        pg.click('#lb-pick'); pg.wait_for_timeout(1500)
        bc = {x['h']: x['bc'] for x in P.get('/api/list').json()['items']}
        check('大图里点「这张更好」→ 服务端封面换成 IMG_403', bc[H['IMG_403.JPG']] == 1 and bc[H['IMG_402.JPG']] == 0)
        pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(250); pg.keyboard.press('Escape')
        check('Esc 关掉大图', pg.is_hidden('#lb'))
        check('墙上的连拍封面跟着换了', pg.locator(f'#grid .tl[data-h="{H["IMG_403.JPG"]}"]').count() == 1)
        pg.click(f'#grid .tl[data-h="{H["IMG_420.MOV"]}"]'); pg.wait_for_selector('#lb video', timeout=5000)
        check('视频在大图里能播（<video> 有时长）', pg.wait_for_function("document.querySelector('#lb video').readyState >= 1 && document.querySelector('#lb video').duration > 3", timeout=10000) is not None)
        shot(pg, 'd12-lightbox-video'); pg.keyboard.press('Escape')

        ai_ui(pg, P, H, files, shot)

        # ---------- 人物 ----------
        pg.click('[data-tab=people]'); pg.wait_for_selector('#people .pcard', timeout=8000)
        shot(pg, 'd13-people', full=True)
        pg.locator('#people [data-claim="7001"][data-me]').click(); pg.wait_for_timeout(1500)
        me_pid = next((p['id'] for p in P.get('/api/list').json()['persons'] if p['name'] == U), None)
        check('人物页点「这是我」→ 建立「我」', me_pid is not None)
        pg.click('[data-tab=grid]'); pg.click('[data-f=mine]')
        n_mine = vis()
        check('「⭐ 与我相关」= 我传的 + 拍到我的', n_mine >= 1, f'{n_mine} 张'); pg.click('[data-f=all]')

        # ---------- 分析 ----------
        pg.click('[data-tab=insight]'); pg.wait_for_selector('#insight .stats', timeout=8000)
        check('分析页有统计和分布', pg.locator('#insight .brow').count() >= 4)
        shot(pg, 'd14-insight', full=True)
        pg.click('[data-tab=grid]')

        # ---------- 选择 + 打包下载 ----------
        pg.click('#btn-sel')
        for h in [H['IMG_410.JPG'], H['DSC09001.JPG'], H['IMG_420.MOV']]: pg.click(f'#grid .tl[data-h="{h}"]')
        check('选择模式计数', '3' in pg.text_content('#selcount'))
        shot(pg, 'd15-select')
        with pg.expect_download(timeout=60000) as dl:
            pg.click('#sel-zip')
        zp = os.path.join(OUT, 'download.zip'); dl.value.save_as(zp)
        zf = zipfile.ZipFile(zp)
        want = {os.path.basename(f): open(f, 'rb').read() for f in files}
        ok = zf.testzip() is None and len(zf.namelist()) == 3 and all(zf.read(n) == want[os.path.basename(n)] for n in zf.namelist())
        check('浏览器里点「打包下载」→ zip 完好、字节和原文件一致', ok, zf.namelist())
        pg.click('#sel-x')

        # ---------- 同一个会话里再选一次 → 提示「已经选过了」，不重复排队 ----------
        n0 = pg.evaluate('__album.UQ.length')
        pg.click('#btn-up'); pg.set_input_files('#file', files); pg.wait_for_timeout(500)
        check('同一次打开里重复选同样的文件 → 不重复排队，并提示', pg.evaluate('__album.UQ.length') == n0 and '已经选过' in (pg.text_content('#toast') or ''),
              pg.text_content('#toast'))
        pg.click('#up-close')
        ctx.close()

        # ---------- 另一个人（全新浏览器，没有任何缓存）传同样的文件 → 全部秒传 ----------
        c2 = br.new_context(viewport={'width': 1280, 'height': 800}, locale='zh-CN'); p2 = c2.new_page(); watch(p2, 'desktop2')
        p2.goto(BASE + '/photos/#k=' + e2e.PASS); p2.wait_for_selector('#f-name:not([hidden])')
        p2.fill('#name', U2); p2.click('#f-name button.pri'); p2.wait_for_selector('#app:not([hidden])')
        p2.click('#btn-up'); p2.set_input_files('#file', files)
        p2.wait_for_function("__album.UQ.length && __album.UQ.every(t => ['ok','dup','failed'].includes(t.state))", timeout=60000)
        st2 = p2.evaluate("__album.UQ.map(t => t.state)")
        check('另一个人传同样的文件 → 全部秒传（一个字节都不用再传）', all(s == 'dup' for s in st2), st2)
        shot(p2, 'd16-other-person-dup')
        lst = P.get('/api/list').json(); uid2 = next(u['id'] for u in lst['users'] if u['name'] == U2)
        check('秒传的同时记上「对方也传过」', all(uid2 in x['u'] for x in lst['items'] if x['h'] in hashes))
        c2.close()

        # ================= 手机（iPhone 尺寸） =================
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        mctx = br.new_context(**dev, locale='zh-CN'); m = mctx.new_page(); watch(m, 'mobile')
        m.goto(BASE + '/photos/'); m.wait_for_selector('#f-pass:not([hidden])')
        shot(m, 'm01-gate')
        m.fill('#pass', e2e.PASS); m.click('#f-pass button'); m.wait_for_selector(f'#names [data-n="{U}"]')
        check('手机：已有名字可以一点就选', True)
        m.click(f'#names [data-n="{U}"]'); m.wait_for_selector('#app:not([hidden])'); m.wait_for_timeout(1200)
        cols = m.evaluate("getComputedStyle(document.querySelector('.tiles')).gridTemplateColumns.split(' ').length")
        check('手机：照片墙 3 列', cols == 3, cols)
        ok, r = bar_ok(m); check('手机：搜索框和筛选 chip 正常显示', ok, r)
        top = m.evaluate("document.querySelector('#grid .tl').getBoundingClientRect().top + scrollY")
        check('手机：次要筛选默认收起，第一屏就能看到照片', not m.is_visible('#specials') and top < 844 - 150, f'第一张照片离页顶 {top:.0f}px（屏高 844）')
        m.click('#more-f'); m.wait_for_selector('#specials', state='visible')
        check('手机：点「筛选 ▾」展开按天/人/场景/设备', m.is_visible('#days') and m.is_visible('#cams'))
        shot(m, 'm02b-filters-open')
        m.click('#more-f'); m.wait_for_selector('#specials', state='hidden')
        ow = m.evaluate('document.documentElement.scrollWidth <= innerWidth')
        check('手机：没有横向溢出', ow)
        shot(m, 'm02-grid')
        m.locator(f'#grid .tl[data-h="{H["IMG_403.JPG"]}"]').tap(); m.wait_for_selector('#lb:not([hidden])')
        shot(m, 'm03-lightbox')
        box = m.locator('#lb-media').bounding_box()
        m.touchscreen.tap(box['x'] + 5, box['y'] + 5)
        m.evaluate("""() => { const el = document.querySelector('#lb-media'); const mk = (t, x) => new TouchEvent(t, {bubbles: true, touches: t === 'touchend' ? [] : [new Touch({identifier: 1, target: el, clientX: x, clientY: 300})], changedTouches: [new Touch({identifier: 1, target: el, clientX: x, clientY: 300})]});
                     el.dispatchEvent(mk('touchstart', 320)); el.dispatchEvent(mk('touchmove', 80)); el.dispatchEvent(mk('touchend', 80)); }""")
        m.wait_for_timeout(400)
        check('手机：大图左滑切到下一张', m.evaluate('__album.S.lb') != -1)
        m.keyboard.press('Escape'); m.click('#lb-x') if m.is_visible('#lb-x') else None
        m.click('[data-tab=people]'); m.wait_for_timeout(700); shot(m, 'm04-people', full=True)
        m.click('[data-tab=insight]'); m.wait_for_timeout(700); shot(m, 'm05-insight', full=True)
        m.click('[data-tab=grid]'); m.click('#btn-up'); m.wait_for_timeout(300); shot(m, 'm06-upload-sheet'); m.click('#up-close')
        # 长按进入选择模式
        t = m.locator(f'#grid .tl[data-h="{H["IMG_410.JPG"]}"]'); t.scroll_into_view_if_needed()
        t.evaluate("""el => { const r = el.getBoundingClientRect(), T = new Touch({identifier: 2, target: el, clientX: r.x + 20, clientY: r.y + 20});
                     el.dispatchEvent(new TouchEvent('touchstart', {bubbles: true, cancelable: true, touches: [T], changedTouches: [T]})); }""")
        m.wait_for_timeout(700)
        check('手机：长按进入选择模式', m.is_visible('#selbar'))
        shot(m, 'm07-longpress-select')
        mctx.close()
        br.close()

    real = [e for e in errs if 'favicon' not in e]
    check('整个过程没有 JS 报错、没有意外的 4xx/5xx', not real, real[:5])


ai_hs = set()          # AI 改出来的新照片：单独记（后面「对方也传过」那条只看测试文件本身）


def ai_ui(pg, P, H, files, shot):
    """AI 改图的界面：大图 → ✨ AI 改图 → 预设 / 自己写 → 开始 → 进度 → 自动跳到新照片 → 按住看原图；失败时表单带着原话回来。
    GPU 端在线（线上有常驻 worker）就真改一次；不在线（本地）就自己扮演 GPU 端：连上 WebSocket 报「能用哪些模型」，
    领任务、把原图反色当「改好的图」传回去 —— 测的是界面和服务端的来回，不是模型。"""
    import threading
    import websockets.sync.client as wsc
    from PIL import Image, ImageOps
    real = bool(P.get('/api/list').json().get('ai'))
    src = H['IMG_410.JPG']
    ws, stop = None, threading.Event()
    if not real:
        ws = wsc.connect(BASE.replace('http', 'ws', 1) + '/photos/api/pipe/ws',
                         additional_headers={'authorization': 'Bearer ' + e2e.PIPE}, open_timeout=20)
        ws.send(json.dumps({'t': 'hello', 'edit': ['nano', 'gpt']}))
        im = Image.open(next(f for f in files if f.endswith('IMG_410.JPG'))).convert('RGB')

        def jpg(x, n=None):
            x = x.copy()
            if n: x.thumbnail((n, n))
            b = io.BytesIO(); x.save(b, 'JPEG', quality=85); return b.getvalue()
        P.req('PUT', f'/api/upload/aux?h={src}&k=p', data=jpg(im, 1600), headers={'content-type': 'application/octet-stream'})
        fail_next = []

        def fake_pipe():
            while not stop.is_set():
                try: ws.recv(timeout=0.5)
                except TimeoutError: pass
                except Exception: return
                for eid in P.get('/api/pipe/edits').json():
                    job = P.post('/api/pipe/edit/start', {'id': eid}).json()
                    if job.get('skip'): continue
                    time.sleep(2)                                  # 让页面看得到「正在改…」
                    if fail_next:
                        fail_next.pop(); P.post('/api/pipe/edit/fail', {'id': eid, 'err': '模型因为内容审核没改这张（测试）'}); continue
                    out = ImageOps.invert(im)
                    r = P.req('PUT', f'/api/pipe/edit/out?id={eid}&w={out.width}&hh={out.height}&mid=fake-{job["model"]}',
                              data=jpg(out), headers={'content-type': 'image/jpeg'}).json()
                    for k, n in (('t', 400), ('p', 1600)):
                        P.req('PUT', f'/api/upload/aux?h={r["h"]}&k={k}', data=jpg(out, n), headers={'content-type': 'application/octet-stream'})
        threading.Thread(target=fake_pipe, daemon=True).start()
        t0 = time.time()
        while not P.get('/api/list').json().get('ai') and time.time() - t0 < 10: time.sleep(0.3)
    try:
        pg.evaluate('__album.refresh(true)'); pg.wait_for_timeout(800)
        pg.click(f'#grid .tl[data-h="{src}"]'); pg.wait_for_selector('#lb:not([hidden])')
        check('GPU 端在线 → 大图里出现「✨ AI 改图」', pg.is_visible('#lb-ai'), '真 worker' if real else '模拟 GPU 端')
        pg.click('#lb-ai'); pg.wait_for_selector('#ai-p')
        n_m = pg.locator('input[name="ai-m"]').count()
        check('改图面板：输入框 + 预设 + 服务端报上来的模型', pg.locator('[data-aip]').count() >= 4 and n_m == (len(P.get('/api/list').json()['ai'])), f'{n_m} 个模型')
        pg.locator('[data-aip]').first.click()
        check('点预设 → 填进输入框', pg.input_value('#ai-p') == '把天空换成绚丽的极光')
        shot(pg, 'd12b-ai-panel')
        if not real:                                               # 先走一次失败：表单要带着原话回来，并告诉用户原因
            fail_next.append(1)
            pg.click('#ai-go'); pg.wait_for_selector('#lb-aied .spin', timeout=5000)
            pg.wait_for_selector('#ai-p', timeout=20000)
            check('改图失败 → 提示原因，表单带着原话回来', '内容审核' in (pg.text_content('#toast') or '') and pg.input_value('#ai-p') == '把天空换成绚丽的极光',
                  pg.text_content('#toast'))
        pg.fill('#ai-p', '把天空换成绿色的极光，建筑保持不变')
        pg.click('#ai-go'); pg.wait_for_selector('#lb-aied .spin', timeout=5000)
        check('点「开始改」→ 显示进度', '排队' in pg.text_content('#lb-aied') or '正在改' in pg.text_content('#lb-aied'), pg.text_content('#lb-aied')[:40])
        shot(pg, 'd12c-ai-progress')
        pg.wait_for_function('(() => { const it = __album.S.view[__album.S.lb]; return it && it.src; })()', timeout=120000)
        it = pg.evaluate('__album.S.view[__album.S.lb]')
        ai_hs.add(it['h'])
        check('改好后自动跳到新照片，信息栏写着从哪张改来、用的哪句话',
              it['src'] == src and pg.is_visible('.aisrc') and '把天空换成绿色的极光' in pg.text_content('.aisrc'), pg.text_content('.aisrc')[:60])
        pg.wait_for_timeout(1200); shot(pg, 'd12d-ai-result')
        img = lambda: pg.evaluate("document.querySelector('#lb-media img').src")
        before = img()
        pg.dispatch_event('#lb-cmp', 'pointerdown')
        mid = img()
        pg.evaluate("dispatchEvent(new PointerEvent('pointerup'))")
        check('「按住看原图」按下换成原图、松开换回来', src in mid and it['h'] in before and img() == before, mid[-40:])
        pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
        check('墙上的新照片带 ✨ 角标，原图还在', pg.locator(f'#grid .tl[data-h="{it["h"]}"] .bd.ai').count() == 1 and pg.locator(f'#grid .tl[data-h="{src}"]').count() == 1)
    finally:
        stop.set()
        if ws: ws.close()
    if not real:
        t0 = time.time()
        while P.get('/api/list').json().get('ai') and time.time() - t0 < 10: time.sleep(0.3)
        pg.evaluate('__album.refresh(true)'); pg.wait_for_timeout(500)
        pg.click(f'#grid .tl[data-h="{src}"]'); pg.wait_for_selector('#lb:not([hidden])')
        check('GPU 端下线 → 按钮自动消失', not pg.is_visible('#lb-ai')); pg.keyboard.press('Escape')


def cleanup():
    P = Client(e2e.PIPE)
    r = P.post('/api/pipe/purge', {'hs': sorted(hashes | ai_hs), 'users': [U, U2]})
    check('收尾：UI 测试数据全部删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try:
        main()
    except Exception as ex:
        import traceback; traceback.print_exc()
        check('UI 脚本跑完', False, repr(ex)[:300])
    finally:
        cleanup()
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} 通过 · {time.time() - t0:.0f}s · {BASE}")
    json.dump({'base': BASE, 'results': [{'name': n, 'ok': o, 'detail': str(d)} for n, o, d in results]},
              open(os.path.join(OUT, 'results.json'), 'w'), ensure_ascii=False, indent=1)
    sys.exit(1 if bad else 0)
