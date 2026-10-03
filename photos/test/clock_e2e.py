#!/usr/bin/env python3
"""相机时钟对齐的端到端测试（本地）：真 JPEG（EXIF 里写拍摄时间 / GPS / 机身序列号）→ 本地相册 →
GPU 端代码（worker.backfill_clock + align_clocks，不加载模型）→ 查列表里的时间。

    python test/clock_e2e.py http://localhost:8787

场景：挪威 6 个场景，每个场景手机拍 2 张（有 GPS，时间准）、相机拍 3 张（没 GPS、没时区标签，钟是北京时间还快 15 分钟）。
「已经分析过」的状态用 /api/pipe/result 模拟（带图像向量；同场景的向量相近）—— 和线上那批老照片的处境一样：
库里没有原始钟点，要 backfill 从原件 EXIF 里补。
"""
import io, os, sys, time
from datetime import datetime, timedelta
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pipeline'))
import e2e
from e2e import Client, check, results, upload

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
U = f'{e2e.TAG}-CLK'
HS = []


def jpeg(seed, dto, lat=None, lon=None, make='Apple', model='iPhone 15 Pro Max', serial=None):
    from PIL import Image
    im = Image.new('RGB', (64, 48), ((seed * 37) % 255, (seed * 91) % 255, 120))
    ex = Image.Exif(); ex[0x010F], ex[0x0110] = make, model
    sub = ex.get_ifd(0x8769); sub[0x9003] = dto.strftime('%Y:%m:%d %H:%M:%S')
    if serial: sub[0xA431] = serial
    if lat is not None:
        r = lambda x: (int(x), int((x % 1) * 60), round(((x * 60) % 1) * 60, 2))
        g = ex.get_ifd(0x8825); g[1], g[2], g[3], g[4] = 'N', r(lat), 'E', r(lon)
    b = io.BytesIO(); im.save(b, 'JPEG', exif=ex.tobytes()); return b.getvalue()


def main():
    import worker as W, media as M
    from models import q8
    A, P = Client(), Client(e2e.PIPE); A.login(U)
    rng = np.random.default_rng(3)
    LOF = (68.2, 13.6)                                         # 罗弗敦，Europe/Oslo（10 月初 UTC+2）
    truth = {}
    k = 0
    for sc in range(6):
        local = datetime(2026, 10, 1, 10) + timedelta(hours=5 * sc)      # 手机钟点 = 挪威当地
        base = rng.normal(size=1152)
        for j in range(5):
            phone = j < 2
            loc = local + timedelta(minutes=(0, 1, -2, 1, 3)[j])
            if phone:
                b = jpeg(k, loc, *LOF)
            else:                                              # 相机：北京时间（当地 +6）再快 15 分钟，没 GPS、没时区标签
                b = jpeg(k, loc + timedelta(hours=6, minutes=15), make='Canon', model='Canon EOS R5', serial='TEST' + e2e.TAG)
            name = f'{e2e.TAG}_{"IMG" if phone else "CAM"}_{k:03d}.jpg'
            h, r, _ = upload(A, name, b); HS.append(h)
            meta = M.image_meta(__import__('PIL.Image', fromlist=['Image']).open(io.BytesIO(b)))
            ev, es = q8((base + 0.1 * rng.normal(size=1152)).astype(np.float32))
            # 模拟「早就分析过」的老照片：只有 taken（=EXIF 钟点）、GPS、向量，没有 ctime
            P.post('/api/pipe/result', {'h': h, 'aver': W.AVER, 'taken': meta['taken'], 'emb': ev, 'emb_scale': es,
                                        **({'lat': meta['lat'], 'lon': meta['lon']} if phone else {}), 'cam': meta.get('cam')})
            if not phone: truth[h] = loc.strftime('%Y-%m-%dT%H:%M:%S')
            k += 1
    I = {x['h']: x for x in A.get('/api/list').json()['items']}
    check('上传 30 个文件（12 张手机 + 18 张相机），相机照片现在显示的是北京钟点', all(I[h]['t'] != truth[h] for h in truth))

    w = W.Worker.__new__(W.Worker)
    w.api = W.Api(BASE, e2e.PIPE); w.cache = __import__('pathlib').Path(os.environ.get('TMPDIR', '/tmp'))
    n = w.backfill_clock()
    media = [m for m in w.api.get('/api/pipe/media') if m['h'] in set(HS)]
    check('backfill：从原件 EXIF 补上原始钟点 / 机身序列号 / 时间来源', n >= 30 and all(m.get('ctime') for m in media)
          and {m['tzsrc'] for m in media} == {'gps', 'none'} and all(m.get('cser') == 'TEST' + e2e.TAG for m in media if m['tzsrc'] == 'none'),
          f'补了 {n} 个')
    E = {}
    import base64
    for r in w.api.get('/api/pipe/embs'):
        if r['h'] in set(HS):
            v = np.frombuffer(base64.b64decode(r['vec']), dtype=np.int8).astype(np.float32) * r['scale']; E[r['h']] = v / np.linalg.norm(v)
    moved = w.align_clocks(media, E)
    I = {x['h']: x for x in A.get('/api/list').json()['items']}
    err = max(abs((datetime.fromisoformat(I[h]['t']) - datetime.fromisoformat(t)).total_seconds()) for h, t in truth.items())
    check('对齐后 18 张相机照片都换成挪威当地时间（误差 ≤ 5 分钟）', len(moved) == 18 and err <= 300, f'改了 {len(moved)} 张，最大误差 {err:.0f} 秒')
    phones = [h for h in HS if h not in truth]
    check('手机照片一张没动', all(h not in moved for h in phones))
    media = [m for m in w.api.get('/api/pipe/media') if m['h'] in set(HS)]
    again = w.align_clocks(media, E)
    check('再跑一遍（每次聚类都会跑）→ 一张都不改，不烧免费额度', again == {}, len(again))


def cleanup():
    r = Client(e2e.PIPE).post('/api/pipe/purge', {'hs': HS, 'users': [U]})
    check('收尾：测试文件和用户删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
