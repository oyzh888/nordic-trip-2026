#!/usr/bin/env python3
"""视频新版（H.264 + 调色）的端到端测试（本地）：真视频文件 → 本地相册 → GPU 端代码（worker.transcode_one）→ 查结果。

    python test/video_e2e.py http://localhost:8787 < /dev/null

四段测试片（都在 ffmpeg 里现做，见 make()）：
  clog3.mp4   像 R5 那样：Canon Log 3 / Cinema Gamut、10-bit 4:2:2 HEVC、MP4 品牌 CAEP —— 内容是标准彩条（知道「正确颜色」是什么）
  drone.mp4   像大疆：8-bit HEVC，带拍摄时间 / GPS / 音轨
  phone.mp4   普通 8-bit H.264（iPhone 经 Safari 传上来的就是这样）→ 不用转
  hlg.mp4     HDR HLG（新 iPhone 直接导出的 HDR 视频）
查：每段判对了没有、新版是 H.264、原片一个字节没动、Log 那段颜色真的回来了（和原始彩条比）、缩略图 / 720p 预览也换成了新颜色、
下载新版文件名是 .mp4、打包下载里是新版、元数据（拍摄时间 / GPS）还在。
"""
import io, os, subprocess, sys, time, zipfile
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pipeline'))
import e2e
from e2e import Client, check, results, upload

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
U = f'{e2e.TAG}-VID'
D = os.path.join(os.environ.get('TMPDIR', '/tmp'), f'vid-{e2e.TAG}')
HS = {}
X265 = ['-x265-params', 'pools=4:frame-threads=1:log-level=error']
W, H = 1280, 720


def bars():
    r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', f'smptehdbars=s={W}x{H}', '-frames:v', '1', '-vf', 'format=rgb48le',
                        '-f', 'rawvideo', '-'], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.uint16).reshape(H, W, 3).astype(np.float64) / 65535


def make():
    os.makedirs(D, exist_ok=True)
    ref = bars()
    # BT.709 显示值 → 线性 → Cinema Gamut → Canon Log 3（佳能公开公式，结果是「码值 / 1023」）
    lin = np.where(ref < 0.081, ref / 4.5, ((ref + 0.099) / 1.099) ** (1 / 0.45))
    def M(prim):
        xy = np.array(prim); X = xy[:, 0] / xy[:, 1]; Z = (1 - xy[:, 0] - xy[:, 1]) / xy[:, 1]; P = np.stack([X, np.ones(3), Z])
        w = np.array([0.3127 / 0.3290, 1, (1 - 0.3127 - 0.3290) / 0.3290]); return P * np.linalg.solve(P, w)
    cg = lin @ (np.linalg.inv(M([(0.74, 0.27), (0.17, 1.14), (0.08, -0.10)])) @ M([(0.64, 0.33), (0.30, 0.60), (0.15, 0.06)])).T
    with np.errstate(invalid='ignore'):
        log = np.where(cg <= 0.014, 1.9754798 * cg + 0.12512219, 0.36726845 * np.log10(np.maximum(cg, 0) * 14.98325 + 1) + 0.12240537)
    raw = (np.clip(log, 0, 1) * 65535).round().astype('<u2').tobytes()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb48le', '-s', f'{W}x{H}', '-r', '24', '-i', '-', '-t', '2',
                    '-vf', 'scale=out_color_matrix=bt709:out_range=pc,format=yuv422p10le', '-color_range', 'tv', '-c:v', 'libx265', *X265, '-crf', '12',
                    '-tag:v', 'hvc1', '-brand', 'CAEP', os.path.join(D, 'clog3.mp4')], input=raw * 48, check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1920x1080:r=30', '-f', 'lavfi', '-i', 'sine=f=440:r=48000', '-t', '2',
                    '-vf', 'format=yuv420p', '-c:v', 'libx265', *X265, '-crf', '26', '-tag:v', 'hvc1', '-c:a', 'aac',
                    '-metadata', 'creation_time=2026-10-02T13:17:26Z', '-metadata', 'location=+68.2000+013.6000/', os.path.join(D, 'drone.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30', '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    os.path.join(D, 'phone.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30', '-t', '2', '-vf', 'format=yuv420p10le',
                    '-c:v', 'libx265', *X265, '-crf', '22', '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc',
                    '-tag:v', 'hvc1', os.path.join(D, 'hlg.mp4')], check=True)
    return ref


def rgb(b, size=None):
    p = os.path.join(D, 'probe.bin'); open(p, 'wb').write(b)
    vf = 'scale=out_range=pc' + (f',scale={size[0]}:{size[1]}' if size else '') + ',format=rgb24'
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-frames:v', '1', '-vf', vf, '-f', 'rawvideo', '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).astype(float) / 255


