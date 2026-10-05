#!/usr/bin/env python3
"""增量列表对拍：把整套 e2e.py 跑一遍，每发一个「会改东西」的请求，就让一个镜像客户端用增量（/api/list?since=）
跟上，再和服务端现拼的全量（/api/list）逐项比 —— 一模一样才算过。

覆盖 e2e 里的全部写操作：上传 / 秒传 / 补块 / 缩略图 / GPU 分析结果 / 聚类（连拍、时刻、场景、人脸）/
认领人物 / 合并 / 摘掉一张脸 / 挑封面 / 撤回 / Live Photo 配对 / AI 改图 / 收尾删除。
哪一步漏了 bump(h)，镜像就会和全量对不上，这里会指出是哪个请求。

    python test/list_delta.py http://localhost:8787 < /dev/null
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e2e

assert 'localhost' in e2e.BASE or '127.0.0.1' in e2e.BASE, '只在本地跑'
orig_req, orig_login = e2e.Client.req, e2e.Client.login
stat = {'checks': 0, 'bad': [], 'delta': 0, 'full': 0, 'bytes': 0, 'full_bytes': 0}


class Mirror:
    """和 app.js 的 loadList / mergeDelta 同一个算法"""
    def __init__(self): self.cookie, self.d = None, None

    def get(self, q):
        r = orig_req(self.c, 'GET', '/api/list' + q); stat['bytes'] += len(r.content); return r.json()

    @property
    def c(self):
        c = e2e.Client(); c.cookie = self.cookie; return c

    def sync(self):
        if self.d is None: self.d = self.get('?stale=1')
        d = self.get(f"?since={self.d['ver']}")
        if not d.get('delta'):
            stat['full'] += 1; self.d = d; return
        stat['delta'] += 1
        upd = {it['h']: it for it in d['items']}; gone = set(d['gone'])
        items = []
        for it in self.d['items']:
            if it['h'] in gone: continue
            items.append(upd.pop(it['h'], it))
        items += upd.values()
        g = {k: d.get(k, self.d.get(k)) for k in ('users', 'persons', 'scenes', 'moments', 'pipe', 'ai')}
        self.d = {**self.d, **g, 'ver': d['ver'], 'items': items}

    def check(self, why):
        self.sync()
        r = orig_req(self.c, 'GET', '/api/list'); full = r.json(); stat['full_bytes'] += len(r.content)
        stat['checks'] += 1
        a = {x['h']: x for x in self.d['items']}; b = {x['h']: x for x in full['items']}
        diff = [h[:8] for h in set(a) | set(b) if a.get(h) != b.get(h)]
        gd = [k for k in ('users', 'persons', 'scenes', 'moments', 'pipe', 'ai') if self.d.get(k) != full.get(k)]
        if self.d['ver'] != full['ver'] or diff or gd or len(self.d['items']) != len(full['items']):
            stat['bad'].append((why, self.d['ver'], full['ver'], diff[:4], gd))
            print(f'  !! 增量和全量对不上：{why} · ver {self.d["ver"]}/{full["ver"]} · 照片 {diff[:4]} · 全局 {gd}', flush=True)
            if diff:
                h = next(x for x in set(a) | set(b) if x[:8] == diff[0])
                print('     增量:', json.dumps(a.get(h), ensure_ascii=False)[:300]); print('     全量:', json.dumps(b.get(h), ensure_ascii=False)[:300])
            self.d = full                                       # 对齐后接着找下一处


M = Mirror()


def login(self, name):
    r = orig_login(self, name)
    if M.cookie is None and self.cookie: M.cookie = self.cookie
    return r


def req(self, method, path, **kw):
    r = orig_req(self, method, path, **kw)
    if method != 'GET' and M.cookie and not path.startswith('/api/list'):
        try: M.check(f'{method} {path.split("?")[0]}')
        except Exception as e:  # noqa: BLE001 —— 收尾删掉了镜像借用的用户之后，列表要 401
            if M.d is not None and 'Expecting value' not in str(e) and 'purge' not in path: print('  镜像出错', path, repr(e))
    return r


e2e.Client.req, e2e.Client.login = req, login

if __name__ == '__main__':
    t0 = time.time()
    try: e2e.main()
    except Exception as ex:  # noqa: BLE001
        import traceback; traceback.print_exc(); e2e.check('e2e 跑完', False, repr(ex)[:200])
    finally: e2e.cleanup()
    n_e2e, ok_e2e = len(e2e.results), sum(r[1] for r in e2e.results)
    e2e.results.clear()
    e2e.check(f'e2e 本身照常全过（{ok_e2e}/{n_e2e}）', ok_e2e == n_e2e and n_e2e > 50, [r[0] for r in e2e.results if not r[1]][:3])
    e2e.check(f'每个写请求之后，增量拼出来的列表和全量一模一样（比了 {stat["checks"]} 次）', stat['checks'] > 50 and not stat['bad'], stat['bad'][:3])
    e2e.check('绝大多数同步走的是增量（服务端答得了）', stat['delta'] > 0.9 * (stat['delta'] + stat['full']), f"增量 {stat['delta']} · 退回全量 {stat['full']}")
    print(f"  镜像一共下载 {stat['bytes'] / 1e3:.0f} KB；同样次数的全量是 {stat['full_bytes'] / 1e3:.0f} KB")
    ok = sum(r[1] for r in e2e.results)
    print(f'\n{ok}/{len(e2e.results)} 通过 · {time.time() - t0:.0f}s')
    sys.exit(0 if ok == len(e2e.results) else 1)
