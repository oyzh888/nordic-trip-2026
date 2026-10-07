#!/usr/bin/env python3
"""边选边传（本地，手机尺寸）：上传进行中「再选一批」按钮一直在；点它弹选择器，选中的排在正在传的后面一起传完；
按「手机准备用了多久 ÷ 张数」记下这台手机每张要几秒，提示「每批选多少张」。

    python test/ui_pickmore.py http://localhost:8787 < /dev/null
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results
from ui_upload_live import MAKE

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
U = f'{e2e.TAG}-PICK'
D = os.path.join(os.environ.get('TMPDIR', '/tmp'), f'pick-{e2e.TAG}')


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    os.makedirs(D, exist_ok=True)
    files = []
    for i in range(12):
        p = os.path.join(D, f'IMG_{8000 + i}.jpeg'); Image.new('RGB', (1600, 1200), (i * 20 % 255, 90, 160)).save(p, 'JPEG', quality=90); files.append(p)
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        ctx = br.new_context(**dev, locale='zh-CN'); pg = ctx.new_page()
        cdp = ctx.new_cdp_session(pg); cdp.send('Network.enable')
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        # 第一批：页面里现画 40 张、限速上行，保证「再选一批」时它还在传
        pg.evaluate(f"async () => {{ window.__a = await ({MAKE})([0, 40, Date.UTC(2026, 9, 3, 10), 60000]); }}")
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 20, 'downloadThroughput': -1, 'uploadThroughput': 0.1e6 / 8})
        pg.evaluate('() => __album.enqueue(window.__a)')
        pg.wait_for_selector('#pick-more:not([hidden])', timeout=10000)
        check('上传进行中，面板顶上一直有「再选一批」', pg.is_visible('#pick-more'))
        # 点它 → 弹选择器（和真手机一样，等几秒才交文件 = 手机在准备）
        with pg.expect_file_chooser() as fc:
            pg.click('#pick-more')
        time.sleep(6)
        fc.value.set_files(files)
        still = pg.evaluate("() => __album.UQ.filter(t => t.f.name.startsWith('LIVE_') && t.state !== 'ok').length")
        check('第二批进来时第一批还在传（两批重叠，不用等）', still > 0, f'第一批还剩 {still} 张')
        cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1})
        pg.wait_for_function("() => __album.UQ.length === 52 && __album.UQ.every(t => t.state === 'ok' || t.state === 'dup')", timeout=120000)
        check('两批 52 张都传完', True)
        prep = pg.evaluate('() => Number(localStorage.np_prep)')
        check('记下了这台手机每张要准备几秒（6 秒 ÷ 12 张 ≈ 0.5 秒）', 0.4 < prep < 0.8, f'{prep:.2f} 秒/张')
        pg.evaluate('() => document.querySelector("#upsheet").hidden = false'); pg.wait_for_timeout(300)   # 面板本来就开着（传的时候自动打开）
        tip = pg.evaluate("() => { const e = document.querySelector('#pick-tip'); return e && !e.hidden ? e.textContent : '' }")
        check('上传面板里提示「每批选多少张」（0.5 秒/张 → 每批 40 张左右，只等 ~20 秒）', '每批选 40 张' in tip, tip[:80])
        check('传完了「再选一批」就收起来（大框就是选照片）', not pg.is_visible('#pick-more'))
        br.close()


def cleanup():
    P = Client(e2e.PIPE); L = Client(); L.login(U)
    me = L.get('/api/me').json()['user']['id']
    P.post('/api/pipe/purge', {'hs': [x['h'] for x in L.get('/api/list').json()['items'] if me in (x.get('u') or [])], 'users': [U]})
    import shutil; shutil.rmtree(D, ignore_errors=True)


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
