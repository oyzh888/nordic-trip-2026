#!/usr/bin/env python3
"""上传和后处理分开（本地）：
  1. GPU 端的增量读（图像向量 / 人脸）和全量读结果一模一样，第二次几乎不拉数据
  2. 服务端告诉 GPU 端「刚有人在传」（upAgo），GPU 端据此把聚类等重活往后推
  3. 批量写回（/api/pipe/results）和一条条写结果一样
  4. 「已确认人脸」的小签名：有人点「这是我」就变，不变时一样

    python test/async_e2e.py http://localhost:8787 < /dev/null
"""
import base64, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pipeline'))
import e2e
from e2e import Client, check, results, upload

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
U = f'{e2e.TAG}-ASY'
HS = []


def main():
    import worker as W
    from models import q8
    A, P = Client(), Client(e2e.PIPE); A.login(U)
    rng = np.random.default_rng(5)
    for i in range(12):
        b = b'\xff\xd8\xff\xe0' + rng.bytes(5000 + i) + b'\xff\xd9'
        h, r, _ = upload(A, f'{e2e.TAG}_{i}.jpg', b); HS.append(h)
    pend = P.get('/api/pipe/pending?aver=99&limit=1').json()
    check('刚有人上传 → 服务端报 upAgo 很小（GPU 端会把重活往后推）', pend.get('upAgo') is not None and pend['upAgo'] <= 5, pend.get('upAgo'))

    # 批量写回：12 条（带向量和人脸）一个请求
    items = []
    for i, h in enumerate(HS):
        ev, es = q8(rng.normal(size=1152).astype(np.float32))
        face = {'x': .3, 'y': .2, 'w': .1, 'hh': .1, 'score': .9, 'emb': base64.b64encode(rng.bytes(1024)).decode()}
        items.append({'h': h, 'aver': 1, 'caption': f'批量 {i}', 'emb': ev, 'emb_scale': es, 'faces': [face] if i % 2 == 0 else []})
    r = P.post('/api/pipe/results', {'items': items}).json()
    I = {x['h']: x for x in A.get('/api/list').json()['items']}
    check('批量写回：12 条一个请求，描述 / 人脸都写进去了', r.get('n') == 12 and all(I[h].get('cap') == f'批量 {i}' for i, h in enumerate(HS))
          and sum(I[h]['nf'] for h in HS) == 6, {'n': r.get('n'), 'err': [x for x in r.get('res', []) if x.get('error')][:2], 'cap': [I[h].get('cap') for h in HS[:3]], 'nf': sum(I[h]['nf'] for h in HS)})

    w = W.Worker.__new__(W.Worker); w.api = W.Api(BASE, e2e.PIPE)
    full = {}
    for x in P.get('/api/pipe/embs').json():
        v = np.frombuffer(base64.b64decode(x['vec']), dtype=np.int8).astype(np.float32) * x['scale']; full[x['h']] = v / (np.linalg.norm(v) or 1)
    inc = w.load_embs()
    check('增量读的图像向量和全量读的一模一样', set(inc) == set(full) and all(np.allclose(inc[h], full[h]) for h in full), f'{len(inc)} 条')
    t = time.time(); r2 = P.get(f'/api/pipe/embs?since={w.emb_max}').json()
    check('第二次增量读：没有新的就一条都不拉', r2['rows'] == [], f'{(time.time() - t) * 1000:.0f} ms')
    ff = {f['id']: f for f in P.get('/api/pipe/faces').json()}
    lf = {f['id']: f for f in w.load_faces()}
    check('增量读的人脸（位置 / 归属 / 特征）和全量读的一模一样', ff.keys() == lf.keys() and all(ff[k] == lf[k] for k in ff), f'{len(lf)} 张脸')
    light = len(P.get('/api/pipe/faces?light=1').content); heavy = len(P.get('/api/pipe/faces').content)
    check('每次都要拉的那部分（位置 / 归属）比全量小得多', light < heavy / 3, f'{light / 1e3:.1f} KB vs 全量 {heavy / 1e3:.1f} KB')
    # 重新分析一张：旧脸删掉、换新 id → 增量读跟得上
    ev, es = q8(rng.normal(size=1152).astype(np.float32))
    P.post('/api/pipe/result', {'h': HS[0], 'aver': 1, 'emb': ev, 'emb_scale': es, 'faces': [{'x': .5, 'y': .5, 'w': .1, 'hh': .1, 'score': .8, 'emb': 'AAAA'}]})
    ff = {f['id']: f for f in P.get('/api/pipe/faces').json()}; lf = {f['id']: f for f in w.load_faces()}
    e2 = w.load_embs()
    check('重新分析一张之后：增量读到的人脸 / 向量还是和全量一致', ff.keys() == lf.keys() and all(ff[k] == lf[k] for k in ff)
          and np.allclose(e2[HS[0]], np.frombuffer(base64.b64decode(ev), np.int8).astype(np.float32) * es / np.linalg.norm(np.frombuffer(base64.b64decode(ev), np.int8).astype(np.float32) * es)))

    c0 = P.get('/api/pipe/pending?aver=99&limit=1').json()['conf']
    c1 = P.get('/api/pipe/pending?aver=99&limit=1').json()['conf']
    fid = next(f['id'] for f in P.get('/api/pipe/faces?light=1').json() if f['h'] in HS)
    A.post('/api/people/claim', {'face': fid, 'me': True})
    c2 = P.get('/api/pipe/pending?aver=99&limit=1').json()['conf']
    check('「已确认人脸」签名：没人动时不变，有人点「这是我」就变', c0 == c1 and c2 != c1, f'{c1} → {c2}')


def cleanup():
    r = Client(e2e.PIPE).post('/api/pipe/purge', {'hs': HS, 'users': [U]})
    check('收尾：测试数据删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
