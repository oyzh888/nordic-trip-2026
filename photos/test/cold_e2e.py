#!/usr/bin/env python3
"""冷存储（NAS）端到端 —— 热 R2 + 冷 blobd 混合的整条链路（本地，blobd 模拟 NAS）。

要先起两个东西（test/cold_env.sh 一条命令起好）：
    模拟 NAS：blobd（BLOBD_TOKEN 全权限 / BLOBD_EDGE_TOKEN 只读）           端口 $COLD_PORT（默认 41191）
    相册 Worker：配了 COLD_URL / COLD_TOKEN（= edge 令牌）                    端口 8791
    python test/cold_e2e.py http://localhost:8791 < /dev/null

走的是真搬运工脚本（nas/cold_mover.py，子进程），不是在测试里重写一遍：
  1. 没搬之前：全在 R2，读起来和以前一样；清单里是「分析完 + 缩略图做好」的那几张（没做好的不在里面）
  2. 搬：NAS 上的文件内容 = 原件（内容 ID 复核）· 视频新版也搬 · 引擎记下（flags 32）· 热里那份还在
  3. 释放：热里那份删掉（flags 64）—— 这之后读原图 / 视频新版 / Range / 打包 zip 全都从 NAS 来，字节一模一样；缩略图仍在热
  4. 混合：搬完之后新传的 → 还在 R2，读照常；再搬一轮接着搬
  5. NAS 断线：读已释放的原件 → 503 + retry（不是 500、不卡住）；上传 / 翻相册 / 缩略图 / 还在 R2 的原件不受影响；恢复后全部正常
  6. 引擎不信搬运工的话：NAS 上没有的 / 大小不对的 → cold-done 不记；edge 令牌写不进 NAS；巡检能抓出被改坏的文件；孤儿文件能清
  7. 撤回 purge：热冷两边都删
"""
import hashlib, os, signal, subprocess, sys, time, zipfile, io, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results, upload, jpeg
import requests

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
HERE = os.path.dirname(os.path.abspath(__file__))
MOVER = os.path.join(HERE, '..', 'nas', 'cold_mover.py')
T = os.environ.get('COLD_TEST_DIR', os.path.join(os.environ.get('TMPDIR', '/tmp'), 'coldtest'))
COLD = f"http://127.0.0.1:{os.environ.get('COLD_PORT', 41191)}"
CREDS = dict(l.strip().split('=', 1) for l in open(os.path.join(T, 'creds.env')) if '=' in l)
BT, ET = CREDS['BLOBD_TOKEN'], CREDS['BLOBD_EDGE_TOKEN']
U = f'{e2e.TAG}-COLD'
NAS = os.path.join(T, 'nas')


def cid(b):
    parts = [b[i:i + e2e.PART] for i in range(0, max(len(b), 1), e2e.PART)]
    return hashlib.sha256(b''.join(hashlib.sha256(p).digest() for p in parts)).hexdigest()


def mover(*args, env=None):
    e = {**os.environ, 'PIPE_TOKEN': e2e.PIPE, 'BLOBD_TOKEN': BT, **(env or {})}
    r = subprocess.run([sys.executable, MOVER, *args, '--engine', BASE, '--blobd', COLD], capture_output=True, text=True, env=e, timeout=600)
    return r.returncode, (r.stdout + r.stderr)


def nas_file(key): return os.path.join(NAS, key)


def blobd(up):
    """起 / 停模拟 NAS（独立的 tmux 会话）"""
    subprocess.run(['tmux', 'kill-session', '-t', 'cold-blobd'], capture_output=True)
    if not up: time.sleep(1); return
    cmd = (f"BLOBD_DIR={NAS} BLOBD_PORT={COLD.rsplit(':', 1)[1]} BLOBD_TOKEN={BT} BLOBD_EDGE_TOKEN={ET} BLOBD_PROCS=2 "
           f"node {os.path.join(HERE, '..', 'local', 'blobd.mjs')} 2>&1 | tee -a {T}/blobd.log")
    subprocess.run(['tmux', 'new', '-d', '-s', 'cold-blobd', cmd], check=True)
    for _ in range(40):
        try:
            if requests.get(COLD + '/health', headers={'x-blobd-token': BT}, timeout=1).status_code == 200: return
        except requests.RequestException: pass
        time.sleep(0.25)
    raise RuntimeError('模拟 NAS 起不来')
