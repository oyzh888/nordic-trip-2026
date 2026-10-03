"""把 wrangler dev 模拟 R2 存的文件导出成普通文件（切到 blobd 用）。只读打开模拟器的库，不碰运行中的服务。

模拟器的格式：一个 SQLite（_mf_objects：key → blob_id）+ blobs/ 下的原始字节文件，blob 写完不再改。
  · 整份上传的对象：一个 blob → 直接**硬链接**到 files/<key>（瞬间完成、不占额外空间）
  · 分块上传的对象：blob_id 为空，块在 _mf_multipart_parts 里 → 按块号顺序拼起来
幂等：files/<key> 已存在且大小一致就跳过 —— 可以先在服务运行时导一遍，切换时停服务再补一遍增量。
    python export_r2.py /mnt/localssd/photos-store/state /mnt/localssd/photos-store/files [--verify]
"""
import glob, hashlib, os, sqlite3, sys, time

state, out = sys.argv[1], sys.argv[2]
verify = '--verify' in sys.argv
db = glob.glob(os.path.join(state, 'v3/r2/miniflare-R2BucketObject/*.sqlite'))
db = [d for d in db if not d.endswith('metadata.sqlite')]
assert len(db) == 1, db
blobs = glob.glob(os.path.join(state, 'v3/r2/*/blobs'))
assert len(blobs) == 1, blobs
blobs = blobs[0]
c = sqlite3.connect(f'file:{db[0]}?mode=ro', uri=True)
rows = c.execute('SELECT key, blob_id, size, etag FROM _mf_objects').fetchall()
t0 = time.time(); n = {'link': 0, 'concat': 0, 'skip': 0, 'bad': 0}; tot = 0
for key, bid, size, etag in rows:
    dst = os.path.join(out, key)
    if os.path.exists(dst) and os.path.getsize(dst) == size:
        n['skip'] += 1; continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.export-tmp'
    if os.path.exists(tmp): os.unlink(tmp)
    if bid:
        os.link(os.path.join(blobs, bid), tmp); kind = 'link'
    else:
        ps = c.execute('SELECT part_number, blob_id, size FROM _mf_multipart_parts WHERE object_key=? ORDER BY part_number', (key,)).fetchall()
        with open(tmp, 'wb') as f:
            for _, pb, _ in ps:
                with open(os.path.join(blobs, pb), 'rb') as g:
                    while (b := g.read(8 << 20)): f.write(b)
        kind = 'concat'
    if os.path.getsize(tmp) != size or (verify and bid and hashlib.md5(open(tmp, 'rb').read()).hexdigest() != etag):
        os.unlink(tmp); n['bad'] += 1; print('坏的', key, flush=True); continue
    os.replace(tmp, dst); n[kind] += 1; tot += size
print(f'对象 {len(rows)} · 硬链接 {n["link"]} · 拼接 {n["concat"]} · 跳过(已有) {n["skip"]} · 坏 {n["bad"]} · 新导出 {tot / 1e9:.2f} GB · {time.time() - t0:.1f}s')
sys.exit(1 if n['bad'] else 0)
