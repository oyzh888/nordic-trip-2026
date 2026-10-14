#!/usr/bin/env python3
"""冷存储搬运工：跑在 NAS 上，把相册的原件（o/）和视频 H.264 新版（g/）从 Cloudflare 的 R2 拷到 NAS，
核对无误后让引擎记下来；过了宽限期再让引擎删掉 R2 里那份。缩略图 / 预览 / 720p 视频不搬（永远在 R2，翻相册不碰 NAS）。

它自己什么都不决定，只是照引擎的清单干活：
  搬谁      GET  /api/pipe/cold-todo      （分析完、缩略图做好了的才在清单里，新传的先在 R2 放几分钟）
  怎么搬    GET  /f/<h>/o                 从相册把字节流下来（经 Worker，R2 出口免费），边流边往本机 blobd 写、边算内容 ID，
            PUT  blobd /o/o/<h>           写完比一遍：原件的内容 ID 必须等于文件名里的 h，新版视频的 CRC32 必须等于登记的
  记下      POST /api/pipe/cold-done      引擎自己再去 NAS 取一次文件大小核对（顺便验证「从公网经隧道读 NAS」这条路是通的）
  释放 R2   POST /api/pipe/cold-release   只删「核对过 + 过了宽限期」的 R2 副本 —— 这之后 NAS 是唯一副本

幂等、可随时中断：同一个文件再跑一遍，NAS 上已经有就跳过下载；引擎没记下的，下一轮清单里还会出现。
纯标准库（NAS 容器里不一定有 requests）。令牌只从环境变量读，不打印。

    PIPE_TOKEN=… BLOBD_TOKEN=… python3 cold_mover.py --engine https://<相册域名> --blobd http://blobd:41071 run
        --limit 20            只搬 20 个就停（金丝雀）           --dry-run  只列清单，不搬
        --release-after-days 14   搬完的、核对过超过 14 天的，删掉 R2 里那份（不给这个参数就永远不删）
        --release-limit 5         总共最多释放 5 个（释放金丝雀；0 = 不限）
    ... status                 进度：多少在 NAS、多少 R2 已释放、还剩多少
    ... scrub [--sample N]     巡检：把 NAS 上已登记的文件读回来重新算内容 ID（防静默坏块）
    ... gc --data-dir /data [--apply]   清 NAS 上引擎不认的孤儿文件（默认只列；只动 1 天前的）
    ... check --h <h> [<h> …] | --sample N   走用户真实会走的路（公网 → Worker →［R2 没有就］NAS）把原件读回来，重算内容 ID，报耗时和速度
"""
import argparse, hashlib, http.client, json, os, sys, threading, time, urllib.error, urllib.parse, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor

PART = 8 * 2 ** 20
LOCK = threading.Lock()
ENGINE = BLOBD = ''
PIPE = BLOBD_TOK = ''


def log(*a):
    with LOCK:
        print(time.strftime('%m-%d %H:%M:%S'), *a, flush=True)


def api(method, path, body=None, tries=6):
    data = json.dumps(body).encode() if body is not None else None
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(ENGINE + '/photos' + path, data=data, method=method,
                                         headers={'authorization': 'Bearer ' + PIPE, 'content-type': 'application/json', 'user-agent': 'cold-mover/1'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read() or b'{}')
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'replace')[:200]
            if e.code < 500 and e.code not in (408, 429): raise RuntimeError(f'{method} {path}: {e.code} {msg}')
            err = f'{e.code} {msg}'
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            err = repr(e)[:150]
        time.sleep(min(60, 2 ** i))
    raise RuntimeError(f'{method} {path}: {err}')