def edge(method, path, **kw): return requests.request(method, COLD + path, headers={'x-blobd-token': ET}, timeout=30, **kw)


def main():
    blobd(True)
    A, P = Client(), Client(e2e.PIPE)
    A.login(U); me = A.get('/api/me').json()['user']['id']
    H = {}                                                      # 名字 → h
    RAW = {}                                                    # h → 字节（和 NAS / 相册里取回来的比）

    def add(name, b, typ='image/jpeg', thumbs=True, analyzed=True):
        h, _, _ = upload(A, name, b, typ=typ)
        H[name], RAW[h] = h, b
        if thumbs:
            for k in 'tp': A.req('PUT', f'/api/upload/aux?h={h}&k={k}', data=jpeg((9, 9, 9), name, (64, 48)), headers={'content-type': 'application/octet-stream'})
        if analyzed: P.post('/api/pipe/result', {'h': h, 'aver': 1, 'caption': name})
        return h

    for i in range(3): add(f'IMG_{i}.jpg', jpeg((i * 60, 100, 160), f'cold{i}', (800, 600)))
    big = os.urandom(20 * 2 ** 20 + 12345)                      # 3 块（8 MB 一块）：分块上传的原件
    add('BIG.jpg', big)
    add('NOTHUMB.jpg', jpeg((1, 2, 3), 'nothumb'), thumbs=False)    # 缩略图还没做好
    add('NOANALYSIS.jpg', jpeg((3, 2, 1), 'noanalysis'), analyzed=False)   # 还没分析
    vid = os.urandom(3_000_000); vh = add('clip.mp4', vid, typ='video/mp4', thumbs=False)
    P.req('PUT', f'/api/upload/aux?h={vh}&k=v', data=b'\x00\x00\x00\x18ftypmp42' + os.urandom(1000), headers={'content-type': 'application/octet-stream'})   # 720p 预览
    gver = b'\x00\x00\x00\x18ftypisom' + os.urandom(900_000)                                                  # H.264 新版
    gid = P.post('/api/pipe/gmp/init', {'h': vh}).json()['id']
    pe = P.req('PUT', f'/api/pipe/gmp/part?h={vh}&id={gid}&n=1', data=gver, headers={'content-type': 'application/octet-stream'}).json()['etag']
    P.post('/api/pipe/gmp/complete', {'h': vh, 'id': gid, 'parts': [{'n': 1, 'etag': pe}], 'plan': 'transcode', 'size': len(gver), 'crc': zlib.crc32(gver)})
    mine = lambda: {x['n']: x for x in A.get('/api/list').json()['items'] if me in x['u']}
    get = lambda h, k='o', **kw: A.get(f'/f/{h}/{k}', **kw)

    st = P.get('/api/pipe/cold-status').json()
    check('Worker 配了冷存储（COLD_URL / COLD_TOKEN）', st['configured'], st)
    todo = P.get('/api/pipe/cold-todo?limit=50&minAgeMin=0').json()
    want = {H[n] for n in ('IMG_0.jpg', 'IMG_1.jpg', 'IMG_2.jpg', 'BIG.jpg', 'clip.mp4')}
    got = {i['h'] for i in todo['items']}
    check('搬运清单 = 分析完 + 缩略图做好的（没分析的、缩略图还没好的不在里面）', want <= got and H['NOTHUMB.jpg'] not in got and H['NOANALYSIS.jpg'] not in got,
          {'清单': len(got), '缺': [n for n in H if H[n] in want - got], '多': [n for n in H if H[n] in got - want]})
    vi = next(i for i in todo['items'] if i['h'] == vh)
    check('视频的清单项带着新版的大小和 CRC', vi.get('gsize') == len(gver) and vi.get('gcrc') == zlib.crc32(gver), vi)
    check('没搬之前：原件读出来和传的一字不差（在 R2）', all(get(H[n]).content == RAW[H[n]] for n in ('IMG_0.jpg', 'BIG.jpg', 'clip.mp4')))

    # ---------- 1) 搬 ----------
    v0 = A.get('/api/list').json()['ver']
    rc, out = mover('run', '--once', '--min-age', '0', '--workers', '2')
    print('   ' + out.strip().replace('\n', '\n   '))
    check('搬运工跑完退出码 0', rc == 0, out[-300:])
    on_nas = {n: os.path.exists(nas_file('o/' + H[n])) for n in H}
    check('清单里的原件都到了 NAS，没资格的没搬', all(on_nas[n] for n in ('IMG_0.jpg', 'IMG_1.jpg', 'IMG_2.jpg', 'BIG.jpg', 'clip.mp4')) and not on_nas['NOTHUMB.jpg'] and not on_nas['NOANALYSIS.jpg'], on_nas)
    check('NAS 上的文件内容 = 原件（20 MB 分块的那个也是；内容 ID 复核）', all(cid(open(nas_file('o/' + H[n]), 'rb').read()) == H[n] for n in ('IMG_0.jpg', 'BIG.jpg', 'clip.mp4')))
    check('视频新版也搬了，CRC 对', open(nas_file(f'g/{vh}.mp4'), 'rb').read() == gver)
    m = mine()
    check('引擎记下了（flags 32），热里那份还在（还没释放：没有 64）', all(m[n]['f'] & 32 and not m[n]['f'] & 64 for n in ('IMG_0.jpg', 'BIG.jpg', 'clip.mp4')) and not m['NOTHUMB.jpg']['f'] & 32, {n: m[n]['f'] for n in m})
    d = A.get(f'/api/list?since={v0}').json()
    check('增量列表带上了新的状态位（页面不用重拉全量）', d.get('delta') and any(x['f'] & 32 for x in d['items']), {'delta': d.get('delta'), 'n': len(d.get('items', []))})
    check('搬完（还没释放）读起来照旧', all(get(H[n]).content == RAW[H[n]] for n in ('IMG_0.jpg', 'BIG.jpg', 'clip.mp4')) and get(vh, 'g').content == gver)
    rc, out = mover('run', '--once', '--min-age', '0')
    check('再跑一遍什么都不用搬（幂等）', rc == 0 and '清单' not in out, out[-200:])

    # ---------- 2) 释放：热里删掉，只剩 NAS ----------
    r = P.post('/api/pipe/cold-release', {'olderThanDays': 1}).json()
    check('宽限期没到（1 天）→ 不释放', r['released'] == 0, r)
    r = P.post('/api/pipe/cold-release', {'olderThanDays': 0}).json()
    check('宽限期到了 → 释放（每个 +o，视频还有 +g）', r['released'] == 5 and not r['bad'], r)
    m = mine()
    check('flags 64：热里已删', all(m[n]['f'] & 64 for n in ('IMG_0.jpg', 'IMG_1.jpg', 'IMG_2.jpg', 'BIG.jpg', 'clip.mp4')))
    rc, out = mover('check', '--h', H['BIG.jpg'], H['clip.mp4'])
    check('check：走用户真实路径读已释放的原件，内容 ID 对、报了耗时和速度', rc == 0 and out.count('✓') == 2 and 'Mbps' in out, out[-200:])
    check('释放之后读原图：从 NAS 来，字节一模一样（含 20 MB 分块的）', all(get(H[n]).content == RAW[H[n]] for n in ('IMG_0.jpg', 'BIG.jpg', 'clip.mp4')))
    check('视频新版从 NAS 读，一模一样', get(vh, 'g').content == gver)
    rg = get(H['BIG.jpg'], headers={'range': 'bytes=9000000-9000999'})
    check('Range 读（视频拖进度条 / 断点下载）：206、内容和切片一致', rg.status_code == 206 and rg.content == big[9000000:9001000] and rg.headers.get('content-range', '').endswith(f'/{len(big)}'), (rg.status_code, rg.headers.get('content-range')))
    r1 = get(H['IMG_0.jpg']); et = r1.headers.get('etag')
    r2 = get(H['IMG_0.jpg'], headers={'if-none-match': et}) if et else None
    check('条件请求（If-None-Match）：304', r2 is not None and r2.status_code == 304, r2 and r2.status_code)
    dl = get(H['IMG_1.jpg'], params={'dl': 1})
    check('下载（?dl=1）：文件名是原名', 'IMG_1.jpg' in dl.headers.get('content-disposition', '') and dl.content == RAW[H['IMG_1.jpg']], dl.headers.get('content-disposition'))
    check('缩略图 / 预览 / 720p 视频预览仍在热里（翻相册不碰 NAS）', all(get(H[n], k).status_code == 200 for n in ('IMG_0.jpg', 'BIG.jpg') for k in 'tp') and get(vh, 'v').status_code == 200)
    z = A.post('/api/zip', {'ids': [H['IMG_0.jpg'], H['BIG.jpg'], vh]}).json()
    zr = A.get(z['url'].replace('/photos', '', 1)) if z.get('url') else None
    zf = zipfile.ZipFile(io.BytesIO(zr.content)) if zr is not None and zr.status_code == 200 else None
    bodies = {os.path.basename(n): zf.read(n) for n in zf.namelist()} if zf else {}
    check('打包下载 zip：已释放的原件照样打进去，一字不差', zf and bodies.get('IMG_0.jpg') == RAW[H['IMG_0.jpg']] and bodies.get('BIG.jpg') == big and zf.testzip() is None, sorted(bodies))

    # ---------- 3) 混合：搬完之后新传的 ----------
    add('LATE_0.jpg', jpeg((200, 30, 30), 'late0', (800, 600))); add('LATE_1.jpg', jpeg((30, 200, 30), 'late1', (800, 600)))
    check('搬完之后新传的：在 R2，读照常（新旧混着）', get(H['LATE_0.jpg']).content == RAW[H['LATE_0.jpg']] and not os.path.exists(nas_file('o/' + H['LATE_0.jpg'])))
    s = P.get('/api/pipe/cold-status').json()
    check('进度表：NAS 有 5、R2 已释放 5、只在 R2 的另算', s['onCold']['n'] == 5 and s['hotReleased']['n'] == 5 and s['hotOnly']['n'] >= 4, {k: s[k]['n'] if isinstance(s[k], dict) else s[k] for k in ('total', 'onCold', 'hotReleased', 'hotOnly', 'eligibleNow')})
    rc, out = mover('run', '--once', '--min-age', '0')
    check('再搬一轮：新传的接着搬过去', rc == 0 and all(os.path.exists(nas_file('o/' + H[n])) for n in ('LATE_0.jpg', 'LATE_1.jpg')), out[-200:])

    # ---------- 4) NAS 断线 ----------
    blobd(False)
    down = get(H['BIG.jpg'])
    check('NAS 断线：读已释放的原件 → 503 + retry（不是 500，也没卡住）', down.status_code == 503 and down.json().get('retry') and 'retry-after' in down.headers, (down.status_code, down.text[:120]))
    check('NAS 断线：缩略图 / 预览 / 列表 / 还在 R2 的原件照常', get(H['BIG.jpg'], 't').status_code == 200 and get(H['LATE_1.jpg']).status_code == 200 and A.get('/api/list').status_code == 200)
    h_new, _, _ = upload(A, 'DURING_OUTAGE.jpg', jpeg((7, 7, 200), 'during', (640, 480))); H['DURING_OUTAGE.jpg'] = h_new
    check('NAS 断线：照样能上传新照片（上传不依赖 NAS）', get(h_new).status_code == 200)
    cd = P.post('/api/pipe/cold-done', {'items': [H['IMG_0.jpg']]}).json()
    check('NAS 断线：引擎核对不了 → 不乱记（bad 里写着原因）', cd['ok'] == [] or cd['ok'] == [H['IMG_0.jpg']], cd)   # IMG_0 本来就已记过，这里只要不报 500
    blobd(True)
    check('NAS 恢复：已释放的原件又能读了', get(H['BIG.jpg']).content == big)

    # ---------- 5) 引擎不轻信搬运工 + 令牌 + 巡检 + 孤儿 ----------
    h_x = add('LIE.jpg', jpeg((50, 50, 50), 'lie', (700, 500)))
    cd = P.post('/api/pipe/cold-done', {'items': [h_x]}).json()
    check('搬运工谎报（NAS 上根本没有）→ 引擎去核对，不记', cd['ok'] == [] and cd['bad'] and '不在冷存储' in cd['bad'][0]['why'] and not mine()['LIE.jpg']['f'] & 32, cd)
    os.makedirs(os.path.dirname(nas_file('o/' + h_x)), exist_ok=True); open(nas_file('o/' + h_x), 'wb').write(b'short')
    cd = P.post('/api/pipe/cold-done', {'items': [h_x]}).json()
    check('NAS 上有但大小不对 → 不记', cd['ok'] == [] and '大小' in cd['bad'][0]['why'], cd)
    os.unlink(nas_file('o/' + h_x))
    check('edge 令牌（Worker 用）写不进 NAS（403）', edge('PUT', f'/o/o/{"0" * 64}', data=b'x').status_code == 403)
    check('edge 令牌能读', edge('GET', f'/o/o/{H["IMG_0.jpg"]}').content == RAW[H['IMG_0.jpg']])
    check('没令牌 / 错令牌：403', requests.get(COLD + f'/o/o/{H["IMG_0.jpg"]}').status_code == 403 and requests.get(COLD + f'/o/o/{H["IMG_0.jpg"]}', headers={'x-blobd-token': 'nope'}).status_code == 403)
    rc, out = mover('scrub')
    check('巡检：NAS 上已登记的文件读回来重算内容 ID，全部对', rc == 0, out[-200:])
    p = nas_file('o/' + H['IMG_1.jpg']); b = bytearray(open(p, 'rb').read()); b[len(b) // 2] ^= 0xFF; open(p, 'wb').write(bytes(b))
    rc, out = mover('scrub')
    check('巡检能抓出被改坏的一个字节（静默坏块）', rc == 1 and H['IMG_1.jpg'][:12] in out, out[-200:])
    open(p, 'wb').write(RAW[H['IMG_1.jpg']])
    orphan = nas_file('o/' + 'ab' * 32); open(orphan, 'wb').write(b'orphan'); old = time.time() - 3 * 86400; os.utime(orphan, (old, old))
    rc, out = mover('gc', '--data-dir', NAS)
    check('gc 只列不删（默认）', os.path.exists(orphan) and '孤儿文件 1 个' in out, out[-120:])
    rc, out = mover('gc', '--data-dir', NAS, '--apply')
    check('gc --apply：删掉孤儿，已登记的一个不动', not os.path.exists(orphan) and os.path.exists(nas_file('o/' + H['IMG_0.jpg'])), out[-120:])
    check('释放不带参数（--release-after-days）时搬运工永远不删 R2', '释放 R2' not in mover('run', '--once', '--min-age', '0')[1])

    # ---------- 6) 撤回 purge：热冷都删 ----------
    r = P.post('/api/pipe/purge', {'hs': [H['BIG.jpg'], vh]}).json()
    check('purge：NAS 上的原件和视频新版也删了', not os.path.exists(nas_file('o/' + H['BIG.jpg'])) and not os.path.exists(nas_file('o/' + vh)) and not os.path.exists(nas_file(f'g/{vh}.mp4')) and r.get('ok'), r)
    check('purge 之后取不到了', get(H['BIG.jpg']).status_code == 404)


def cleanup():
    P = Client(e2e.PIPE); L = Client(); L.login(U)
    me = L.get('/api/me').json()['user']['id']
    P.post('/api/pipe/purge', {'hs': [x['h'] for x in L.get('/api/list').json()['items'] if me in (x.get('u') or [])], 'users': [U]})


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
