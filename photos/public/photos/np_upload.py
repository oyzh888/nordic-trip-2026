#!/usr/bin/env python3
"""北欧 2026 共享相册 · 命令行批量上传（只用 Python 标准库，不用装任何东西）

    export NP_KEY=np_xxxxxxxx            # 相册网页 → 上传 → 「🔑 用脚本批量传」里生成
    python3 np_upload.py ~/Pictures/冰岛 ~/Desktop/IMG_1234.HEIC
    python3 np_upload.py -j 8 /Volumes/SD卡/DCIM          # 8 个文件同时传

- 文件夹会递归进去；只传照片 / 视频 / 相机 RAW，其它文件（.AAE、.DS_Store…）跳过
- 断点续传：传到一半中断，重新跑同一条命令 —— 传过的秒跳过，传一半的只补缺的块
- 去重：相册里已经有的（谁传的都算）不会再传一遍
- Live Photo（HEIC + MOV）、RAW、各种格式都原样上传，相册那边会自动配对 / 解码
文档：https://nordic.airacle.com/photos/api.html
"""
import argparse, hashlib, json, mimetypes, os, sys, threading, time, urllib.error, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor, as_completed

PART = 8 * 2 ** 20
EXT = set('jpg jpeg png webp gif avif heic heif hif tif tiff dng raw arw srf sr2 cr2 cr3 crw nef nrw orf rw2 raf pef srw rwl 3fr iiq x3f '
          'mov mp4 m4v 3gp mkv avi webm insv insp'.split())
UA = 'np_upload/1.0'


class Api:
    def __init__(self, base, key):
        self.base, self.key = base.rstrip('/') + '/photos', key

    def call(self, method, path, body=None, data=None, headers=None, tries=6):
        h = {'authorization': 'Bearer ' + self.key, 'user-agent': UA, **(headers or {})}
        if body is not None:
            data, h['content-type'] = json.dumps(body).encode(), 'application/json'
        for i in range(tries):
            try:
                with urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, method=method, headers=h), timeout=600) as r:
                    return json.loads(r.read() or b'{}')
            except urllib.error.HTTPError as e:
                msg = e.read().decode('utf-8', 'replace')[:300]
                if e.code == 401: sys.exit('密钥不对或已被撤销（401）。到相册网页 → 上传 →「🔑 用脚本批量传」重新生成')
                if e.code < 500 and e.code not in (408, 429): raise RuntimeError(f'{e.code} {msg}')
                err = f'{e.code} {msg}'
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
                err = repr(e)
            time.sleep(min(30, 2 ** i))
        raise RuntimeError(f'{method} {path} 重试 {tries} 次仍失败：{err}')


def fingerprint(path, size):
    """内容 ID = SHA-256(每 8 MB 块的 SHA-256 依次拼接)，和网页端、服务端同一个算法"""
    shas, crc = [], 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(PART)
            if not b: break
            shas.append(hashlib.sha256(b).digest()); crc = zlib.crc32(b, crc)
    if not shas: shas = [hashlib.sha256(b'').digest()]
    return hashlib.sha256(b''.join(shas)).hexdigest(), [s.hex() for s in shas], crc & 0xFFFFFFFF


def upload(api, path, size, log):
    name = os.path.basename(path)
    h, shas, crc = fingerprint(path, size)
    typ = mimetypes.guess_type(name)[0] or ''
    for _ in range(40):
        r = api.call('POST', '/api/upload/init', {'h': h, 'size': size, 'name': name, 'type': typ, 'crc': crc})
        if r.get('status') != 'wait': break
        time.sleep(3)                               # 另一处正在传同一个文件
    if r.get('status') == 'exists': return 'dup'
    n, done = r['nparts'], set(r.get('done') or [])
    for _round in range(3):
        c = None
        with open(path, 'rb') as f:
            for i in range(1, n + 1):
                if i in done: continue
                f.seek((i - 1) * PART); b = f.read(PART)
                pr = api.call('PUT', f'/api/upload/part?h={h}&n={i}', data=b, headers={'content-type': 'application/octet-stream', 'x-part-sha256': shas[i - 1]})
                if pr.get('status') in ('done', 'corrupt') or pr.get('complete'): c = {'status': pr.get('status') or 'done'}   # 单块：服务端顺手收了尾
                done.add(i)
                if n > 1: log(f'  {name}  {len(done)}/{n} 块')
        c = c or api.call('POST', '/api/upload/complete', {'h': h})
        if c.get('status') in ('done', 'exists'): return 'ok' if not r.get('done') else 'resumed'
        if c.get('status') == 'missing': done = set(c.get('done') or []); continue
        raise RuntimeError(f'complete: {c}')
    raise RuntimeError('传了 3 轮还缺块')