def main():
    import worker as W_, video as V
    ref = make()
    A, P = Client(), Client(e2e.PIPE); A.login(U)
    names = {'clog3.mp4': f'{e2e.TAG}_MVI_0001.MP4', 'drone.mp4': f'{e2e.TAG}_DJI_0361.MP4', 'phone.mp4': f'{e2e.TAG}_IMG_7001.MOV', 'hlg.mp4': f'{e2e.TAG}_IMG_7002.MOV'}
    raw = {}
    for f, n in names.items():
        raw[f] = open(os.path.join(D, f), 'rb').read()
        h, r, _ = upload(A, n, raw[f], typ='video/mp4'); HS[f] = h
    check('四段视频原样上传完成', len(HS) == 4)
    todo = {t['h']: t for t in P.get('/api/pipe/transcode').json()}
    check('转码队列里有这四段（还没看过的视频）', all(h in todo for h in HS.values()), len(todo))

    w = W_.Worker.__new__(W_.Worker)
    w.api = W_.Api(BASE, e2e.PIPE); w.cache = __import__('pathlib').Path(D); (w.cache / 'o').mkdir(exist_ok=True)
    t0 = time.time()
    for f, h in HS.items():
        w.transcode_one(todo[h])
    check('GPU 端四段都处理完', True, f'{time.time() - t0:.1f}s')

    I = {x['h']: x for x in A.get('/api/list').json()['items']}
    want = {'clog3.mp4': 'clog3-cg', 'drone.mp4': 'transcode', 'hlg.mp4': 'hlg'}
    got = {f: I[h].get('gp') for f, h in HS.items()}
    check('判定：佳能 Log → 套 LUT · 大疆 HEVC → 只转码 · HDR HLG → 转普通亮度 · H.264 → 不用转',
          all(got[f] == p for f, p in want.items()) and got['phone.mp4'] is None and not I[HS['phone.mp4']].get('gs'), got)
    check('不用转的那段从队列里出去了（不会每分钟再看一遍）', HS['phone.mp4'] not in {t['h'] for t in P.get('/api/pipe/transcode').json()})

    for f in want:
        h = HS[f]
        g = A.get(f'/f/{h}/g'); d = A.get(f'/f/{h}/g?dl=1')
        p = os.path.join(D, 'g_' + f); open(p, 'wb').write(g.content)
        info, vs, aus = V.probe(p)
        o = A.get(f'/f/{h}/o').content
        cd = d.headers.get('content-disposition', '')
        check(f'{f}：新版是 8-bit H.264 BT.709、文件名 .mp4；原片一个字节没动',
              g.status_code == 200 and vs['codec_name'] == 'h264' and vs['pix_fmt'] == 'yuv420p' and vs.get('color_transfer') == 'bt709'
              and len(g.content) == I[h]['gs'] and o == raw[f] and names[f].rsplit('.', 1)[0] + '.mp4' in cd,
              f"{vs['codec_name']} {vs['pix_fmt']} {vs.get('color_transfer')} · {len(g.content) / 1e3:.0f} KB · {cd[-40:]}")
        if f == 'drone.mp4':
            tags = {k.lower(): v for k, v in (info['format'].get('tags') or {}).items()}
            check('drone.mp4：拍摄时间、GPS、音轨都还在', tags.get('creation_time', '').startswith('2026-10-02T13:17:26') and '+68.2' in tags.get('location', '') and aus is not None, tags)

    # Log 那段：颜色真的回来了
    h = HS['clog3.mp4']
    out = rgb(A.get(f'/f/{h}/g').content).reshape(H, W, 3)
    log = rgb(raw['clog3.mp4']).reshape(H, W, 3)
    ref8 = np.round(ref * 255) / 255
    sat = lambda a: float(np.mean(a.max(-1) - a.min(-1)))
    check('Log 那段颜色回来了：饱和度从灰蒙蒙恢复到接近原始彩条、和原始彩条的差变小',
          sat(out) > 0.8 * sat(ref8) and np.abs(out - ref8).mean() < 0.06 and np.abs(log - ref8).mean() > 0.15,
          f'饱和度 原始 {sat(ref8):.2f} · Log {sat(log):.2f} · 新版 {sat(out):.2f} · 和原始的差 {np.abs(out - ref8).mean():.3f}')
    t = A.get(f'/f/{h}/t').content; v = A.get(f'/f/{h}/v').content
    tv = rgb(t); vv = rgb(v)
    check('Log 那段的缩略图和 720p 预览也换成了新颜色（不再是灰的）', sat(tv.reshape(-1, 3)) > 0.2 and sat(vv.reshape(-1, 3)) > 0.2,
          f'缩略图饱和度 {sat(tv.reshape(-1, 3)):.2f} · 预览 {sat(vv.reshape(-1, 3)):.2f}')

    r = A.post('/api/zip', {'ids': [HS['clog3.mp4'], HS['phone.mp4']]}).json()
    z = zipfile.ZipFile(io.BytesIO(A.get(r['url'].replace('/photos', '', 1)).content))
    nm = sorted(os.path.basename(n) for n in z.namelist())
    inner = {os.path.basename(n): z.read(n) for n in z.namelist()}
    check('打包下载：视频用新版（.mp4），不用转的照旧是原片', nm == sorted([names['clog3.mp4'].rsplit('.', 1)[0] + '.mp4', names['phone.mp4']])
          and inner[names['phone.mp4']] == raw['phone.mp4'] and len(inner[names['clog3.mp4'].rsplit('.', 1)[0] + '.mp4']) == I[HS['clog3.mp4']]['gs'], nm)


def cleanup():
    P = Client(e2e.PIPE)
    r = P.post('/api/pipe/purge', {'hs': list(HS.values()), 'users': [U]})
    gone = all(P.get(f'/f/{h}/g').status_code == 404 for h in HS.values())
    check('收尾：测试视频、新版、用户全部删除', r.status_code == 200 and gone, r.text[:60])
    subprocess.run(['rm', '-rf', D])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
