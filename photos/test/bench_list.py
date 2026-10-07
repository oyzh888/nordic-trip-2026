#!/usr/bin/env python3
"""「存储优先」压测（本地）：相册有 N 张（默认 14,000，和线上现在一样多）时，
有人开着页面、GPU 端在不停写分析结果 —— 这时候上传一张照片的握手要等多久。

两种轮询方式各跑一遍，别的都一样：
  全量：老页面那样，每次轮询拉整份列表（版本号一变就是 9 MB 重拼 + 重下）
  增量：新页面，?since=<手上的版本>，只拿变过的那几张

    python test/bench_list.py http://localhost:8787 [N=14000] [看相册的人=5] < /dev/null

数据是合成的（标签 / 描述的长度照线上真实分布），结束时全部删掉。只在本地跑。
"""
import json, os, random, statistics as st, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 14000
VIEWERS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
POLL = 1.5          # 真页面 15 秒一次；压测压缩 10 倍，让几十秒里出现足够多次
U = f'{e2e.TAG}-BENCH'
HS = [f'{random.randrange(16 ** 60):060x}beef' for _ in range(N)]
OBJ = ['山', '湖', '天空', '云', '岩石', '草地', '雪', '海', '船', '房子', '路', '人', '树', '桥', '灯塔', '瀑布']


def tags(rnd):
    o = rnd.sample(OBJ, 6)
    return {'objects': o, 'scene': rnd.sample(['户外', '自然', '城市', '海边', '夜景'], 2), 'en': [f'thing{k}' for k in range(6)],
            'alias': [], 'special': [], 'memo': rnd.randrange(1, 5)}


def seed(P):
    rnd = random.Random(7)
    for i in range(0, N, 500):
        P.post('/api/pipe/import', {'items': [{'h': h, 'size': 3_000_000 + j, 'type': 'image/jpeg', 'name': f'BENCH_{i + j:05d}.jpg',
                                                'created': 1790000000000 + i + j, 'flags': 3} for j, h in enumerate(HS[i:i + 500])]})
    for i in range(0, N, 200):
        P.post('/api/pipe/results', {'items': [{'h': h, 'aver': 1, 'taken': f'2026-09-{25 + (i + j) % 6:02d}T1{(i + j) % 10}:00:00',
                                                 'caption': '海边日落时分，山峦剪影映衬着金色云霞，海面平静如镜，宁静而壮美。', 'tags': tags(rnd),
                                                 'cam': 'Canon EOS R6', 'score': rnd.random(), 'w': 6000, 'hh': 4000, 'lat': 64.1, 'lon': -21.9}
                                                for j, h in enumerate(HS[i:i + 200])]})


def run(mode, secs=25):
    stop = threading.Event()
    polls = {'n': 0, 'bytes': 0, 'ms': []}

    def gpu():                       # GPU 端：每 0.8 秒写回一批 8 张的结果（真机大约每 3 秒一张）
        P = Client(e2e.PIPE); k = 0
        while not stop.is_set():
            P.post('/api/pipe/results', {'items': [{'h': HS[(k * 8 + j) % N], 'aver': 1, 'score': random.random()} for j in range(8)]})
            k += 1; time.sleep(0.8)

    def viewer():
        c = Client(); c.cookie = A.cookie
        ver = c.get('/api/list' + ('?stale=1' if mode == 'delta' else '')).json()['ver']   # 第一次打开都要拿全量，不计入
        time.sleep(random.random() * POLL)
        while not stop.is_set():
            q = f'?since={ver}' if mode == 'delta' else ''
            t = time.time(); r = c.get('/api/list' + q); dt = (time.time() - t) * 1000
            d = r.json(); ver = d['ver']
            polls['n'] += 1; polls['bytes'] += len(r.content); polls['ms'].append(dt)
            time.sleep(POLL)

    ths = [threading.Thread(target=gpu, daemon=True)] + [threading.Thread(target=viewer, daemon=True) for _ in range(VIEWERS)]
    for t in ths: t.start()
    time.sleep(2)
    lat, t_end, i = [], time.time() + secs, 0
    while time.time() < t_end:                  # 上传的人：一张接一张传小图，量 init + complete 两次握手
        b = e2e.jpeg((i * 7 % 255, 90, 160), f'{mode}{i}', (320, 240)); i += 1
        h, parts = e2e.content_id(b); e2e.RUN['hs'].add(h)
        t = time.time(); r = A.post('/api/upload/init', {'h': h, 'size': len(b), 'name': f'BU_{mode}_{i}.jpg', 'type': 'image/jpeg', 'crc': 0}).json()
        t_init = time.time() - t
        for n, p in enumerate(parts, 1):
            A.req('PUT', f'/api/upload/part?h={h}&n={n}', data=p, headers={'x-part-sha256': __import__('hashlib').sha256(p).hexdigest()})
        t = time.time(); A.post('/api/upload/complete', {'h': h}); t_done = time.time() - t
        lat.append((t_init + t_done) * 1000)
        time.sleep(0.2)
    stop.set()
    for t in ths: t.join(5)
    q = lambda xs, p: sorted(xs)[min(len(xs) - 1, int(len(xs) * p))]
    out = {'mode': mode, 'uploads': len(lat), 'up_p50': st.median(lat), 'up_p95': q(lat, .95), 'up_max': max(lat),
           'polls': polls['n'], 'kb_per_poll': polls['bytes'] / max(1, polls['n']) / 1e3, 'poll_p50': st.median(polls['ms']), 'poll_p95': q(polls['ms'], .95)}
    print(f"  {'全量轮询' if mode == 'full' else '增量轮询'}：上传握手 中位 {out['up_p50']:.0f} ms · p95 {out['up_p95']:.0f} ms · 最慢 {out['up_max']:.0f} ms（{out['uploads']} 张）"
          f" ｜ 每次轮询 {out['kb_per_poll']:.1f} KB · 中位 {out['poll_p50']:.0f} ms · p95 {out['poll_p95']:.0f} ms（{out['polls']} 次）", flush=True)
    return out


def main():
    global A
    P = Client(e2e.PIPE)
    A = Client(); A.login(U)
    t = time.time(); seed(P); print(f'造了 {N} 张（{time.time() - t:.0f} 秒）· {VIEWERS} 个人开着相册 · GPU 一直在写结果')
    r = A.get('/api/list'); print(f'  全量列表 {len(r.content) / 1e6:.1f} MB')
    full = run('full'); delta = run('delta')
    check('增量轮询时，上传握手的 p95 比全量轮询时低一半以上', delta['up_p95'] < full['up_p95'] / 2, f"{full['up_p95']:.0f} → {delta['up_p95']:.0f} ms")
    check('增量轮询每次下载 < 全量的 1%', delta['kb_per_poll'] < full['kb_per_poll'] / 100, f"{full['kb_per_poll']:.0f} → {delta['kb_per_poll']:.1f} KB")
    json.dump({'n': N, 'viewers': VIEWERS, 'full': full, 'delta': delta}, open(os.path.join(e2e.HERE, 'out', 'bench-list.json'), 'w'), indent=1)


def cleanup():
    P = Client(e2e.PIPE)
    allh = HS + sorted(e2e.RUN['hs'])
    for i in range(0, len(allh), 1000): P.post('/api/pipe/purge', {'hs': allh[i:i + 1000]})
    P.post('/api/pipe/purge', {'users': [U]})


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