class Blobd:
    def __init__(self, base, token):
        u = urllib.parse.urlparse(base)
        self.https, self.host, self.port = u.scheme == 'https', u.hostname, u.port or (443 if u.scheme == 'https' else 80)
        self.h = {'x-blobd-token': token}

    def conn(self):
        return (http.client.HTTPSConnection if self.https else http.client.HTTPConnection)(self.host, self.port, timeout=600)

    def head(self, key):
        c = self.conn()
        try:
            c.request('HEAD', '/o/' + key, headers=self.h)
            r = c.getresponse(); r.read()
            return int(r.getheader('x-size') or r.getheader('content-length') or 0) if r.status == 200 else None
        finally:
            c.close()

    def put(self, key, size, chunks):
        c = self.conn()
        try:
            c.putrequest('PUT', '/o/' + key)
            for k, v in {**self.h, 'content-length': str(size)}.items(): c.putheader(k, v)
            c.endheaders()
            for ch in chunks: c.send(ch)
            r = c.getresponse(); b = r.read()
            if r.status != 200: raise RuntimeError(f'blobd PUT {key}: {r.status} {b[:100]!r}')
            return json.loads(b)
        finally:
            c.close()

    def get(self, key):
        c = self.conn()
        c.request('GET', '/o/' + key, headers=self.h)
        r = c.getresponse()
        if r.status != 200: c.close(); raise RuntimeError(f'blobd GET {key}: {r.status}')
        return c, r

    def delete(self, keys):
        c = self.conn()
        try:
            c.request('POST', '/delete', body=json.dumps({'keys': keys}), headers={**self.h, 'content-type': 'application/json'})
            r = c.getresponse(); r.read()
        finally:
            c.close()


class Cid:
    """内容 ID（和相册一致）：每 8 MB 一块各算 SHA-256，再对这串哈希算一次 SHA-256"""
    def __init__(self): self.cat, self.cur, self.n = b'', hashlib.sha256(), 0

    def update(self, b):
        while b:
            take = b[:PART - self.n]; self.cur.update(take); self.n += len(take); b = b[len(take):]
            if self.n == PART: self.cat += self.cur.digest(); self.cur, self.n = hashlib.sha256(), 0

    def hexdigest(self):
        cat = self.cat + (self.cur.digest() if self.n or not self.cat else b'')
        return hashlib.sha256(cat).hexdigest()


def download(path):
    req = urllib.request.Request(ENGINE + '/photos' + path, headers={'authorization': 'Bearer ' + PIPE, 'user-agent': 'cold-mover/1'})
    return urllib.request.urlopen(req, timeout=600)


def copy_key(bd, h, key, size, kind, crc=None):
    """把 key 对应的字节从相册流到 NAS。返回 None = 成功，否则一句原因"""
    have = bd.head(key)
    if have == size: return None                                   # 已经在了（blobd 写文件是临时名 + 原子改名，在就是完整的）
    resp = download(f'/f/{h}/{"o" if key.startswith("o/") else "g"}')
    try:
        n = int(resp.headers.get('content-length') or -1)
        if n != size: return f'相册给的大小 {n} ≠ 登记的 {size}'
        cid, c32, got = Cid(), 0, 0

        def chunks():
            nonlocal c32, got
            while True:
                b = resp.read(1 << 20)
                if not b: break
                got += len(b); cid.update(b); c32 = zlib.crc32(b, c32)
                yield b
            if got != size: raise IOError(f'只收到 {got}/{size} 字节')
        r = bd.put(key, size, chunks())
    finally:
        resp.close()
    if r.get('size') != size: bd.delete([key]); return f'写进去的大小 {r.get("size")} ≠ {size}'
    if key.startswith('o/') and cid.hexdigest() != h: bd.delete([key]); return '内容 ID 对不上（原件在传输中坏了）'
    if key.startswith('g/') and crc is not None and (c32 & 0xFFFFFFFF) != (int(crc) & 0xFFFFFFFF): bd.delete([key]); return '视频新版 CRC32 对不上'
    return None


def move_item(bd, it):
    h = it['h']
    try:
        why = copy_key(bd, h, 'o/' + h, it['size'], it['kind'])
        if not why and it.get('gsize'): why = copy_key(bd, h, f'g/{h}.mp4', it['gsize'], 'g', it.get('gcrc'))
    except Exception as e:  # noqa: BLE001 —— 一个坏的不能拖垮一批
        why = repr(e)[:160]
    return h, why