def collect(paths):
    out = []
    for p in paths:
        p = os.path.expanduser(p)
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                out += [os.path.join(root, f) for f in sorted(files)]
        elif os.path.isfile(p):
            out.append(p)
        else:
            print(f'找不到：{p}', file=sys.stderr)
    return [f for f in out if not os.path.basename(f).startswith('.') and f.rsplit('.', 1)[-1].lower() in EXT]


def main():
    ap = argparse.ArgumentParser(description='批量上传到北欧 2026 共享相册')
    ap.add_argument('paths', nargs='+', help='文件或文件夹（文件夹递归）')
    ap.add_argument('-k', '--key', default=os.environ.get('NP_KEY'), help='API 密钥（默认读环境变量 NP_KEY）')
    ap.add_argument('-j', '--jobs', type=int, default=4, help='同时传几个文件（默认 4）')
    ap.add_argument('--base', default=os.environ.get('NP_BASE', 'https://nordic.airacle.com'))
    a = ap.parse_args()
    if not a.key: sys.exit('缺密钥：export NP_KEY=np_…（相册网页 → 上传 →「🔑 用脚本批量传」里生成）')
    api = Api(a.base, a.key)
    me = api.call('GET', '/api/me')['user']
    files = collect(a.paths)
    sizes = {f: os.path.getsize(f) for f in files}
    files = [f for f in files if sizes[f]]
    total = sum(sizes.values())
    print(f'以「{me["name"]}」的身份上传 {len(files)} 个文件，共 {total / 2**30:.2f} GB → {a.base}/photos/')
    # 先整批问一次「文件名 + 大小」相册里有没有 —— 重跑同一条命令时，传过的不用再读文件
    todo, dup = [], 0
    for i in range(0, len(files), 1000):
        part = files[i:i + 1000]
        hit = set(api.call('POST', '/api/upload/probe', {'items': [[os.path.basename(f), sizes[f]] for f in part]}).get('hit') or [])
        dup += len(hit); todo += [f for j, f in enumerate(part) if j not in hit]
    if dup: print(f'{dup} 个相册里已经有了，跳过')
    lock, st, t0 = threading.Lock(), {'ok': 0, 'dup': dup, 'fail': 0, 'bytes': 0}, time.time()
    log = lambda s: print(s, flush=True)

    def one(f):
        r = upload(api, f, sizes[f], log)
        with lock:
            st['ok' if r != 'dup' else 'dup'] += 1; st['bytes'] += sizes[f]
            dt = time.time() - t0
            log(f'[{st["ok"] + st["dup"] - dup + st["fail"]}/{len(todo)}] {"秒传" if r == "dup" else "续传完成" if r == "resumed" else "✓"} '
                f'{os.path.basename(f)}  ({st["bytes"] / 2**20 / max(dt, .1):.1f} MB/s)')
    with ThreadPoolExecutor(max(1, a.jobs)) as ex:
        futs = {ex.submit(one, f): f for f in todo}
        for fu in as_completed(futs):
            if fu.exception():
                with lock: st['fail'] += 1
                log(f'✗ {futs[fu]}: {fu.exception()}')
    print(f'\n完成：新传 {st["ok"]} · 已有 {st["dup"]} · 失败 {st["fail"]} · 用时 {time.time() - t0:.0f} 秒'
          + ('\n失败的重新跑同一条命令就行（会从断点接着传）' if st['fail'] else ''))
    sys.exit(1 if st['fail'] else 0)


if __name__ == '__main__':
    main()
