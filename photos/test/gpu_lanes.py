#!/usr/bin/env python3
"""GPU 端的两条车道（本地，假模型）：
  1. 缩略图快车道：一批相机直出的大 JPEG（2,400 万像素，有横有竖）不带缩略图传上来 → 不等 AI 分析，几路并行先把缩略图补齐；
     竖拍的缩略图是竖的、列表里的宽高是转正后的
  2. 分析：预处理并行、一批结果一个请求写回
  3. 写回出错不让进程退出：批量写回失败退回逐张；同一张连着失败 3 次就跳过，不永远堵在队头

模型换成假的（这里测的是调度和写回，不是模型本身）。只在本地跑，结束时全部删掉。

    python test/gpu_lanes.py http://localhost:8787 [N=24] < /dev/null
"""
import argparse, io, os, sys, tempfile, threading, time, types
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pipeline'))
import e2e
from e2e import Client, check, results, upload

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 24
U = f'{e2e.TAG}-GPU'


class FakeModels:
    vlm = True
    def __init__(self, vlm=True): self.calls = 0
    def embed_images(self, ims):
        self.calls += 1; time.sleep(0.05 * len(ims))
        return [np.random.default_rng(i).standard_normal(1152).astype(np.float32) for i in range(len(ims))]
    def describe(self, ims): return [{'caption': f'测试描述 {e2e.TAG}', 'tags': {'objects': ['山'], 'special': [], 'memo': 2}, 'quality': 3} for _ in ims]
    def faces(self, im): return []


import models  # noqa: E402  （导入时不加载模型）
models.Models = FakeModels
import worker as W  # noqa: E402


def camera_jpeg(i, portrait):
    from PIL import Image, ImageDraw
    w, h = 6000, 4000
    small = Image.effect_noise((w // 8, h // 8), 40).convert('RGB').resize((w, h), Image.BILINEAR)
    d = ImageDraw.Draw(small); d.rectangle([200, 200, 2200, 1400], fill=(i * 9 % 255, 120, 200))
    ex = Image.Exif(); ex[0x010F], ex[0x0110] = 'Canon', 'Canon EOS R6'
    ex.get_ifd(0x8769)[0x9003] = f'2026:10:01 00:{i // 60:02d}:{i % 60:02d}'
    if portrait: ex[274] = 6                                    # 竖拍：像素是横的，EXIF 说转 90°
    b = io.BytesIO(); small.save(b, 'JPEG', quality=90, exif=ex); return b.getvalue()


def main():
    from PIL import Image
    A = Client(); A.login(U)
    P = Client(e2e.PIPE)
    t = time.time(); hs, port = [], set()
    for i in range(N):
        b = camera_jpeg(i, i % 3 == 0)
        h, r, _ = upload(A, f'_T6A{1000 + i}.JPG', b)
        hs.append(h)
        if i % 3 == 0: port.add(h)
    mb = 0
    print(f'传了 {N} 张 6000×4000 相机 JPEG（不带缩略图）{time.time() - t:.0f}s')
    mine = lambda: {x['h']: x for x in A.get('/api/list').json()['items'] if x['h'] in set(hs)}
    check(f'{N} 张都在相册里、都还没有缩略图', len(mine()) == N and all(not x['f'] & 3 for x in mine().values()))

    cache = tempfile.mkdtemp(prefix='gpu-lanes-', dir=os.environ.get('TMPDIR'))
    args = argparse.Namespace(base=BASE, cache=cache, no_vlm=False, no_edit=True, keep=False, store='', no_transcode=True,
                              no_thumb_lane=False, retime=False, once=False)
    w = W.Worker(args); w.stop = False
    th = threading.Thread(target=w.thumb_loop, daemon=True); th.start()
    t0 = time.time()
    while time.time() - t0 < 180:
        m = mine()
        if all(x['f'] & 3 == 3 for x in m.values()): break
        time.sleep(0.5)
    dt = time.time() - t0
    m = mine()
    done = sum(1 for x in m.values() if x['f'] & 3 == 3)
    check(f'缩略图快车道：{N} 张不等分析先补齐缩略图', done == N, f'{done}/{N} · {dt:.1f}s · 每张 {dt / N:.2f}s')
    check('补缩略图时还没开始分析（两条车道互不等待）', all(not x['a'] for x in m.values()) and w.m.calls == 0)
    t_ = Image.open(io.BytesIO(A.get(f'/f/{sorted(port)[0]}/t').content)); l_ = Image.open(io.BytesIO(A.get(f'/f/{[h for h in hs if h not in port][0]}/t').content))
    x = m[sorted(port)[0]]
    check('竖拍的缩略图是竖的、横拍的是横的；列表里的宽高是转正后的', t_.height > t_.width and l_.width > l_.height and (x['w'], x['hh']) == (4000, 6000),
          f'竖 {t_.size} · 横 {l_.size} · 列表 {x["w"]}×{x["hh"]}')
    check('缩略图 / 预览的尺寸和浏览器端同规格（短边 360 / 长边 1600）', min(t_.size) == 360 and max(Image.open(io.BytesIO(A.get(f'/f/{hs[1]}/p').content)).size) == 1600)

    # 2) 分析：并行预处理 + 一批一个请求
    sent = []
    orig_post = w.api.post
    w.api.post = lambda p, js: (sent.append(p), orig_post(p, js))[1]
    t0 = time.time()
    while True:
        pend = [it for it in P.get(f'/api/pipe/pending?aver={W.AVER}&limit=8').json()['items'] if it['h'] in set(hs)]
        if not pend: break
        w.process(pend)
    dt = time.time() - t0
    m = mine()
    check(f'分析完 {N} 张（写回了描述）', all(x['a'] and x['cap'] for x in m.values()), f'{dt:.1f}s · 每张 {dt / N:.2f}s')
    check('写回是一批一个请求（不再一张一个）', sent.count('/api/pipe/results') == -(-N // 8) and '/api/pipe/result' not in sent, {k: sent.count(k) for k in set(sent)})

    # 3) 写回出错：批量那一下 500 → 退回逐张；其中一张一直 500 → 不退出，连着 3 次之后跳过
    bad = hs[0]
    W.AVER = 2                                                  # 换了分析版本：全部重新排队
    def flaky(p, js):
        if p == '/api/pipe/results': raise RuntimeError('POST /api/pipe/results: 500 模拟')
        if p == '/api/pipe/result' and js['h'] == bad and js.get('caption'): raise RuntimeError('POST /api/pipe/result: 500 模拟')
        return orig_post(p, js)
    w.api.post = flaky
    raised, rounds = None, 0
    pending = lambda: [it for it in P.get(f'/api/pipe/pending?aver={W.AVER}&limit=50').json()['items'] if it['h'] in set(hs)]
    while (pend := pending()[:8]) and rounds < 10:
        try: w.process(pend)
        except Exception as e: raised = e   # noqa: BLE001
        rounds += 1
        if rounds == 1:
            left = {it['h'] for it in pending()}
            check('批量写回 500 → 改逐张写，同一批别的照片照样写进去；进程不退出',
                  raised is None and bad in left and not left & {it['h'] for it in pend[1:]}, f'{repr(raised)} · 这一批还剩 {len(left & {it["h"] for it in pend})}')
    left = pending()
    check('同一张连着写回失败 3 次 → 跳过（标成分析过），不永远堵在队头', raised is None and not left and w.fails.get(bad) == 3, f'剩 {len(left)} · 失败 {w.fails.get(bad)} · {rounds} 轮')
    w.stop = True
    import shutil; shutil.rmtree(cache, ignore_errors=True)


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