def cycle(a, bd):
    todo = api('GET', f'/api/pipe/cold-todo?limit={min(a.batch, a.limit) if a.limit else a.batch}&minAgeMin={a.min_age}')
    items = todo['items']
    if not items: return 0, todo
    t0 = time.time(); nbytes = sum(i['size'] + (i.get('gsize') or 0) for i in items)
    log(f'清单 {len(items)} 个（共还剩 {todo["left"]} 个 · {todo["leftBytes"] / 1e9:.1f} GB）')
    if a.dry_run:
        for i in items: log(f'  {i["h"][:12]} {i["kind"]:5s} {i["size"] / 1e6:8.1f} MB' + (f' + 新版 {i["gsize"] / 1e6:.1f} MB' if i.get('gsize') else ''))
        return 0, todo
    with ThreadPoolExecutor(a.workers) as ex: res = list(ex.map(lambda it: move_item(bd, it), items))
    good = [h for h, why in res if not why]
    for h, why in res:
        if why: log(f'  ✗ {h[:12]} {why}')
    ok = []
    for i in range(0, len(good), 15):                              # 一次最多 15 个（免费版每个请求最多 50 次外部调用）
        r = api('POST', '/api/pipe/cold-done', {'items': good[i:i + 15]})
        ok += r['ok']
        for b in r['bad']: log(f'  ✗ {b["h"][:12]} 引擎核对没过：{b["why"]}')
    dt = time.time() - t0
    log(f'搬了 {len(ok)}/{len(items)} 个 · {nbytes / 1e6:.0f} MB · {dt:.0f}s · {nbytes / 1e6 / max(dt, .1):.1f} MB/s')
    return len(ok), todo


def release(a):
    tot = 0
    while not a.release_limit or tot < a.release_limit:
        r = api('POST', '/api/pipe/cold-release', {'olderThanDays': a.release_after_days, 'limit': min(12, a.release_limit - tot) if a.release_limit else 12})
        for b in r.get('bad', []): log(f'  ✗ 不释放 {b["h"][:12]}：{b["why"]}')
        if not r['released']: break
        tot += r['released']; log(f'释放 R2 副本 {r["released"]} 个 · {r["bytes"] / 1e6:.0f} MB（累计 {tot}）')
    return tot


def status():
    s = api('GET', '/api/pipe/cold-status'); g = lambda x: f'{x["n"]} 个 · {x["b"] / 1e9:.1f} GB'
    print(f'冷存储{"已配置" if s.get("configured") else "没配（Worker 缺 COLD_URL / COLD_TOKEN）"}\n  相册共        {g(s["total"])}\n  NAS 有核对过的  {g(s["onCold"])}'
          f'\n  R2 已释放      {g(s["hotReleased"])}   ← 这些只剩 NAS 一份\n  只在 R2        {g(s["hotOnly"])}\n  现在可搬       {s["eligibleNow"]["n"]} 个 · {s["eligibleNow"]["b"] / 1e9:.1f} GB')


def scrub(bd, sample):
    after, n, bad = '', 0, []
    while True:
        page = api('GET', f'/api/pipe/cold-list?after={after}&limit=500')
        if not page: break
        for it in page:
            after = it['h']
            if sample and n >= sample: break
            n += 1
            try:
                c, r = bd.get('o/' + it['h'])
                cid, got = Cid(), 0
                for b in iter(lambda: r.read(1 << 20), b''): cid.update(b); got += len(b)
                c.close()
                if got != it['size'] or cid.hexdigest() != it['h']: bad.append(it['h'])
                if it.get('gsize') and bd.head(f'g/{it["h"]}.mp4') != it['gsize']: bad.append(it['h'])
            except Exception as e:  # noqa: BLE001
                bad.append(it['h']); log('  ✗', it['h'][:12], repr(e)[:100])
        if sample and n >= sample: break
    log(f'巡检 {n} 个 · 不对 {len(set(bad))}' + ('' if not bad else '：' + ', '.join(h[:12] for h in sorted(set(bad))[:10])))
    return 1 if bad else 0


