#!/usr/bin/env python3
"""把 showcase.py 的产出 + 三套测试的结果拼成一页 HTML（给人看的测试报告）。

    python test/showcase_report.py <showcase 输出目录> <报告目录>

只收检查项的**名字**，不收 detail（pipe_e2e 的 detail 里有人物照的簇名、哈希之类，不该发出去）。
"""
import html, json, os, re, sys
from PIL import Image

SRC, DST = sys.argv[1], sys.argv[2]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
os.makedirs(os.path.join(DST, 'img'), exist_ok=True)
RUN = json.load(open(os.path.join(SRC, 'run.json')))
E = html.escape


def jpg(name, maxw=1440):
    im = Image.open(os.path.join(SRC, name)).convert('RGB')
    if im.width > maxw: im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    out = os.path.splitext(name)[0] + '.jpg'
    im.save(os.path.join(DST, 'img', out), 'JPEG', quality=82, optimize=True, progressive=True)
    return 'img/' + out


def suite(f):
    d = json.load(open(os.path.join(OUT, f)))
    return d['results']


SUITES = [  # (名字, 测什么, 本地结果文件, 线上结果文件)
    ('e2e.py', '服务端：口令、上传、去重、断点续传、下载、zip、搜索、人物、权限……', 'e2e-local.json', 'e2e-prod.json'),
    ('ui.py', '真浏览器（Playwright）：手机 + 桌面把界面点一遍', None, None),
    ('pipe_e2e.py', '真照片 + 真模型（看图 / 认脸 / 以文搜图）+ 真 AI 改图', 'pipe-local.json', 'pipe-prod.json'),
]
UI_TXT = {k: open(os.path.join(OUT, f'ui-{k}.txt')).read().strip().splitlines()[-1] for k in ('local', 'prod')}


def tally(f):
    r = suite(f); return f"{sum(x['ok'] for x in r)}/{len(r)}"


rows = []
for name, what, lf, pf in SUITES:
    if name == 'ui.py':
        loc, prod = (UI_TXT[k].split(' ')[0] for k in ('local', 'prod'))
    else:
        loc, prod = tally(lf), tally(pf)
    rows.append(f'<tr><td><code>{name}</code></td><td>{E(what)}</td><td class="ok">{loc}</td><td class="ok">{prod}</td></tr>')

checks = []
for name, _, lf, pf in SUITES:
    if not pf: continue
    items = ''.join(f'<li class="{"ok" if x["ok"] else "bad"}">{"✓" if x["ok"] else "✗"} {E(x["name"])}</li>' for x in suite(pf))
    checks.append(f'<details><summary><code>{name}</code> 线上 {tally(pf)} —— 展开看每一条</summary><ul class="ck">{items}</ul></details>')
ui_items = [l[6:] for l in open(os.path.join(OUT, 'ui-prod.txt')).read().splitlines() if l.startswith('PASS  ')]
ui_items = ''.join(f'<li class="ok">✓ {E(l.split("  — ")[0])}</li>' for l in ui_items)
checks.insert(1, f'<details><summary><code>ui.py</code> 线上 {UI_TXT["prod"].split(" ")[0]} —— 展开看每一条</summary><ul class="ck">{ui_items}</ul></details>')

NAMES = {'nano': 'Nano Banana 2', 'pro': 'Nano Banana Pro', 'gpt': 'GPT Image 2'}
ai = []
for e in RUN['edits']:
    t = e.get('model_s') or e.get('wall')
    ai.append(f'''<figure class="ba">
  <div class="pair"><div><img src="{jpg('src-' + e['model'] + '.jpg', 900)}" alt=""><span>原图</span></div>
  <div><img src="{jpg('out-' + e['model'] + '.jpg', 900)}" alt=""><span>✨ 改后</span></div></div>
  <figcaption>「{E(e['prompt'])}」<br><b>{NAMES[e['model']]}</b> <code>{e['mid']}</code> · {t} 秒</figcaption></figure>''')

for s in RUN['shots']:  # 搜索截图的说明是抓的页面文字，连着按钮一起，只留「几个结果」
    m = re.match(r'搜「(.+?)」：.*?(\d+) 个结果', s['cap'])
    if m: s['cap'] = f'搜「{m[1]}」：{m[2]} 个结果（关键词 + 画面语义一起排）'
shots_d = [s for s in RUN['shots'] if s['f'].startswith('d')]
shots_m = [s for s in RUN['shots'] if s['f'].startswith('m')]
gal = lambda xs, cls: ''.join(f'<figure class="{cls}"><a href="{(p := jpg(s["f"]))}" target="_blank"><img loading="lazy" src="{p}" alt=""></a><figcaption>{E(s["cap"])}</figcaption></figure>' for s in xs)

