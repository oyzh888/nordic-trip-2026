#!/usr/bin/env python3
"""演示走查：真上传 → 线上常驻 GPU 端真分析 → 真 AI 改图 → 每个界面截图 → 全部删掉。

    python test/showcase.py https://nordic.airacle.com /mnt/localssd/colligo_cache/tmp/photos-showcase

和 pipe_e2e.py 用同一批素材，但**只用风景**（Wikimedia Commons，CC 授权）—— 截图要发出去，
人物照（公众人物的公开照片、insightface 自带的合影）一张都不传。所以人物页在这里是空的，人脸识别的结果看 pipe_e2e。
输出：截图 + 改图前后对比 + 一份 run.json（每一步的耗时、改图用的模型和原话），给 HTML 报告用。
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e
from e2e import Client
from pipe_e2e import make_fixtures, wait_done

BASE = e2e.BASE
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(e2e.HERE, 'out', 'showcase')
U = '小北'
SCENERY = {'IMG_5001.JPG', 'IMG_5003.JPG', 'DSC01001.JPG', 'DSC01002.JPG', 'DSC01003.JPG', 'DSC01004.JPG',
           'IMG_5010.JPG', 'IMG_5012.JPG', 'IMG_5014.JPG', 'IMG_5015.JPG', 'DSC01101.JPG', 'DSC01102.JPG',
           'IMG_5020.JPG', 'IMG_5030.JPG', 'IMG_5031.JPG', 'IMG_5013.MOV', 'VID_5032.mp4'}
# 第一张在界面里点着改（截面板、进度、结果），另外两张直接走 API 并行排队
EDITS = [('IMG_5010.JPG', 'nano', '变成大雪覆盖的冬天，瀑布边结满冰挂'),
         ('IMG_5031.JPG', 'gpt', '改成吉卜力动画风格'),
         ('IMG_5001.JPG', 'pro', '把天空换成绚丽的绿色极光，教堂保持不变')]
MODEL_ID = {'nano': 'gemini-3.1-flash-image', 'pro': 'gemini-3-pro-image', 'gpt': 'gpt-image-2'}
RUN = {'base': BASE, 'shots': [], 'edits': [], 't': {}}
HS = set()


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    files = [p for p in make_fixtures()[0] if os.path.basename(p) in SCENERY]
    assert len(files) == len(SCENERY), [os.path.basename(p) for p in files]
    A, P = Client(), Client(e2e.PIPE)
    A.login(U)

    with sync_playwright() as pw:
        br = pw.chromium.launch(channel='chrome', headless=True)

        def shot(pg, name, cap, full=False):
            pg.wait_for_timeout(500)
            pg.screenshot(path=os.path.join(OUT, name + '.png'), full_page=full)
            RUN['shots'].append({'f': name + '.png', 'cap': cap})
            print('  截图', name, cap, flush=True)

        def settle(pg):
            pg.evaluate('__album.refresh(true)'); pg.wait_for_timeout(1500)

        def search(pg, q):
            pg.fill('#q', q)
            pg.wait_for_function(f"document.querySelector('#sum').textContent.includes({json.dumps(q)}) && !document.querySelector('#sum').textContent.includes('正在找')", timeout=20000)
            pg.wait_for_timeout(1200)

        ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1, locale='zh-CN')
        pg = ctx.new_page()
        pg.goto(BASE + '/photos/#k=' + e2e.PASS)
        pg.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        pg.fill('#name', U)
        shot(pg, 'd01-login', '邀请链接自带口令，第一次只问「你是谁」')
        pg.click('#f-name button.pri'); pg.wait_for_selector('#app:not([hidden])', timeout=15000)

        # ---- 上传（浏览器真的读 EXIF、算内容 ID、分片传）----
        pg.click('#btn-up'); pg.set_input_files('#file', files)
        t0 = time.time()
        pg.wait_for_function("__album.UQ.length && __album.UQ.every(t => ['ok','dup','failed'].includes(t.state))", timeout=300000)
        RUN['t']['upload'] = round(time.time() - t0, 1)
        st = pg.evaluate("__album.UQ.map(t => [t.f.name, t.state, t.h])")
        H = {n: h for n, s, h in st}
        HS.update(H.values())
        assert all(s == 'ok' for _, s, _ in st), st
        shot(pg, 'd02-upload', f'一次选 {len(files)} 个文件（15 张照片 + 2 段视频），{RUN["t"]["upload"]} 秒传完')
        pg.click('#up-close')

        # ---- 等线上 GPU 端分析 + 聚类 ----
        t0 = time.time()
        RUN['t']['analyze'] = round(wait_done(A, P, list(H.values())), 1)
        print(f'分析 + 聚类完成 {RUN["t"]["analyze"]}s', flush=True)
        settle(pg)
        shot(pg, 'd03-grid-day', '📅 按天（默认）：连拍 4 张只露出最清楚的一张，右下角标着「4」', full=True)
        pg.click('[data-gp=place]'); shot(pg, 'd04-grid-place', '📍 按地点：GPS 反查到景点名，统一简体中文', full=True)
        pg.click('[data-gp=moment]'); shot(pg, 'd05-grid-moment', '✨ 按时刻：按时间和位置切成一段段经历，模型起标题，★ 是最值得纪念的几段', full=True)
        pg.click('[data-gp=cam]'); shot(pg, 'd06-grid-cam', '📷 按设备：谁的手机 / 相机拍的', full=True)
        pg.click('[data-gp=day]')
        pg.click('[data-f=hl]'); shot(pg, 'd07-highlights', '★ 精选：AI 觉得值得纪念的（极光、瀑布、冰川……）', full=True)
        pg.click('[data-f=all]')
        sp = pg.locator('#specials [data-sp]')
        if sp.count():
            name = sp.first.get_attribute('data-sp'); sp.first.click()
            shot(pg, 'd08-special', f'特殊场景一键筛：「{name}」')
            sp.first.click()

        # ---- 搜索 ----
        for i, q in enumerate(['极光', '海边的小鸟', '瀑布', 'tram']):
            search(pg, q)
            shot(pg, f'd09-search-{i}', f'搜「{q}」：{pg.text_content("#sum").strip()[:40]}')
        pg.fill('#q', ''); pg.wait_for_timeout(800)

        # ---- 连拍组 ----
        lst = {x['h']: x for x in A.get('/api/list').json()['items']}
        cover = next((h for n, h in H.items() if n.startswith('DSC0100') and lst[h].get('bc')), H['DSC01001.JPG'])
        RUN['burst'] = {n: lst[h].get('b') for n, h in H.items() if n.startswith('DSC0100')}
        pg.click(f'#grid .tl[data-h="{cover}"]'); pg.wait_for_selector('#lb .lb-grp')
        pg.locator('#lb .lb-grp').scroll_into_view_if_needed()
        shot(pg, 'd10-burst', '点开连拍的封面：信息栏列出同组 4 张（原图 / 轻糊 / 重糊 / 裁边），AI 选了最清楚的那张，可以换')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

        # ---- 视频 ----
        pg.click(f'#grid .tl[data-h="{H["IMG_5013.MOV"]}"]'); pg.wait_for_selector('#lb video', timeout=10000)
        pg.wait_for_timeout(1500)
        shot(pg, 'd11-video', 'iPhone 的 HEVC .mov：GPU 端转出 720p H.264，Windows / 安卓的浏览器也能直接播')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

        # ---- AI 改图：界面里改第一张 ----
        fn, model, prompt = EDITS[0]
        pg.click(f'#grid .tl[data-h="{H[fn]}"]'); pg.wait_for_selector('#lb:not([hidden])')
        pg.click('#lb-ai'); pg.wait_for_selector('#ai-p')
        pg.fill('#ai-p', prompt)
        pg.check(f'input[name="ai-m"][value="{model}"]')
        shot(pg, 'd12-ai-panel', '✨ AI 改图：写一句话或点预设，选模型')
        t0 = time.time()
        pg.click('#ai-go'); pg.wait_for_selector('#lb-aied .spin', timeout=10000)
        pg.wait_for_timeout(1500); shot(pg, 'd13-ai-progress', '改的过程中原图照常显示，下面是进度')
        # 另外两张走 API，同时排队（每人最多 3 张在改）
        eids = []
        for fn2, m2, p2 in EDITS[1:]:
            r = A.post('/api/edit', {'h': H[fn2], 'prompt': p2, 'model': m2}).json()
            assert 'id' in r, r
            eids.append((fn2, m2, p2, r['id']))
        pg.wait_for_function('(() => { const it = __album.S.view[__album.S.lb]; return it && it.src; })()', timeout=300000)
        it = pg.evaluate('__album.S.view[__album.S.lb]')
        HS.add(it['h'])
        RUN['edits'].append({'src': fn, 'model': model, 'mid': MODEL_ID[model], 'prompt': prompt, 'wall': round(time.time() - t0, 1),
                             'src_h': H[fn], 'out_h': it['h']})
        pg.wait_for_timeout(3500)                                  # 等「改好了」的提示消失，别挡住信息栏
        shot(pg, 'd14-ai-result', '改好后自动跳到新照片（原图不动）：信息栏写着从哪张改来、哪句话、谁改的；按住「按住看原图」可对比')
        pg.keyboard.press('Escape'); pg.wait_for_timeout(300)

        for fn2, m2, p2, eid in eids:
            t1 = time.time()
            while True:
                e = A.get(f'/api/edit?id={eid}').json()
                if e['status'] in ('done', 'failed') or time.time() - t1 > 300: break
                time.sleep(2)
            ok = e['status'] == 'done'
            if ok: HS.add(e['out_h'])
            RUN['edits'].append({'src': fn2, 'model': m2, 'mid': MODEL_ID[m2], 'prompt': p2, 'status': e['status'], 'err': e.get('err'),
                                 'model_s': round((e['done'] - e['started']) / 1000, 1) if ok and e.get('started') else None,
                                 'src_h': H[fn2], 'out_h': e.get('out_h')})
        settle(pg)
        shot(pg, 'd15-grid-with-ai', '改出来的 3 张作为新照片排在原图旁边，带 ✨ 角标', full=True)

        # 改图前后的预览图存下来给报告用
        for e in RUN['edits']:
            for k in ('src_h', 'out_h'):
                if e.get(k):
                    b = A.get(f'/f/{e[k]}/p').content
                    open(os.path.join(OUT, f'{k[:3]}-{e["model"]}.jpg'), 'wb').write(b)

        pg.click('[data-tab=insight]'); pg.wait_for_selector('#insight .stats', timeout=10000)
        shot(pg, 'd16-insight', '「分析」页：场景分布、设备、时刻一览', full=True)
        pg.click('[data-tab=grid]')
        pg.click('#btn-sel'); pg.wait_for_timeout(300)
        for n in ('IMG_5010.JPG', 'IMG_5012.JPG', 'IMG_5014.JPG'):
            pg.click(f'#grid .tl[data-h="{H[n]}"]')
        shot(pg, 'd17-select', '「选择」→ 勾几张 →「⬇ 打包下载」出 zip（原画质，按「日期_地点」分文件夹）')
        pg.click('#sel-x')
        ctx.close()

        # ---- 手机 ----
        dev = dict(pw.devices['iPhone 13']); dev.pop('default_browser_type', None)
        mc = br.new_context(**dev, locale='zh-CN')
        m = mc.new_page()
        m.goto(BASE + '/photos/#k=' + e2e.PASS); m.wait_for_selector('#f-name:not([hidden])', timeout=15000)
        m.fill('#name', U); m.click('#f-name button.pri'); m.wait_for_selector('#app:not([hidden])', timeout=15000)
        m.wait_for_timeout(1500)
        shot(m, 'm01-grid', '手机：照片墙')
        m.click('[data-gp=moment]'); shot(m, 'm02-moment', '手机：按时刻', full=True); m.click('[data-gp=day]')
        search(m, '极光'); shot(m, 'm03-search', '手机：搜「极光」'); m.fill('#q', ''); m.wait_for_timeout(800)
        m.click(f'#grid .tl[data-h="{RUN["edits"][0]["out_h"]}"]'); m.wait_for_selector('#lb:not([hidden])'); m.wait_for_timeout(1500)
        shot(m, 'm04-lightbox', '手机：大图 + AI 改图结果')
        mc.close()
        br.close()


def cleanup():
    P = Client(e2e.PIPE)
    r = P.post('/api/pipe/purge', {'hs': sorted(HS), 'users': [U]})
    RUN['purge'] = {'status': r.status_code, 'n': len(HS)}
    left = [x for x in P.get('/api/list').json()['items'] if x['h'] in HS]
    RUN['purge']['left'] = len(left)
    print('收尾：删除', len(HS), '个文件', r.status_code, '剩', len(left), flush=True)


if __name__ == '__main__':
    t0 = time.time()
    try:
        main()
    except Exception:
        import traceback; traceback.print_exc(); RUN['error'] = traceback.format_exc()[-800:]
    finally:
        cleanup()
        RUN['t']['total'] = round(time.time() - t0, 1)
        json.dump(RUN, open(os.path.join(OUT, 'run.json'), 'w'), ensure_ascii=False, indent=1)
        print('→', OUT)
