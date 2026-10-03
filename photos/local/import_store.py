"""搬家第一步：把从 R2 拉到本地的文件（manifest.json + r2/<key>）导入本机跑的相册。
字节经 /api/pipe/blob 写进本地存储，原件再经 /api/pipe/import 登记成照片（状态 ready，GPU 端会重新分析）。
幂等：已登记的跳过（INSERT OR IGNORE），字节重写一遍也无害。
    PIPE_TOKEN=… python import_store.py http://127.0.0.1:41069 /mnt/localssd/photos-store
"""
import concurrent.futures as cf, json, os, sys, time, requests
from datetime import datetime
BASE, SRC = sys.argv[1].rstrip('/'), sys.argv[2]
H = {'authorization': 'Bearer ' + os.environ['PIPE_TOKEN']}
objs = json.load(open(os.path.join(SRC, 'manifest.json')))
keys = {o['key'] for o in objs}
s = requests.Session()

def put(o):
    p = os.path.join(SRC, 'r2', o['key'])
    for i in range(5):
        try:
            r = s.put(f"{BASE}/photos/api/pipe/blob", params={'k': o['key']}, data=open(p, 'rb').read(), timeout=300,
                      headers={**H, 'content-type': (o.get('http_metadata') or {}).get('contentType') or 'application/octet-stream'})
            if r.ok: return True
        except requests.RequestException: pass
        time.sleep(2 ** i)
    return False

t = time.time()
with cf.ThreadPoolExecutor(8) as ex: ok = list(ex.map(put, objs))
print(f'blob {sum(ok)}/{len(objs)} · {time.time() - t:.0f}s', flush=True)
items = []
for o in objs:
    if not o['key'].startswith('o/'): continue
    h = o['key'][2:]
    flags = (1 if f't/{h}.jpg' in keys else 0) | (2 if f'p/{h}.jpg' in keys else 0) | (4 if f'v/{h}.mp4' in keys else 0)
    items.append({'h': h, 'size': o['size'], 'type': (o.get('http_metadata') or {}).get('contentType'), 'flags': flags,
                  'created': int(datetime.fromisoformat(o['last_modified'].replace('Z', '+00:00')).timestamp() * 1000)})
n = 0
for i in range(0, len(items), 200):
    n += s.post(f"{BASE}/photos/api/pipe/import", json={'items': items[i:i + 200]}, headers=H, timeout=120).json()['imported']
print(f'media 登记 {n}（原件共 {len(items)}）', flush=True)
sys.exit(0 if all(ok) else 1)
