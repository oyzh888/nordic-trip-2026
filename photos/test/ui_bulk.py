#!/usr/bin/env python3
"""一次选几百张的上传压力测试：手机尺寸 + CPU 降速 4 倍（模拟 iPhone），量三件事 ——

1. 传 N 张时页面卡不卡：页面里每 50 ms 打一次点，记录最长一次被耽误了多久（主线程被占住的时间）
2. 重选同一批（iPhone 每次导出 lastModified 都是新的，本机缓存认不出来）→ 多久全部「秒传」完
3. 传到一半页面被杀（模拟 iOS 内存不够把标签页关掉）→ 重新打开有没有提示、重选后只补没传的

    python test/ui_bulk.py http://localhost:8787 [N=250]

测试图是页面里用 canvas 现画的（按序号固定随机种子，重画出来字节一样），结束时连同测试用户一起删掉。
只在本地跑 —— 线上有真人在用，不往线上灌几百张测试图。
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
N = int(sys.argv[2]) if len(sys.argv) > 2 else 250
U = f'{e2e.TAG}-BULK'
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'

MAKE = """async ([from, n, w, h]) => {
  const out = [];
  for (let i = from; i < from + n; i++) {
    let s = i * 2654435761 >>> 0; const rnd = () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296;
    const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
    g.fillStyle = `hsl(${i * 37 % 360},40%,40%)`; g.fillRect(0, 0, w, h);
    for (let k = 0; k < 160; k++) { g.fillStyle = `hsl(${rnd() * 360},60%,${30 + rnd() * 40}%)`; g.fillRect(rnd() * w, rnd() * h, rnd() * w / 4, rnd() * h / 4); }
    g.fillStyle = '#fff'; g.font = '80px sans-serif'; g.fillText('BULK ' + i, 60, 140);
    const b = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.9));
    out.push(new File([b], `IMG_${String(i).padStart(4, '0')}.jpeg`, { type: 'image/jpeg', lastModified: Date.now() }));
  }
  window.__bulk = (window.__bulk || []).concat(out);
  return out.reduce((a, f) => a + f.size, 0);
}"""
# 主线程探针：每 50 ms 一次，被耽误的部分就是页面「卡住」的时间
LAG = """() => { window.__lag = { max: 0, n200: 0 }; let t = performance.now();
  clearInterval(window.__lagT); window.__lagT = setInterval(() => { const now = performance.now(), d = now - t - 50; t = now;
    if (d > window.__lag.max) window.__lag.max = d; if (d > 200) window.__lag.n200++; }, 50); }"""
KEPT = """() => new Promise(r => { const q = indexedDB.open('np-upload', 1); q.onupgradeneeded = () => q.result.createObjectStore('files');
  q.onsuccess = () => { const c = q.result.transaction('files').objectStore('files').count(); c.onsuccess = () => r(c.result); }; q.onerror = () => r(-1); })"""
STATE = """() => { const q = __album.UQ, c = s => q.filter(t => t.state === s).length;
  return { n: q.length, ok: c('ok'), dup: c('dup'), failed: c('failed'), left: c('queued') + c('active'), lag: window.__lag }; }"""


def main():
    from playwright.sync_api import sync_playwright
    P = Client(e2e.PIPE)
    print(f'批量上传测试 {BASE} · {N} 张 · 手机尺寸 + CPU 降速 4 倍\n')
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        ctx = br.new_context(**dev, locale='zh-CN')
        pg = ctx.new_page()
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(BASE + '/photos/#k=' + e2e.PASS)
        pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)

        def slow(page):
            cdp = ctx.new_cdp_session(page); cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})

        def run(label, files_js, timeout=900):
            pg.evaluate(LAG)
            t0 = time.time()
            pg.evaluate(files_js)
            while time.time() - t0 < timeout:
                st = pg.evaluate(STATE)
                if st['n'] and not st['left']: break
                time.sleep(0.5)
            st = pg.evaluate(STATE); st['s'] = round(time.time() - t0, 1)
            print(f"  {label}: {st['s']} 秒 · 完成 {st['ok']} · 秒传 {st['dup']} · 失败 {st['failed']} · "
                  f"主线程最长卡 {st['lag']['max']:.0f} ms · 卡超过 200 ms 的次数 {st['lag']['n200']}")
            return st

        mb = pg.evaluate(MAKE, [0, N, 1600, 1200]) / 2 ** 20
        print(f'  画好 {N} 张测试图，共 {mb:.0f} MB')
        slow(pg)
        a = run(f'第一次传 {N} 张', '() => __album.enqueue(window.__bulk)')
        check(f'{N} 张全部传完、没有失败', a['ok'] == N and not a['failed'], a)
        check('传的过程中页面不卡（主线程最长被占 < 1 秒）', a['lag']['max'] < 1000, f"{a['lag']['max']:.0f} ms")

        # 2) 重选同一批：同样的字节、同样的名字，但 lastModified 是新的（iPhone 每次导出都这样）
        pg.reload(); pg.wait_for_selector('#app:not([hidden])', timeout=15000); slow(pg)
        pg.evaluate(MAKE, [0, N, 1600, 1200])
        b = run(f'重选同一批 {N} 张', '() => __album.enqueue(window.__bulk)', timeout=300)
        check('重选同一批 → 全部秒传，不用一张张读文件', b['dup'] == N and b['s'] < 15, f"{b['s']} 秒")

        # 3) 传到一半页面被杀
        M = 40
        pg.reload(); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        pg.evaluate(MAKE, [N, M, 1600, 1200]); slow(pg)
        # 上行限到 2 Mbps：现在传得很快，不限的话等到第 8 张传完时 40 张早就全完了，测不到「传一半被杀」
        cdp = ctx.new_cdp_session(pg); cdp.send('Network.enable')
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 20, 'downloadThroughput': -1, 'uploadThroughput': 2e6 / 8})
        pg.evaluate('() => __album.enqueue(window.__bulk)')
        pg.wait_for_function('() => __album.UQ.filter(t => t.state === "ok").length >= 8', timeout=120000)
        pg.wait_for_timeout(600)                                   # 让本机缓存落盘（攒 400 ms 写一次）
        done1 = pg.evaluate(STATE)['ok']
        kept = pg.evaluate(KEPT)
        check('传到一半：还没传的文件已经存进浏览器（IndexedDB）', kept >= M - done1 - 6 and kept > 0, f'已传 {done1} · 浏览器里存着 {kept} 个')
        pg.reload(); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        # 不重选：页面自己从浏览器里把文件拿回来接着传（2 Mbps 还在限着）
        pg.wait_for_function('() => __album.UQ.length > 0', timeout=15000)
        n_restored = pg.evaluate('() => __album.UQ.length')
        pg.screenshot(path=os.path.join(e2e.HERE, 'out', 'ui', 'bulk-resume.png'))
        check('页面被杀后重新打开 → 不用重选，自动接着传', n_restored >= M - done1 - 6, f'自动恢复 {n_restored} 个（被杀前已传完 {done1} 个）')
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        pg.wait_for_function("() => __album.UQ.every(t => t.state === 'ok' || t.state === 'dup' || t.state === 'failed')", timeout=300000)
        c = pg.evaluate(STATE)
        pg.evaluate("() => __album.refresh(true)")
        mine = pg.evaluate(f"() => __album.S.data.items.filter(x => x.n.startsWith('IMG_') && Number(x.n.slice(4, 8)) >= {N}).length")
        check(f'这 {M} 张最后全在相册里，没有失败、没有重复', mine == M and not c['failed'], f'相册里 {mine} 张 · {c}')
        pg.wait_for_timeout(1500)
        check('传完之后浏览器里存的副本全删了（不长期占手机空间）', pg.evaluate(KEPT) == 0, pg.evaluate(KEPT))
        check('补完之后「没传完」的提示消失', not pg.is_visible('#resume-hint'))
        check('整个过程没有 JS 报错', not errs, errs[:3])
        br.close()


def cleanup():
    P = Client(e2e.PIPE)
    L = Client(); L.login(U)
    me = L.get('/api/me').json()['user']['id']
    hs = [x['h'] for x in L.get('/api/list').json()['items'] if me in (x.get('u') or [])]
    r = P.post('/api/pipe/purge', {'hs': hs, 'users': [U]})
    check(f'收尾：{len(hs)} 张测试图和测试用户全部删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    json.dump({'results': results}, open(os.path.join(e2e.HERE, 'out', 'bulk-local.json'), 'w'), ensure_ascii=False, indent=1)
    sys.exit(0 if ok == len(results) else 1)
