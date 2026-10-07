#!/usr/bin/env python3
"""相机卡里直接选 RAW（本地，手机尺寸，真 RAW 样片）：
  1. 默认「转成 JPEG 再传」：CR3 / NEF 传上去的是相机内嵌的全尺寸 JPEG（几 MB），拍摄时间 / 机身对；浏览器自己做好缩略图
  2. 内嵌 JPEG 太小的（松下 RW2 只有 1920 宽）→ 原样传 RAW，那一行写明原因
  3. 相机 RAW+JPEG 拍的（同名 .CR2 和 .JPG 都选了）→ RAW 跳过，只传 JPEG
  4. 同一批再选一次 → 全部秒传（转出来的字节每次一样）
  5. 切到「原样传 RAW」→ 传的是原片
  6. 这一批的转换统计记进了上传日志

    python test/ui_raw.py http://localhost:8787 < /dev/null      # 样片在 $RAW_SAMPLES（默认 /mnt/localssd/raw-samples）
"""
import os, shutil, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client, check, results

BASE = e2e.BASE
assert 'localhost' in BASE or '127.0.0.1' in BASE, '只在本地跑'
SET = os.environ.get('RAW_SAMPLES', '/mnt/localssd/raw-samples')
U = f'{e2e.TAG}-URAW'
D = os.path.join(os.environ.get('TMPDIR', '/tmp'), f'uraw-{e2e.TAG}')
PICK = {'IMG_4241.CR3': 'Canon_EOS_R6_Mark_III__IMG_4241.CR3', 'DSC_0750.NEF': 'Z_6__DSC_0750.NEF',
        'P1047510.RW2': 'DC-S5__P1047510.RW2', 'B13A0729.CR2': 'EOS_5D_Mark_IV__B13A0729.CR2'}


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(D, exist_ok=True)
    for n, src in PICK.items():
        dst = os.path.join(D, n)
        if not os.path.exists(dst): os.link(os.path.join(SET, src), dst) if os.stat(SET).st_dev == os.stat(D).st_dev else shutil.copy(os.path.join(SET, src), dst)
    open(os.path.join(D, 'B13A0729.JPG'), 'wb').write(e2e.jpeg((30, 90, 160), 'camera-jpeg', (1600, 1067)))   # 相机同时出的那张 JPEG
    files = [os.path.join(D, n) for n in sorted(os.listdir(D))]
    L = Client(); L.login(U); me = L.get('/api/me').json()['user']['id']
    mine = lambda: {x['n']: x for x in L.get('/api/list').json()['items'] if me in x['u']}
    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        ctx = br.new_context(**dev, locale='zh-CN'); pg = ctx.new_page()
        errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(BASE + '/photos/#k=' + e2e.PASS); pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U); pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        check('默认是「转成 JPEG 再传」', pg.evaluate("() => document.querySelector('input[name=rawm][value=jpeg]').checked"))
        done = "() => __album.UQ.length && __album.UQ.every(t => ['ok', 'dup', 'failed'].includes(t.state))"
        t0 = time.time()
        pg.set_input_files('#file', files)
        toast = pg.text_content('#toast') or ''
        pg.wait_for_function(done, timeout=300000); dt = time.time() - t0
        rows = pg.evaluate("() => __album.UQ.map(t => ({ n: t.f.name, raw: t.raw && t.raw.name, state: t.state, msg: t.msg, size: t.f.size }))")
        print('  ', *[f"{r['n']} {r['state']} {r['size'] / 1e6:.1f} MB · {r['msg']}" for r in rows], sep='\n   ')
        check('选的时候就提示：RAW 先取 JPEG 再传、同名 JPEG 的那张 RAW 跳过', '取出相机里的 JPEG' in toast and '跳过' in toast, toast[:120])
        m = mine()
        sz = sum(r['size'] for r in rows); raw_sz = sum(os.path.getsize(f) for f in files)
        check('CR3 / NEF 传上去的是 JPEG（名字 .JPG、几 MB）', 'IMG_4241.JPG' in m and 'DSC_0750.JPG' in m and m['IMG_4241.JPG']['s'] < 8e6 and 'IMG_4241.CR3' not in m,
              f'选了 {raw_sz / 1e6:.0f} MB → 实际传 {sz / 1e6:.0f} MB · {dt:.1f}s')
        c = m.get('IMG_4241.JPG', {})
        check('拍摄时间 / 机身是 RAW 里的（不是文件修改时间）', c.get('t') == '2026-01-22T15:41:04' and c.get('cam') == 'Canon EOS R6 Mark III', (c.get('t'), c.get('cam')))
        rw = next((r for r in rows if r['n'] == 'P1047510.RW2'), {})
        check('内嵌 JPEG 太小的 RW2 → 原样传 RAW，那一行写明原因', 'P1047510.RW2' in m and '原样传了 RAW' in (rw.get('msg') or '') and '1920×1280' in rw.get('msg', ''), rw.get('msg'))
        check('RAW+JPEG 拍的：同名 JPEG 选了 → CR2 跳过，只有 JPEG', 'B13A0729.JPG' in m and 'B13A0729.CR2' not in m and not any(r['n'] == 'B13A0729.CR2' for r in rows))
        pg.wait_for_function("() => { const it = [...__album.S.byH.values()].find(x => x.n === 'IMG_4241.JPG'); return it && (it.f & 3) === 3; }", timeout=120000)
        pg.evaluate('() => __album.refresh(true)')
        check('转出来的 JPEG 浏览器自己做好了缩略图 / 预览（不用等 GPU）', (mine()['IMG_4241.JPG']['f'] & 3) == 3)
        ok_row = next(r for r in rows if r['n'] == 'IMG_4241.JPG')
        check('那一行写着省了多少（RAW xx MB → JPEG x MB）', 'RAW' in ok_row['msg'] and '→ JPEG' in ok_row['msg'], ok_row['msg'])
        lg = [l for l in Client(e2e.PIPE).get('/api/pipe/uplog?limit=10').json() if l.get('name') == U]
        r = lg[0]['j'].get('raw') if lg else None
        check('这一批的转换统计记进了上传日志', r and r['jpg'] == 2 and r['kept'] == 1 and r['inMB'] > 70 and r['outMB'] < 8, r)

        # 4) 同一批再选一次（新页面，模拟换天再选）
        pg.reload(); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        pg.set_input_files('#file', files); pg.wait_for_function(done, timeout=300000)
        st = pg.evaluate("() => __album.UQ.map(t => t.state)")
        check('同一批再选一次 → 全部秒传', st and all(s == 'dup' for s in st), st)

        # 5) 切到「原样传 RAW」
        pg.reload(); pg.wait_for_selector('#app:not([hidden])', timeout=15000)
        pg.evaluate("() => document.querySelector('#upsheet').hidden = false")
        pg.check('input[name=rawm][value=raw]')
        check('切换会记住（本机）', pg.evaluate('() => localStorage.np_raw') == 'raw')
        pg.set_input_files('#file', [os.path.join(D, 'IMG_4241.CR3')]); pg.wait_for_function(done, timeout=300000)
        m = mine()
        check('原样传 RAW → 相册里是 .CR3 原片（字节一个不少）', m.get('IMG_4241.CR3', {}).get('s') == os.path.getsize(os.path.join(D, 'IMG_4241.CR3')), m.get('IMG_4241.CR3', {}).get('s'))
        check('整个过程没有 JS 报错', not errs, errs[:3])
        br.close()


def cleanup():
    P = Client(e2e.PIPE); L = Client(); L.login(U)
    me = L.get('/api/me').json()['user']['id']
    P.post('/api/pipe/purge', {'hs': [x['h'] for x in L.get('/api/list').json()['items'] if me in (x.get('u') or [])], 'users': [U]})
    shutil.rmtree(D, ignore_errors=True)


if __name__ == '__main__':
    t0 = time.time()
    try: main()
    except Exception as e:  # noqa: BLE001
        import traceback; traceback.print_exc(); check('脚本跑完', False, repr(e)[:200])
    finally: cleanup()
    ok = sum(r[1] for r in results)
    print(f'\n{ok}/{len(results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(results) else 1)
