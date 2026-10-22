#!/usr/bin/env python3
"""NAS 优先读（COLD_FIRST=1，本地，blobd 模拟 NAS）：
  1. R2 和 NAS 都有的 → 读 NAS（x-store: nas）、内容一字不差、Range 也行
  2. 只在 R2（还没搬 / 刚上传的）→ 退回 R2（没有 x-store 头）
  3. 只在 NAS（已释放）→ 读 NAS
  4. NAS 断线：两边都有的 → 退回 R2（x-store: r2-fallback）；只在 NAS 的 → 503；缩略图不受影响
  5. NAS 恢复后又读 NAS
起环境：COLD_FIRST=1 bash test/cold_env.sh && python test/cold_first_e2e.py http://localhost:8791 < /dev/null"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e, cold_e2e as C
from e2e import Client, check, results, upload, jpeg


def main():
    t0 = time.time()
    C.blobd(True)
    A, P = Client(), Client(e2e.PIPE)
    A.login(C.U)
    RAW, H = {}, {}
    for name, size in (('ONLY_R2.jpg', 200_000), ('ONLY_NAS.jpg', 400_000)):
        b = os.urandom(size)
        h, _, _ = upload(A, name, b); H[name], RAW[h] = h, b
        for k in 'tp': A.req('PUT', f'/api/upload/aux?h={h}&k={k}', data=jpeg((9, 9, 9), name, (64, 48)), headers={'content-type': 'application/octet-stream'})
        if name != 'ONLY_R2.jpg': P.post('/api/pipe/result', {'h': h, 'aver': 1, 'caption': name})
    rc, out = C.mover('run', '--once', '--min-age', '0')
    check('搬运工跑完：ONLY_NAS 到了 NAS，没分析的 ONLY_R2 没搬', rc == 0 and os.path.exists(C.nas_file('o/' + H['ONLY_NAS.jpg'])) and not os.path.exists(C.nas_file('o/' + H['ONLY_R2.jpg'])), out[-200:])
    r = P.post('/api/pipe/cold-release', {'olderThanDays': 0}).json()
    check('释放：ONLY_NAS 的 R2 副本删了', r['released'] == 1 and not r['bad'], r)

    def get(n, k='o', **kw): return A.req('GET', f'/f/{H[n]}/{k}', **kw)
    # 再造一张「搬了、但没释放」的：R2 和 NAS 两边都有
    b2 = os.urandom(250_000); h2, _, _ = upload(A, 'BOTH2.jpg', b2); H['BOTH2.jpg'], RAW[h2] = h2, b2
    A.req('PUT', f'/api/upload/aux?h={h2}&k=t', data=jpeg((9, 9, 9), 'x', (64, 48)), headers={'content-type': 'application/octet-stream'})
    A.req('PUT', f'/api/upload/aux?h={h2}&k=p', data=jpeg((9, 9, 9), 'x', (64, 48)), headers={'content-type': 'application/octet-stream'})
    P.post('/api/pipe/result', {'h': h2, 'aver': 1, 'caption': 'both2'})
    rc, out = C.mover('run', '--once', '--min-age', '0')
    check('BOTH2 搬到了 NAS 且 R2 还留着（没释放）', rc == 0 and os.path.exists(C.nas_file('o/' + h2)), out[-160:])

    r = get('BOTH2.jpg')
    check('1) 两边都有 → 读 NAS，内容一字不差', r.status_code == 200 and r.content == b2 and r.headers.get('x-store') == 'nas', (r.status_code, r.headers.get('x-store')))
    r = get('BOTH2.jpg', headers={'range': 'bytes=1000-1999'})
    check('1) Range 读也走 NAS，206 且切片一致', r.status_code == 206 and r.content == b2[1000:2000] and r.headers.get('x-store') == 'nas', (r.status_code, r.headers.get('x-store')))
    r = get('ONLY_R2.jpg')
    check('2) 只在 R2（没搬）→ 读 R2，内容对，没有 x-store 头', r.status_code == 200 and r.content == RAW[H['ONLY_R2.jpg']] and 'x-store' not in r.headers, (r.status_code, r.headers.get('x-store')))
    r = get('ONLY_NAS.jpg')
    check('3) 只在 NAS（已释放）→ 读 NAS，内容对', r.status_code == 200 and r.content == RAW[H['ONLY_NAS.jpg']] and r.headers.get('x-store') == 'nas', (r.status_code, r.headers.get('x-store')))

    C.blobd(False)
    r = get('BOTH2.jpg')
    check('4) NAS 断线 + R2 还有 → 退回 R2，内容对，x-store: r2-fallback', r.status_code == 200 and r.content == b2 and r.headers.get('x-store') == 'r2-fallback', (r.status_code, r.headers.get('x-store')))
    r = get('ONLY_NAS.jpg')
    check('4) NAS 断线 + 只在 NAS → 503（不是 500、不卡住）', r.status_code == 503, r.status_code)
    r = get('ONLY_NAS.jpg', 't')
    check('4) NAS 断线：缩略图照常（在 R2）', r.status_code == 200 and len(r.content) > 100, r.status_code)
    r = get('ONLY_R2.jpg')
    check('4) NAS 断线：没搬过的原件照常', r.status_code == 200 and r.content == RAW[H['ONLY_R2.jpg']])

    C.blobd(True)
    r = get('ONLY_NAS.jpg')
    check('5) NAS 恢复 → 又能读 NAS', r.status_code == 200 and r.content == RAW[H['ONLY_NAS.jpg']] and r.headers.get('x-store') == 'nas', (r.status_code, r.headers.get('x-store')))

    P.post('/api/pipe/purge', {'hs': list(H.values())})
    ok = sum(1 for r in results if r[0])
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)


if __name__ == '__main__':
    main()