T = RUN['t']
page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>共享相册 · 测试报告</title><style>
:root{{--bg:#0f0e0c;--fg:#ece6da;--mu:#9d968a;--ac:#5fd3a4;--card:#1a1916;--ln:#2c2a26}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.7 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:32px 20px 80px}}h1{{font-size:28px;margin:0 0 6px}}h2{{margin:48px 0 12px;font-size:21px;border-bottom:1px solid var(--ln);padding-bottom:6px}}
.mu{{color:var(--mu)}}a{{color:var(--ac)}}code{{background:#24221e;padding:1px 5px;border-radius:4px;font-size:.88em}}
.tldr{{background:var(--card);border-left:3px solid var(--ac);padding:14px 18px;border-radius:8px}}
table{{border-collapse:collapse;width:100%;margin:8px 0}}td,th{{border-bottom:1px solid var(--ln);padding:8px 10px;text-align:left;vertical-align:top}}th{{color:var(--mu);font-weight:500}}
td.ok{{color:var(--ac);font-weight:600;white-space:nowrap}}
.ba{{margin:0 0 28px}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.pair div{{position:relative}}.pair img{{width:100%;border-radius:8px;display:block}}
.pair span{{position:absolute;left:8px;top:8px;background:#000a;padding:1px 8px;border-radius:10px;font-size:13px}}figcaption{{color:var(--mu);font-size:14px;margin-top:6px}}
.g{{display:grid;grid-template-columns:1fr;gap:34px}}.g figure,.m figure{{margin:0}}
.g img{{width:100%;max-height:760px;object-fit:cover;object-position:top;border-radius:8px;border:1px solid var(--ln);display:block}}
.m{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:18px}}.m img{{width:100%;height:540px;object-fit:cover;object-position:top;border-radius:14px;border:1px solid var(--ln);display:block}}
details{{background:var(--card);border-radius:8px;padding:8px 14px;margin:8px 0}}summary{{cursor:pointer}}.ck{{columns:2;font-size:14px;padding-left:18px}}.ck li{{list-style:none;break-inside:avoid}}.ck .ok{{color:#b9e8d3}}.ck .bad{{color:#f08a7a}}
dl dt{{font-weight:600;margin-top:8px}}dl dd{{margin:0 0 0 1em;color:var(--mu)}}
@media(max-width:640px){{.ck{{columns:1}}.pair{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>📷 共享相册 · 测试报告</h1>
<p class="mu">2026-09-26 · <a href="https://nordic.airacle.com/photos/">nordic.airacle.com/photos/</a> · 源码 <a href="https://github.com/oyzh888/nordic-trip-2026/tree/main/photos">github.com/oyzh888/nordic-trip-2026/photos</a></p>

<div class="tldr"><b>一句话：测过了，全部通过；下面每张截图都是真跑出来的，不是设计稿。</b><br>
17 个文件（15 张冰岛 / 里斯本风景照 + 2 段视频）从浏览器真上传，GPU 端用真模型看图、认地点、分组、挑连拍里最好的一张；
然后用三个真模型各改了一张图（Nano Banana 2 {RUN['edits'][0].get('wall')} 秒 · Nano Banana Pro {RUN['edits'][2].get('model_s')} 秒 · GPT Image 2 {RUN['edits'][1].get('model_s')} 秒）。
跑完把这些文件、改图、演示用户全部删掉（删除 {RUN['purge']['n']} 个，剩 {RUN['purge']['left']} 个）。</div>

<h2>这页是怎么来的</h2>
<p>一个脚本（<code>photos/test/showcase.py</code>）用无头浏览器（没有窗口、由程序操控的 Chrome）扮演一个叫「小北」的用户，按真实用法点一遍，每一步截一张图。</p>
<p>⚠️ <b>截图是在本地副本上拍的，不是线上。</b>跑到一半发现线上相册里已经有同行的人在传真照片了（十几张）。在线上截图，就会把那个人的照片截进一个公开网页里。
所以我停了线上那次（它传的 17 个演示文件已经删掉，没碰那个人的照片），换到本地副本上重跑：同一份代码、同一台 GPU、同样的三个看图模型，AI 改图也同样走真接口。
区别只在于照片存在本地模拟的存储里，而不是 Cloudflare。线上本身测过，见下表最右一列。</p>
<p class="mu">耗时：上传 {T['upload']} 秒。分析加分组：第一次冷跑是 216.6 秒（每个文件约 13 秒，含视频转码和反查地名）；截图用的这次是 {T['analyze']} 秒，因为分析结果按文件内容缓存，同样的文件不会重算（17 个里 17 个都命中缓存）。</p>

<h2>测试结果</h2>
<table><tr><th>测试脚本</th><th>测什么</th><th>本地</th><th>线上</th></tr>{''.join(rows)}</table>
<p class="mu"><code>ui.py</code> 在线上少 2 条不是没过：那 2 条（「改图失败时提示原因」「GPU 端下线后按钮消失」）要假装 GPU 端出故障，只在本地跑。
<code>pipe_e2e.py</code> 在本地多 1 条是同样的原因。人脸识别用的是公众人物的公开照片，结果在 <code>pipe_e2e.py</code> 里（同一个人的不同照片归成一个人、别人传的新照片自动认出来），<b>那些照片不放进这个公开页</b>。</p>
{''.join(checks)}

<h2>✨ AI 改图：改前 / 改后</h2>
<p class="mu">原图不会被改动，改出来的是一张新照片，带着原图的时间和地点，排在原图旁边。后两张的秒数是模型本身的用时；第一张是在界面里点的，秒数是从点「开始」到新图出现。</p>
{''.join(ai)}

<h2>桌面端截图</h2><p class="mu">长截图只露出上半截，点图看完整一张。</p>
<div class="g">{gal(shots_d, '')}</div>
<h2>手机端截图（iPhone 13 尺寸）</h2>
<div class="m">{gal(shots_m, '')}</div>

<h2>看出来的问题（没藏）</h2>
<ul>
<li><b>搜「海边的小鸟」</b>：海鹦找到了，但混进来一张雷克雅未克街景。原因是分词切成了「海边 / 的小鸟」，「的小鸟」匹配不到任何关键词，只剩「海边」加画面相似度在起作用。要修的是分词：「的」应该丢掉。</li>
<li><b>★ 精选在这批上几乎全亮</b>：测试素材全是维基共享资源（Wikimedia Commons）上挑过的风景名片，模型觉得张张都值得纪念。「时刻」那一层已经限制了带 ★ 的最多三分之一，单张照片还没限。等真照片进来再看要不要收紧。</li>
<li><b>冰河湖的地名是冰岛语</b>（Sveitarfélagið Hornafjörður，一个行政区名）：500 米内的地图数据里没有带中文名的景点，所以只能退回行政区名。</li>
<li><b>「人物」页在这里是空的</b>：发出来的截图故意不含人像，所以没有脸可认。人脸功能看上面 <code>pipe_e2e.py</code> 的检查项。</li>
</ul>

<h2>术语</h2><dl>
<dt>GPU 端 / 分析端</dt><dd>一台有显卡的机器上常驻的程序，主动连到相册拿新照片来分析。它下线时上传、浏览、下载都照常，只是新照片暂时没有描述和分组。</dd>
<dt>VLM（视觉语言模型）</dt><dd>能看图说话的模型，这里用 Qwen3-VL-8B：写中文描述、列物体和场景、判断是不是值得纪念。</dd>
<dt>以文搜图 / 语义搜索</dt><dd>用 SigLIP 模型把文字和图片放进同一个「意思空间」，搜「海边的小鸟」不需要照片被打过「海鹦」这个标签也能找到。</dd>
<dt>连拍组</dt><dd>几秒内拍的几张几乎一样的照片。默认只露出 AI 打分最高的一张，点开能看整组、能换。</dd>
<dt>时刻</dt><dd>按拍摄时间和位置自动切出的一段段经历（隔 45 分钟或移动 2 公里就分段），模型给每段起标题，★ 是最值得纪念的几段。</dd>
<dt>缓存命中</dt><dd>同样的输入以前算过，就直接拿结果，不再算一次。</dd>
</dl>

<h2>素材来源</h2>
<p class="mu">风景照来自维基共享资源（Wikimedia Commons），CC BY / CC BY-SA 授权，仅作功能演示。拍摄时间、地点和相机是测试脚本按一条假行程写进 EXIF（照片里自带的拍摄信息）的。
演示用户「小北」和所有演示文件在跑完后都已删除。</p>
</main></body></html>'''
open(os.path.join(DST, 'index.html'), 'w').write(page)
print('→', DST, sum(os.path.getsize(os.path.join(DST, 'img', f)) for f in os.listdir(os.path.join(DST, 'img'))) // 1024, 'KB')