def check(hs, sample):
    """端到端：和用户点「下载原图」走一模一样的路。释放 R2 之后，这就是「用户拿到的东西对不对、多快」的证据"""
    if not hs:
        import random
        page = api('GET', '/api/pipe/cold-list?limit=2000')
        hs = [it['h'] for it in random.sample(page, min(sample or 3, len(page)))]
    bad = 0
    for h in hs:
        t0 = time.time()
        try:
            resp = download(f'/f/{h}/o'); cid, n = Cid(), 0
            for b in iter(lambda: resp.read(1 << 20), b''): cid.update(b); n += len(b)
            resp.close(); ok = cid.hexdigest() == h
        except Exception as e:  # noqa: BLE001
            log('  ✗', h[:12], repr(e)[:120]); bad += 1; continue
        dt = time.time() - t0
        log(f'  {"✓" if ok else "✗"} {h[:12]} {n / 1e6:.1f} MB · {dt:.1f}s · {n * 8 / 1e6 / max(dt, .001):.0f} Mbps' + ('' if ok else ' —— 内容 ID 对不上！'))
        bad += not ok
    return 1 if bad else 0


def gc(bd, data_dir, apply):
    keep, after = set(), ''
    while True:
        page = api('GET', f'/api/pipe/cold-list?after={after}&limit=2000')
        if not page: break
        for it in page: keep.add(it['h'])
        after = page[-1]['h']
    old, orphans, nb = time.time() - 86400, [], 0
    for d, ext in (('o', ''), ('g', '.mp4')):
        for f in os.listdir(os.path.join(data_dir, d)):
            h = f[:-len(ext)] if ext and f.endswith(ext) else f
            p = os.path.join(data_dir, d, f)
            if h not in keep and os.path.getmtime(p) < old: orphans.append(f'{d}/{f}'); nb += os.path.getsize(p)
    log(f'NAS 上引擎不认的孤儿文件 {len(orphans)} 个 · {nb / 1e6:.0f} MB' + ('' if apply else '（只列出，加 --apply 才删）'))
    if apply and orphans:
        for i in range(0, len(orphans), 200): bd.delete(orphans[i:i + 200])
        log('已删除')


def main():
    global ENGINE, PIPE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['run', 'status', 'scrub', 'gc', 'check'])
    ap.add_argument('--engine', default=os.environ.get('ENGINE_URL', ''), help='相册地址（https://…，不带 /photos）')
    ap.add_argument('--blobd', default=os.environ.get('BLOBD_URL', 'http://blobd:41071'))
    ap.add_argument('--workers', type=int, default=int(os.environ.get('MOVER_WORKERS', 3)))
    ap.add_argument('--batch', type=int, default=30)
    ap.add_argument('--min-age', type=int, default=10, help='新传的先在 R2 放几分钟（分钟）')
    ap.add_argument('--limit', type=int, default=0, help='总共只搬这么多个就退出（金丝雀）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--once', action='store_true', help='清单搬空就退出（默认一直守着，新传的会接着搬）')
    ap.add_argument('--release-after-days', type=float, default=None)
    ap.add_argument('--release-limit', type=int, default=0, help='总共最多释放这么多个（释放金丝雀）')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--h', nargs='*', default=[])
    ap.add_argument('--data-dir', default='')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    ENGINE = a.engine.rstrip('/')
    PIPE = os.environ.get('PIPE_TOKEN', '')
    if not ENGINE or not PIPE: sys.exit('需要 --engine（或 ENGINE_URL）和环境变量 PIPE_TOKEN')
    bd = Blobd(a.blobd, os.environ.get('BLOBD_TOKEN', ''))
    if a.cmd == 'status': return status()
    if a.cmd == 'scrub': sys.exit(scrub(bd, a.sample))
    if a.cmd == 'check': sys.exit(check(a.h, a.sample))
    if a.cmd == 'gc':
        if not a.data_dir: sys.exit('gc 需要 --data-dir')
        return gc(bd, a.data_dir, a.apply)
    moved = 0
    while True:
        try:
            n, todo = cycle(a, bd)
            moved += n
            if a.dry_run: return
            if a.limit and moved >= a.limit: break
            if n == 0:                                              # 清单空了 / 这一批一个都没搬成
                if a.release_after_days is not None: release(a)
                if a.once or not todo['items']:
                    if a.once: break
                    time.sleep(60)
                else:
                    time.sleep(30)
        except Exception as e:  # noqa: BLE001 —— 守着的进程不能因为一次网络抖动退出
            log('出错，30 秒后重试：', repr(e)[:200])
            if a.once: raise
            time.sleep(30)
    if a.release_after_days is not None: release(a)
    status()


if __name__ == '__main__':
    main()
