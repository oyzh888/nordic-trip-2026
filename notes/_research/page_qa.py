#!/usr/bin/env python3
"""本地起一个 http server，把每个页面按几个宽度打开，报 JS 错误 / 坏图 / 横向溢出。

为什么要这个脚本：三个真 bug（中文标题 line-height <1 重叠、grid 子项 min-width:auto
把整页撑到 2838px、图片 401）都不是「看一眼」能发现的，只能量。

Usage: python3 page_qa.py [页面相对路径 ...]      # 默认查全部
"""
import functools, http.server, socketserver, sys, threading, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAGES = sys.argv[1:] or ["viz/index.html", "styles/index.html", "styles/a-editorial.html",
                         "styles/b-cinema.html", "styles/c-museum.html", "styles/d-swiss.html",
                         "story/index.html"]
WIDTHS = [390, 1440]

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

from playwright.sync_api import sync_playwright   # noqa: E402

bad_total = 0
with sync_playwright() as p:
    br = p.chromium.launch()
    for page_path in PAGES:
        for w in WIDTHS:
            pg = br.new_page(viewport={"width": w, "height": 900})
            errs, failed = [], []
            pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
            pg.on("requestfailed", lambda r: failed.append(r.url[:110]))
            pg.goto(f"http://127.0.0.1:{port}/{page_path}", wait_until="load", timeout=90_000)
            # 把懒加载图逼出来
            for _ in range(14):
                pg.mouse.wheel(0, 3000)
                pg.wait_for_timeout(320)
            pg.wait_for_timeout(2500)
            r = pg.evaluate("""() => {
              /* 空 src 的要排掉 —— lightbox 的 <img id="lbi"> 平时就是空的，
                 naturalWidth===0 但它不是坏图（story 页曾因此被误报一张） */
              const im=[...document.images].filter(i=>(i.currentSrc||i.getAttribute('src')||'').trim());
              return {ow:document.documentElement.scrollWidth, iw:innerWidth,
                total:im.length,
                loaded:im.filter(i=>i.complete&&i.naturalWidth>0).length,
                broken:im.filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.currentSrc||i.src).slice(0,6)};
            }""")
            over = r["ow"] > r["iw"] + 1
            bad = len(r["broken"]) + len(errs) + (1 if over else 0)
            bad_total += bad
            print(f"{page_path:26s} {w:>5}px  图 {r['loaded']}/{r['total']} 坏 {len(r['broken'])}"
                  f" · 溢出 {'是 '+str(r['ow'])+'px' if over else '否'} · JS 错 {len(errs)}"
                  f"{'  ' + ('✅' if bad == 0 else '🔴')}")
            for u in r["broken"]:
                print("      坏图:", u)
            for e in errs:
                print("      JS :", e)
            pg.close()
    br.close()
srv.shutdown()
print("—— 总问题数:", bad_total)
sys.exit(1 if bad_total else 0)
