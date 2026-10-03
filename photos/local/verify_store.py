"""逐个文件核对：经相册接口把每张原图下载回来，重新算内容 ID（每 8 MB 一块的 SHA-256 拼起来再 SHA-256），
必须等于它的 h。顺带检查缩略图 / 预览 / 720p 视频都取得到。   PIPE_TOKEN=… python verify_store.py http://127.0.0.1:41069"""
import concurrent.futures as cf, hashlib, os, sys, time, requests
B = sys.argv[1].rstrip('/') + '/photos'
H = {'authorization': 'Bearer ' + os.environ['PIPE_TOKEN']}
s = requests.Session(); s.mount('http://', requests.adapters.HTTPAdapter(pool_maxsize=32))
items = s.get(B + '/api/list', headers=H).json()['items']
def one(it):
    for k in range(3):
        try: return check(it)
        except requests.RequestException as e: err = f'连接出错 {e!r:.80}'; time.sleep(2 ** k)
    return err
def check(it):
    h = it['h']; cat = b''; size = 0
    with s.get(f'{B}/f/{h}/o', headers=H, stream=True, timeout=600) as r:
        if r.status_code != 200: return f'原图 {r.status_code}'
        part, plen = hashlib.sha256(), 0
        for c in r.iter_content(1 << 20):
            size += len(c)
            while c:
                take = c[:(8 << 20) - plen]; part.update(take); plen += len(take); c = c[len(take):]
                if plen == 8 << 20: cat += part.digest(); part, plen = hashlib.sha256(), 0
        if plen or not cat: cat += part.digest()
    if hashlib.sha256(cat).hexdigest() != h: return '内容不对'
    if size != it['s']: return '大小不对'
    for bit, k in ((1, 't'), (2, 'p'), (4, 'v')):
        if it['f'] & bit and s.get(f'{B}/f/{h}/{k}', headers=H).status_code != 200: return f'{k} 取不到'
    return None
t = time.time()
with cf.ThreadPoolExecutor(16) as ex: res = list(ex.map(one, items))
bad = [(it['n'], e) for it, e in zip(items, res) if e]
print(f'核对 {len(items)} 个 · {sum(i["s"] for i in items) / 1e9:.2f} GB · {time.time() - t:.0f}s · 不对 {len(bad)}', bad[:5])
sys.exit(1 if bad else 0)
