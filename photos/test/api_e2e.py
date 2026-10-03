#!/usr/bin/env python3
"""API 密钥 + 命令行上传（np_upload.py）的端到端测试。本地和线上都能跑（只传随机字节，结束时全删）。

    python test/api_e2e.py http://localhost:8787
    ALBUM_PASS=… PIPE_TOKEN=… python test/api_e2e.py https://nordic.airacle.com
"""
import os, random, shutil, subprocess, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
U = f'{e2e.TAG}-API'
TOOL = os.path.join(e2e.HERE, '..', 'public', 'photos', 'np_upload.py')
HS = set()


class KeyClient(Client):
    def __init__(self, key): super().__init__(); self.key = key
    def h(self, extra=None): return {'authorization': 'Bearer ' + self.key, **(extra or {})}


def jpeg_like(n, seed):
    rnd = random.Random(seed)
    return b'\xff\xd8\xff\xe0' + rnd.randbytes(n - 6) + b'\xff\xd9'


def main():
    A = Client(); A.login(U)
    r = A.post('/api/keys', {'name': '测试脚本'}); k = r.json().get('key', '')
    check('网页登录后能生成密钥（np_ 开头）', r.status_code == 200 and k.startswith('np_') and len(k) > 30, k[:3] + '…' + str(len(k)))
    K = KeyClient(k)
    me = K.get('/api/me').json()
    check('用密钥调 /api/me → 就是本人', me.get('user', {}).get('name') == U)
    check('拿着密钥不能再生成新密钥', K.post('/api/keys', {'name': 'x'}).status_code == 403)
    check('密钥列表里有它，但不含密钥本身', [x['name'] for x in A.get('/api/keys').json()] == ['测试脚本'] and k not in A.get('/api/keys').text)
    check('乱写的密钥 → 401', KeyClient('np_' + 'x' * 32).get('/api/me').status_code == 401)

    # 一步上传
    b = jpeg_like(300_000, 1)
    r = K.req('PUT', f'/api/upload/file?name={e2e.TAG}-one.jpg', data=b, headers={'content-type': 'image/jpeg'}).json()
    HS.add(r.get('h'))
    check('一步上传（PUT /api/upload/file）', r.get('status') == 'uploaded' and r.get('h') == e2e.content_id(b)[0], r)
    r2 = K.req('PUT', f'/api/upload/file?name={e2e.TAG}-again.jpg', data=b).json()
    check('同样的字节再传 → exists（秒传）', r2.get('status') == 'exists')
    big = jpeg_like(8 * 2 ** 20, 2)
    r = K.req('PUT', f'/api/upload/file?name={e2e.TAG}-8mb.jpg', data=big).json(); HS.add(r.get('h'))
    check('一步上传 8 MB（上限）', r.get('status') == 'uploaded' and r.get('h') == e2e.content_id(big)[0], r)
    r413 = K.req('PUT', f'/api/upload/file?name={e2e.TAG}-9mb.jpg', data=jpeg_like(9 * 2 ** 20, 3))
    check('一步上传超过 8 MB → 413，提示走分块', r413.status_code == 413 and '分块' in r413.text)
    item = next((x for x in A.get('/api/list').json()['items'] if x['h'] == r.get('h')), None)
    got = A.get(f"/f/{r.get('h')}/o").content if item else b''
    check('传上去的字节和原文件一模一样', item and got == big, item and len(got))

    # 命令行工具：一个文件夹，里面有照片、一个 18 MB 的「视频」、一个 .AAE、一个隐藏文件
    d = tempfile.mkdtemp(prefix='np-')
    try:
        os.makedirs(os.path.join(d, 'sub'))
        files = {f'{e2e.TAG}_{i}.JPG': jpeg_like(200_000 + i, 10 + i) for i in range(5)}
        files[f'sub/{e2e.TAG}_v.MOV'] = jpeg_like(18 * 2 ** 20, 99)
        for n, x in files.items(): open(os.path.join(d, n), 'wb').write(x)
        open(os.path.join(d, f'{e2e.TAG}_0.AAE'), 'w').write('<plist/>'); open(os.path.join(d, '.DS_Store'), 'wb').write(b'x')
        for x in files.values(): HS.add(e2e.content_id(x)[0])
        env = {**os.environ, 'NP_KEY': k, 'NP_BASE': BASE}
        t = time.time()
        p = subprocess.run([sys.executable, TOOL, '-j', '4', d], capture_output=True, text=True, env=env, timeout=600)
        out = p.stdout + p.stderr
        hs = {x['h'] for x in A.get('/api/list').json()['items']}
        check('np_upload.py 传整个文件夹（递归、跳过 .AAE / 隐藏文件）', p.returncode == 0 and '新传 6' in out and all(e2e.content_id(x)[0] in hs for x in files.values()),
              f'{time.time() - t:.1f}s · ' + out.strip().splitlines()[-1] if out.strip() else p.returncode)
        p = subprocess.run([sys.executable, TOOL, d], capture_output=True, text=True, env=env, timeout=300)
        check('同一条命令再跑一遍 → 全部跳过，一个字节都不传', p.returncode == 0 and '6 个相册里已经有了' in p.stdout and '新传 0' in p.stdout, p.stdout.strip().splitlines()[-1])
        # 断点续传：先手工传掉 1 块，再让工具接着传
        x = jpeg_like(17 * 2 ** 20, 7); n = f'{e2e.TAG}_resume.MOV'; open(os.path.join(d, n), 'wb').write(x)
        h, parts = e2e.content_id(x); HS.add(h)
        ri = K.post('/api/upload/init', {'h': h, 'size': len(x), 'name': n, 'type': 'video/quicktime', 'crc': 0}).json()
        K.req('PUT', f'/api/upload/part?h={h}&n=1', data=parts[0], headers={'content-type': 'application/octet-stream'})
        p = subprocess.run([sys.executable, TOOL, os.path.join(d, n)], capture_output=True, text=True, env=env, timeout=300)
        check('传了一半中断 → 再跑只补缺的块（断点续传）', p.returncode == 0 and '续传完成' in p.stdout and ri.get('nparts') == 3, p.stdout.strip().splitlines()[-2:])
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # 撤销
    kid = A.get('/api/keys').json()[0]['id']
    A.post('/api/keys/revoke', {'id': kid})
    check('撤销密钥 → 马上 401', K.get('/api/me').status_code == 401)
    check('命令行用撤销的密钥 → 明确提示', '撤销' in subprocess.run([sys.executable, TOOL, TOOL], capture_output=True, text=True,
                                                    env={**os.environ, 'NP_KEY': k, 'NP_BASE': BASE}).stderr)


def cleanup():
    P = Client(e2e.PIPE)
    r = P.post('/api/pipe/purge', {'hs': sorted(h for h in HS if h), 'users': [U]})
    check('收尾：测试文件、用户和密钥全部删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s · {BASE}')
    sys.exit(0 if ok == len(results) else 1)
