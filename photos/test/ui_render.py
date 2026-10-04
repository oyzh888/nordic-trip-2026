#!/usr/bin/env python3
"""时间线渲染稳定性（本地）：假装相册里有 N 张（拦截 /api/list 返回合成数据，缩略图统一给一张小图），量
  1. 什么都没变时刷新：要花多久、重建了几个缩略图元素（应该 0 个 —— 以前每次整片重建，Safari 来不及画就「闪」）
  2. 只有一张变了（比如刚补上缩略图）：只换那一个元素
  3. 开着大图时底下的时间线藏起来（Safari 不再把几千张「透」到大图上）、关掉后滚动位置还在

    python test/ui_render.py http://localhost:8787 [N=5000] < /dev/null
"""
import io, json, os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
U = f'{e2e.TAG}-RND'


def fake_list(n, ver, me, bump=None):
    rnd = random.Random(1)
    items = []
    for i in range(n):
        day = 25 + i * 12 // n
        h = f'{i:064x}'
        items.append({'h': h, 'k': 'i', 'n': f'IMG_{i:05d}.jpeg', 's': 3_000_000, 't': f'2026-09-{min(day, 30):02d}T{8 + i % 12:02d}:{i % 60:02d}:00',
                      'c': 1790000000000 + i * 1000, 'w': 4032, 'hh': 3024, 'f': 3 if bump != i else 0, 'a': 1, 'pl': '冰岛', 'cap': '风景', 'tg': None,
                      'b': None, 'bc': 1, 'sc': None, 'u': [me], 'p': [], 'nf': 0, 'cam': 'Apple iPhone 15 Pro Max', 'q': rnd.random(),
                      'mo': None, 'pn': 0, 'la': 64.1, 'lo': -21.9})
    return {'ver': ver, 'items': items, 'users': [{'id': me, 'name': U}], 'persons': [], 'scenes': [], 'moments': [], 'pipe': True, 'ai': []}


def main():
    from playwright.sync_api import sync_playwright
    from PIL import Image
    b = io.BytesIO(); Image.new('RGB', (360, 360), (80, 120, 160)).save(b, 'JPEG'); thumb = b.getvalue()
    A = Client(); A.login(U); me = A.get('/api/me').json()['user']['id']
    state = {'ver': 1000, 'bump': None}
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        ctx = br.new_context(viewport={'width': 1440, 'height': 900}, locale='zh-CN'); pg = ctx.new_page()
        pg.route('**/photos/api/list', lambda r: r.fulfill(status=200, content_type='application/json', body=json.dumps(fake_list(N, state['ver'], me, state['bump']))))
        pg.route('**/photos/f/**', lambda r: r.fulfill(status=200, content_type='image/jpeg', body=thumb))
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=30000)
        pg.wait_for_function(f"() => document.querySelectorAll('#grid .tl').length === {N}", timeout=60000)
        mark = "() => { document.querySelectorAll('#grid .tl').forEach(e => e.__m = 1); }"
        count_new = "() => [...document.querySelectorAll('#grid .tl')].filter(e => !e.__m).length"
        timed = "async () => { const t = performance.now(); await __album.refresh(true); await new Promise(r => requestAnimationFrame(() => setTimeout(r))); return performance.now() - t; }"

        pg.evaluate(mark); state['ver'] += 1
        dt = pg.evaluate(timed); new = pg.evaluate(count_new)
        check(f'{N} 张、什么都没变时刷新：一个缩略图元素都不重建', new == 0, f'重建 {new} 个 · 用时 {dt:.0f} ms')

        pg.evaluate(mark); state['ver'] += 1; state['bump'] = 1234
        dt2 = pg.evaluate(timed); new = pg.evaluate(count_new)
        check('只有一张变了：只换那一个元素', new == 1, f'重建 {new} 个 · 用时 {dt2:.0f} ms')
        state['bump'] = None

        pg.evaluate("() => scrollTo(0, 6000)"); pg.wait_for_timeout(300)
        trace = [('scrollTo 后', pg.evaluate('scrollY'))]
        pg.wait_for_timeout(1500); trace.append(('等 1.5 秒', pg.evaluate('scrollY')))
        y0 = pg.evaluate('scrollY')
        pg.evaluate("() => { const el = [...document.querySelectorAll('#grid .tl')].find(e => e.getBoundingClientRect().top > 100); el.click(); }")
        pg.wait_for_selector('#lb:not([hidden])'); trace.append(('开大图后', pg.evaluate('scrollY')))
        vis = pg.evaluate("() => getComputedStyle(document.querySelector('#app')).visibility")
        check('开着大图时底下的时间线藏起来（Safari 不用再画几千张）', vis == 'hidden', vis)
        pg.keyboard.press('Escape'); trace.append(('Esc 刚按', pg.evaluate('scrollY'))); pg.wait_for_timeout(300); trace.append(('关后 0.3 秒', pg.evaluate('scrollY')))
        print('  滚动位置:', trace)
        vis2 = pg.evaluate("() => getComputedStyle(document.querySelector('#app')).visibility"); y1 = pg.evaluate('scrollY')
        check('关掉大图：时间线回来、滚动位置没丢', vis2 == 'visible' and abs(y1 - y0) < 5, f'{y0} → {y1}')
        rendered = pg.evaluate("() => [...document.querySelectorAll('#grid .grp')].filter(g => g.querySelector('.tl').getBoundingClientRect().height > 0 && g.getBoundingClientRect().bottom > -2000 && g.getBoundingClientRect().top < innerHeight + 2000).length")
        total_g = pg.evaluate("() => document.querySelectorAll('#grid .grp').length")
        print(f'  分组 {total_g} 个，屏幕附近 {rendered} 个')
        br.close()


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
