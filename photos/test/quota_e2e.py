"""存储上限测试：相册跑在本机时，超过 MAX_BYTES（或盘剩余低于 MIN_FREE_BYTES）就拒绝新文件，已有的照片照常秒传。

要对着一个**上限设得很小**的测试实例跑（别对着正式相册跑 —— 它会把磁盘用量报成「满了」，虽然最后会报回来）：
    PHOTOS_STORE=/mnt/localssd/photos-store-test PHOTOS_PORT=41070 PHOTOS_SESSION=photos-test \
      MAX_BYTES=300000000 bash photos/local/run_local.sh
    ALBUM_PASS=… PIPE_TOKEN=… python test/quota_e2e.py http://127.0.0.1:41070
"""
import os, sys, time, random, types, tempfile, shutil

sys.path.insert(0, os.path.dirname(__file__))
import e2e  # noqa: E402
from e2e import Client, check, upload, jpeg, RUN, PIPE, TAG  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

U = TAG + '-Q'


def one_shot(c, name, b):
    h, _ = e2e.content_id(b); RUN['hs'].add(h)
    return c.req('PUT', f'/api/upload/file?name={name}', data=b, headers={'content-type': 'image/jpeg'})


def main():
    P = Client(PIPE)
    A = Client(); A.login(U)
    q = A.get('/api/stats').json()['quota']
    check('stats 里能看到存储上限', q['cap'] > 0 and q['cap'] < 1e9, q)
    cap = q['cap']

    b1 = jpeg((200, 40, 40), 'Q1')
    h1, r, _ = upload(A, 'Q1.JPG', b1)
    check('没满：正常上传', r.get('status') in ('done', 'uploaded', 'ready') or r.get('ok'), r)

    # 1. 单个文件本身就超过剩余额度 → init 直接 413，不建任何上传任务
    big = int(cap)  # 声称的大小 = 整个上限
    r = A.post('/api/upload/init', {'h': '%064x' % random.getrandbits(256), 'size': big, 'name': 'huge.mov', 'type': 'video/quicktime'})
    check('文件大过剩余额度 → 413 + 说清楚原因', r.status_code == 413 and r.json().get('status') == 'full' and '上限' in r.json().get('error', ''), (r.status_code, r.text[:120]))

    # 2. GPU 端报上来的真实占用已经到上限 → 再小的新文件也拒绝（两个上传入口都拒）
    P.post('/api/pipe/disk', {'used': cap, 'free': 10 ** 13})
    b2 = jpeg((40, 200, 40), 'Q2')
    h2, _ = e2e.content_id(b2); RUN['hs'].add(h2)
    r = A.post('/api/upload/init', {'h': h2, 'size': len(b2), 'name': 'Q2.JPG', 'type': 'image/jpeg'})
    check('实测占用到上限 → 分块上传 init 被拒（413）', r.status_code == 413, (r.status_code, r.text[:100]))
    r = one_shot(A, 'Q2.JPG', b2)
    check('实测占用到上限 → 一步上传也被拒（413）', r.status_code == 413 and r.json().get('status') == 'full', (r.status_code, r.text[:100]))
    r = A.post('/api/upload/init', {'h': h1, 'size': len(b1), 'name': 'Q1.JPG', 'type': 'image/jpeg'})
    check('满了也不影响秒传已有的照片（不占新空间）', r.status_code == 200 and r.json().get('status') == 'exists', r.text[:100])
    check('满了之后列表、浏览照常', A.get('/api/list').status_code == 200 and A.get(f'/f/{h1}/o').status_code == 200)
    q = A.get('/api/stats').json()['quota']
    check('stats 显示已用 ≥ 上限', q['used'] >= cap, q)

    # 3. 整块盘剩余太少 → 也拒绝
    P.post('/api/pipe/disk', {'used': 0, 'free': 1})
    r = one_shot(A, 'Q2.JPG', b2)
    check('盘剩余低于 MIN_FREE_BYTES → 拒绝（413，提示磁盘快满）', r.status_code == 413 and '磁盘' in r.json().get('error', ''), r.text[:100])

    # 4. 腾出空间后恢复
    P.post('/api/pipe/disk', {'used': 0, 'free': 10 ** 13})
    r = one_shot(A, 'Q2.JPG', b2)
    check('空间够了 → 恢复接收', r.status_code == 200 and r.json().get('status') in ('uploaded', 'exists'), r.text[:100])

    # 5. GPU 端真的去量盘：用 worker.disk_loop 量一个已知大小的目录，确认报上去的数和服务端算的对得上
    import worker as W
    d = tempfile.mkdtemp(dir=os.environ.get('TMPDIR', '/tmp'))
    try:
        for i in range(3):
            open(os.path.join(d, f'f{i}'), 'wb').write(os.urandom(4 * 2 ** 20))
        stub = types.SimpleNamespace(args=types.SimpleNamespace(store=d), api=types.SimpleNamespace(post=lambda p, js: P.post(p, js).json()), stop=False)
        orig_sleep = W.time.sleep
        W.time.sleep = lambda s: setattr(stub, 'stop', True)       # 只跑一轮
        try: W.Worker.disk_loop(stub)
        finally: W.time.sleep = orig_sleep
        q = A.get('/api/stats').json()['quota']
        check('GPU 端 du 一遍目录并上报（3 × 4 MB → 约 12.6 MB）', q['disk'] is not None and 12e6 <= q['disk'] <= 13.5e6 and q['free'] > 0, q)
    finally:
        shutil.rmtree(d, ignore_errors=True)
        P.post('/api/pipe/disk', {'used': 0, 'free': 10 ** 13})


if __name__ == '__main__':
    t0 = time.time()
    try:
        main()
    except Exception as e:
        import traceback; traceback.print_exc()
        check('脚本跑完', False, repr(e))
    finally:
        r = Client(PIPE).post('/api/pipe/purge', {'hs': sorted(RUN['hs']), 'users': [U]})
        check('收尾：测试文件和用户全部删除', r.status_code == 200, r.text[:80])
    bad = [r for r in e2e.results if not r[1]]
    print(f"\n{len(e2e.results) - len(bad)}/{len(e2e.results)} 通过 · {time.time() - t0:.0f}s · {e2e.BASE}")
    sys.exit(1 if bad else 0)
