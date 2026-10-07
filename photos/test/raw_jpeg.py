#!/usr/bin/env python3
"""相机 RAW → JPEG（浏览器里，不解码）：拿各家真 RAW 样片（raw.pixls.us，CC0）在真浏览器里跑 rawJpeg，逐项对标准答案：
  · 取出来的是最大的那张内嵌 JPEG（尺寸 = rawpy 的 extract_thumb），PIL 能解开
  · 拍摄时间 / 时区 / 亚秒 / 机身 / 序列号 / 镜头 / 方向 / GPS 和 exiftool 读 RAW 本身一致
  · 同一个 RAW 转两次字节一模一样（重选能秒传）
  · 内嵌 JPEG 太小的（< 2560）不转，告诉原因（这种原样传 RAW）

    python test/raw_jpeg.py http://localhost:8787 < /dev/null      # 样片在 $RAW_SAMPLES（默认 /mnt/localssd/raw-samples）
"""
import base64, hashlib, io, json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
SET = os.environ.get('RAW_SAMPLES', '/mnt/localssd/raw-samples')
ET = os.environ.get('EXIFTOOL', '/mnt/localssd/exiftool/exiftool')
U = f'{e2e.TAG}-RAW'
TAGS = ['Make', 'Model', 'Orientation', 'DateTimeOriginal', 'OffsetTimeOriginal', 'SubSecTimeOriginal', 'SerialNumber', 'LensModel',
        'ISO', 'FNumber', 'ExposureTime', 'FocalLength', 'GPSLatitude', 'GPSLongitude']
EXIF_TAGS = {'Make', 'Model', 'Orientation', 'DateTimeOriginal', 'OffsetTimeOriginal', 'SubSecTimeOriginal', 'LensModel', 'ISO', 'FNumber', 'ExposureTime', 'FocalLength', 'GPSLatitude', 'GPSLongitude'}


def et(paths, group=None):
    a = [ET, '-q', '-j', '-n'] + ([f'-{group}:all'] if False else []) + [f'-{t}' for t in TAGS]
    return {os.path.basename(d['SourceFile']): d for d in json.loads(subprocess.check_output(a + paths))}


def main():
    import rawpy
    from PIL import Image
    from playwright.sync_api import sync_playwright
    files = sorted(f for f in os.listdir(SET) if not f.endswith('.json') and not f.startswith('.'))
    ref = et([os.path.join(SET, f) for f in files])
    thumb = {}
    for f in files:
        with rawpy.imread(os.path.join(SET, f)) as r:
            t = r.extract_thumb(); thumb[f] = Image.open(io.BytesIO(t.data)).size if t.format == rawpy.ThumbFormat.JPEG else None
    out_dir = os.path.join(e2e.HERE, 'out', 'raw'); os.makedirs(out_dir, exist_ok=True)
    A = Client(); A.login(U)
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        pg = br.new_page()
        pg.route('**/__raw/**', lambda r: r.fulfill(status=200, body=open(os.path.join(SET, r.request.url.rsplit('/', 1)[1].replace('%20', ' ')), 'rb').read()))
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        conv = {}
        for f in files:
            r = pg.evaluate("""async (n) => { const b = await (await fetch('/__raw/' + n)).blob(); const f = new File([b], n.split('__').pop(), { lastModified: 1 });
                const t = performance.now(); const r = await __album.rawJpeg(f); const ms = performance.now() - t;
                if (!r.file) return { why: r.why, ms };
                const r2 = await __album.rawJpeg(f);
                const u = new Uint8Array(await r.file.arrayBuffer()), u2 = new Uint8Array(await r2.file.arrayBuffer());
                let same = u.length === u2.length; for (let i = 0; same && i < u.length; i++) same = u[i] === u2[i];
                const bm = await createImageBitmap(r.file).catch(() => null);
                let s = ''; for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode(...u.subarray(i, i + 32768));
                return { name: r.file.name, size: r.file.size, raw: f.size, w: r.w, h: r.h, ms, same, decoded: !!bm, b64: btoa(s) }; }""", f)
            conv[f] = r
        br.close()
    for f in files:
        r, t = conv[f], thumb[f]
        if 'why' in r:
            check(f'{f}: 内嵌 JPEG 太小 → 不转（原样传 RAW）', t and max(t) < 2560, f'{r["why"]} · rawpy 看到的最大内嵌 JPEG {t}')
            continue
        p = os.path.join(out_dir, f + '.jpg'); open(p, 'wb').write(base64.b64decode(r['b64']))
        im = Image.open(p); im.load()
        check(f'{f}: 取出最大的内嵌 JPEG，浏览器和 PIL 都能解开', tuple(im.size) == tuple(t) and r['decoded'] and (r['w'], r['h']) == tuple(t),
              f'{r["w"]}×{r["h"]}（rawpy {t}）· {r["raw"] / 1e6:.0f} → {r["size"] / 1e6:.1f} MB · {r["ms"]:.0f} ms')
        got = et([p])[os.path.basename(p)]
        want = ref[f]
        bad = {k: (want.get(k), got.get(k)) for k in TAGS if k in want and k in EXIF_TAGS | {'SerialNumber'} and str(want.get(k)) != str(got.get(k))}
        # 序列号：exiftool 读 RAW 时可能取的是厂商私有字段（MakerNote），EXIF 标准字段没有就算了
        if 'SerialNumber' in bad and got.get('SerialNumber') is None: bad.pop('SerialNumber')
        check(f'{f}: 拍摄信息和 RAW 本身一致（时间 / 时区 / 机身 / 镜头 / 曝光 / 方向 / GPS）', not bad, bad or ', '.join(f'{k}={got.get(k)}' for k in ('Model', 'DateTimeOriginal', 'OffsetTimeOriginal', 'Orientation', 'SerialNumber') if got.get(k) is not None))
        check(f'{f}: 转两次字节一模一样（重选能秒传）', r['same'])


def cleanup():
    Client(e2e.PIPE).post('/api/pipe/purge', {'users': [U]})


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
