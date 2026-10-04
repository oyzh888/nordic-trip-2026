#!/usr/bin/env python3
"""手机上传速度：慢在哪一段。iPhone 尺寸 + CPU 降速（模拟手机）+ 可选限速上行，传 N 张 1200 万像素 JPEG，
读每个文件各阶段用时（app.js 里 runTask 记的 t.tm：fp 算指纹 · init 和相册对一下 · net 传字节 · thumb 等缩略图）。

    python test/ui_speed.py http://localhost:8787 [N=30] [CPU 降速倍数=4] [上行 Mbps=0 不限] < /dev/null

只在本地跑；测试图是页面里现画的，结束时连同测试用户一起删掉。
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30
CPU = float(sys.argv[3]) if len(sys.argv) > 3 else 4
UP = float(sys.argv[4]) if len(sys.argv) > 4 else 0
U = f'{e2e.TAG}-SPD'

# 4032×3024（iPhone 主摄 1200 万像素），画面有细节（不然 JPEG 压得太小，不像真照片）
MAKE = """async ([n]) => {
  const out = [], W = 4032, H = 3024;
  const c = document.createElement('canvas'); c.width = W; c.height = H; const g = c.getContext('2d');
  const s = document.createElement('canvas'); s.width = W / 4; s.height = H / 4; const q = s.getContext('2d');
  for (let i = 0; i < n; i++) {
    const im = q.createImageData(W / 4, H / 4);
    for (let k = 0; k < im.data.length; k += 4) { const v = (k * 7 + i * 131) % 255; im.data[k] = v; im.data[k + 1] = (v * 3 + Math.random() * 90) % 255; im.data[k + 2] = Math.random() * 255; im.data[k + 3] = 255; }
    q.putImageData(im, 0, 0); g.imageSmoothingEnabled = true; g.drawImage(s, 0, 0, W, H);
    for (let k = 0; k < 400; k++) { g.fillStyle = `hsl(${Math.random() * 360},50%,50%)`; g.fillRect(Math.random() * W, Math.random() * H, 40 + Math.random() * 300, 40 + Math.random() * 300); }
    const b = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.92));
    out.push(new File([b], `IMG_${9000 + i}.jpeg`, { type: 'image/jpeg', lastModified: Date.now() }));
  }
  window.__f = out; return out.reduce((a, f) => a + f.size, 0);
}"""


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        ctx = br.new_context(**dev, locale='zh-CN'); pg = ctx.new_page()
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        mb = pg.evaluate(MAKE, [N]) / 2 ** 20
        reqs = []                                                       # 记每个请求发出 / 完成的时间：缩略图必须在所有上传完成之后才开始
        pg.on('request', lambda r: reqs.append(('send', r.url, time.time())))
        pg.on('requestfinished', lambda r: reqs.append(('done', r.url, time.time())))
        cdp = ctx.new_cdp_session(pg)
        cdp.send('Emulation.setCPUThrottlingRate', {'rate': CPU})
        if UP:
            cdp.send('Network.enable')
            cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 40, 'downloadThroughput': 50e6 / 8, 'uploadThroughput': UP * 1e6 / 8})
        t0 = time.time()
        pg.evaluate('() => __album.enqueue(window.__f)')
        pg.wait_for_function("() => __album.UQ.length && __album.UQ.every(t => t.state === 'ok' || t.state === 'dup' || t.state === 'failed')", timeout=900000)
        dt = time.time() - t0
        tms = pg.evaluate("() => __album.UQ.map(t => ({ state: t.state, size: t.f.size, ...(t.tm || {}) }))")
        ok = [t for t in tms if t['state'] == 'ok']
        avg = lambda k: sum(t.get(k, 0) for t in ok) / max(1, len(ok))
        net = f'上行 {UP:g} Mbps' if UP else '网络不限速'
        print(f'{N} 张 · {mb:.0f} MB · CPU 降速 {CPU:g} 倍 · {net}：{dt:.1f} 秒 · 每张 {dt / N:.2f} 秒 · {mb / dt:.1f} MB/s')
        print(f'  每张平均（毫秒）：算指纹 {avg("fp"):.0f} · 和相册对一下 {avg("init"):.0f} · 传字节 {avg("net"):.0f} · 传完还在等缩略图 {avg("thumb"):.0f} · 一共 {avg("total"):.0f}')
        check(f'{N} 张都传完', len(ok) == N, len(ok))
        pg.wait_for_timeout(1500)
        logs = [l for l in Client(e2e.PIPE).get('/api/pipe/uplog?limit=20').json() if l.get('name') == U]
        j = logs[0]['j'] if logs else {}
        check('这一批的用时记到了服务端（一批一行）', len(logs) == 1 and j.get('n') == N and j.get('ok') == N and j.get('upMs') and j.get('kinds') == {'jpeg': N},
              {'rows': len(logs), 'all': [(l['id'], l.get('name'), l['j'].get('n')) for l in Client(e2e.PIPE).get('/api/pipe/uplog?limit=4').json()], **{k: j.get(k) for k in ('n', 'ok', 'upMs', 'kinds')}})
        pg.wait_for_function(f"() => [...__album.S.byH.values()].length >= {N}", timeout=30000)
        t_end = time.time() + 60
        while time.time() < t_end and sum(1 for k, u, _ in reqs if k == 'done' and '/upload/aux' in u) < 2 * N:
            pg.wait_for_timeout(500)
        last_up = max(t for k, u, t in reqs if k == 'done' and '/upload/complete' in u)
        aux = sorted(t for k, u, t in reqs if k == 'send' and '/upload/aux' in u)
        check('后处理和上传完全分开：缩略图请求全部在最后一个文件传完之后才发', aux and aux[0] >= last_up,
              f'缩略图 {len(aux)} 个请求，第一个在最后一个上传完成后 {(aux[0] - last_up) if aux else 0:.2f} 秒')
        check('缩略图最后都补齐了（每张 2 个：缩略图 + 预览）', len(aux) >= 2 * N, len(aux))
        last = pg.evaluate("() => { const e = document.querySelector('#up-last'); return e && !e.hidden ? e.textContent : '' }")
        check('上传面板里显示「上一批：上传用了多久、多少 Mbps」', '上传' in last and 'Mbps' in last, last)
        json.dump({'n': N, 'mb': mb, 'cpu': CPU, 'up': UP, 'sec': dt, 'tm': tms}, open(os.path.join(e2e.HERE, 'out', f'speed-{CPU:g}x-{UP:g}.json'), 'w'))
        br.close()


def cleanup():
    P = Client(e2e.PIPE); L = Client(); L.login(U)
    me = L.get('/api/me').json()['user']['id']
    hs = [x['h'] for x in L.get('/api/list').json()['items'] if me in (x.get('u') or [])]
    P.post('/api/pipe/purge', {'hs': hs, 'users': [U]})


if __name__ == '__main__':
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    sys.exit(0 if all(r[1] for r in results) else 1)
