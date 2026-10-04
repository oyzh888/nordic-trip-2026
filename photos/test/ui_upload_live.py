#!/usr/bin/env python3
"""一边上传、一边浏览 / 看大图：上传不打断用户正在做的事（手机尺寸，真浏览器）。

    python test/ui_upload_live.py http://localhost:8787 < /dev/null

先传 30 张旧照片；滚到中间、记下屏幕上那张照片的位置；然后在后台再传 160 张「更新的」照片
（时间线新的在前 → 它们会插在最上面）。量：
  1. 一边传，正在看的那张照片在屏幕上挪了多少像素（以前每传完一张整页重画，会被往下推）
  2. 顶上有没有冒出「↑ N 张新照片」
  3. 传的同时开着大图按「下一张」：是不是还是原来的下一张（以前按位置算，新照片插进来就跳错）
  4. 传完、关掉大图停手后，列表补齐（200 张）
只在本地跑；测试图是页面里现画的，结束时连同测试用户一起删掉。
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
U = f'{e2e.TAG}-LIVE'
OUT = os.path.join(e2e.HERE, 'out', 'ui')

MAKE = """async ([from, n, t0, step]) => {
  const out = [];
  for (let i = from; i < from + n; i++) {
    const c = document.createElement('canvas'); c.width = 640; c.height = 480; const g = c.getContext('2d');
    g.fillStyle = `hsl(${i * 47 % 360},45%,45%)`; g.fillRect(0, 0, 640, 480);
    g.fillStyle = '#fff'; g.font = '64px sans-serif'; g.fillText('LIVE ' + i, 40, 120);
    const b = await new Promise(r => c.toBlob(r, 'image/jpeg', 0.85));
    out.push(new File([b], `LIVE_${String(i).padStart(4, '0')}.jpg`, { type: 'image/jpeg', lastModified: t0 + (i - from) * step }));
  }
  return out;
}"""


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        ctx = br.new_context(**dev, locale='zh-CN'); pg = ctx.new_page()
        cdp = ctx.new_cdp_session(pg); cdp.send('Network.enable')
        net = lambda mbps: cdp.send('Network.emulateNetworkConditions', {'offline': False, 'latency': 20, 'downloadThroughput': -1,
                                                                        'uploadThroughput': mbps * 1e6 / 8 if mbps else -1})
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        pg.evaluate("() => { __album.S.quick = 'mine'; }")              # 只看自己传的，不受本地库里别的数据影响

        # 1) 先传 30 张「旧」照片（9 月 25 日），传完
        pg.evaluate(f"async () => {{ window.__a = await ({MAKE})([0, 30, Date.UTC(2026, 8, 25, 10), 60000]); __album.enqueue(window.__a); }}")
        pg.wait_for_function("() => __album.UQ.length === 30 && __album.UQ.every(t => t.state === 'ok' || t.state === 'dup')", timeout=120000)
        pg.evaluate("() => { const s = document.querySelector('#upsheet'); if (s) s.hidden = true; return __album.refresh(true); }")
        pg.wait_for_timeout(500)
        n0 = pg.locator('#grid .tl').count()
        check('先传的 30 张都在时间线上', n0 == 30, n0)

        # 2) 滚到中间，记下屏幕顶上那张
        pg.evaluate("() => { const el = document.querySelectorAll('#grid .tl')[15]; scrollTo(0, el.getBoundingClientRect().top + scrollY - 200); }")
        pg.wait_for_timeout(3000)                                       # 停手，让 busy() 过去
        a0 = pg.evaluate("""() => { for (const el of document.querySelectorAll('#grid .tl')) { const r = el.getBoundingClientRect();
            if (r.bottom > 60) return { h: el.dataset.h, top: r.top }; } }""")

        # 3) 后台再传 40 张「更新的」（10 月 3 日）→ 会排在最上面
        pg.evaluate(f"async () => {{ window.__b = await ({MAKE})([1000, 160, Date.UTC(2026, 9, 3, 10), 60000]); }}")
        net(0.25)                                                       # 上行限到 0.25 Mbps：测试图很小（160 张共 ~1 MB），不限的话检查时早传完了
        pg.evaluate("() => __album.enqueue(window.__b)")
        pg.evaluate("() => { const s = document.querySelector('#upsheet'); if (s) s.hidden = true; }")
        # 上传期间后台刷新最多 10 秒一次 → 等到「↑ N 张新照片」冒出来（= 已经经过一次后台刷新），趁还在传的时候量
        pg.wait_for_function("() => { const p = document.querySelector('#newpill'); return p && !p.hidden; }", timeout=30000)
        still = pg.evaluate("() => __album.UQ.some(t => t.state === 'active' || t.state === 'queued')")
        drift = pg.evaluate(f"""() => {{ const el = document.querySelector('#grid .tl[data-h="{a0['h']}"]');
            return el ? el.getBoundingClientRect().top - {a0['top']} : null; }}""")
        n_mid = pg.locator('#grid .tl').count()
        check('一边上传一边看：正在看的那张照片一动不动（上传期间不重画时间线）', still and drift is not None and abs(drift) <= 4 and n_mid == 30,
              f'还在传={still} · 挪了 {drift} 像素 · 时间线 {n_mid} 张')
        pill = pg.evaluate("() => { const p = document.querySelector('#newpill'); return p && !p.hidden ? p.textContent : '' }")
        check('顶上提示「↑ N 张新照片」，而不是把画面推走', '张新照片' in pill, pill)
        pg.screenshot(path=os.path.join(OUT, 'live-upload-pill.png'))
        net(0)                                                          # 放开网速，等这一批传完、看最后那一次重画
        pg.wait_for_function("() => !__album.UQ.some(t => t.state === 'active' || t.state === 'queued')", timeout=120000)
        pg.wait_for_function("() => document.querySelectorAll('#grid .tl').length > 30", timeout=30000)
        pg.wait_for_timeout(1500)
        drift2 = pg.evaluate(f"""() => {{ const el = document.querySelector('#grid .tl[data-h="{a0['h']}"]');
            return el ? el.getBoundingClientRect().top - {a0['top']} : null; }}""")
        check('全部传完、时间线补画那一下：正在看的那张照片还是一动不动', drift2 is not None and abs(drift2) <= 4, f'挪了 {drift2} 像素')
        pg.click('#newpill'); pg.wait_for_timeout(1200)
        n_pill = pg.locator('#grid .tl').count()
        check('点「↑ N 张新照片」→ 立刻显示新照片、回到顶上', n_pill > 30 and pg.evaluate('scrollY') < 50, f'{n_pill} 张')
        pg.evaluate(f"() => {{ const el = document.querySelector('#grid .tl[data-h=\"{a0['h']}\"]'); scrollTo(0, el.getBoundingClientRect().top + scrollY - {a0['top']}); }}")

        # 4) 开着大图、上传还在继续：「下一张」还是原来那张
        pg.wait_for_timeout(2600)
        i = pg.evaluate(f"() => __album.S.view.findIndex(x => x.h === '{a0['h']}')")
        nxt = pg.evaluate(f"() => __album.S.view[{i} + 1].h")
        pg.locator(f'#grid .tl[data-h="{a0["h"]}"]').click(); pg.wait_for_selector('#lb:not([hidden])')
        pg.evaluate(f"async () => {{ window.__c = await ({MAKE})([2000, 10, Date.UTC(2026, 9, 3, 12), 60000]); __album.enqueue(window.__c); }}")
        pg.wait_for_function("() => __album.UQ.filter(t => t.state === 'ok').length >= 198", timeout=120000)
        pg.evaluate('() => __album.refresh(true)')                       # 强制刷新一次：最坏情况，列表就在大图底下变了
        cur = pg.evaluate("() => __album.S.view[__album.S.lb].h")
        pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(300)        # 手机尺寸下箭头按钮是隐藏的（靠左右滑），用键盘的「下一张」
        got = pg.evaluate("() => __album.S.view[__album.S.lb].h")
        check('大图开着时列表变了：还停在同一张，「下一张」也还是原来那张', cur == a0['h'] and got == nxt, f'{cur == a0["h"]} / {got == nxt}')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(500)

        # 5) 全部传完、停手后补齐
        pg.wait_for_function("() => __album.UQ.every(t => t.state === 'ok' || t.state === 'dup')", timeout=120000)
        pg.wait_for_timeout(9000)
        n1 = pg.locator('#grid .tl').count()
        check('传完、停手几秒后时间线补齐（200 张）', n1 == 200, n1)
        check('整个过程没有 JS 报错', not errs, errs[:2])
        br.close()


def cleanup():
    P = Client(e2e.PIPE)
    L = Client(); L.login(U)
    me = L.get('/api/me').json()['user']['id']
    hs = [x['h'] for x in L.get('/api/list').json()['items'] if me in (x.get('u') or [])]
    r = P.post('/api/pipe/purge', {'hs': hs, 'users': [U]})
    check(f'收尾：{len(hs)} 张测试图和测试用户删除', r.status_code == 200, r.text[:60])


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
