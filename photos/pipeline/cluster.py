"""整本相册的聚类：人脸 → 簇 / 自动归人，相似照片 → 连拍组（挑最好的一张），场景，时刻。

全是纯函数：输入是服务端 /api/pipe/{faces,media,embs} 的原样结果，输出直接是 /api/pipe/clusters 的请求体。
每轮都从服务端全量重算 —— 相册是几千张的量级，一轮不到 1 秒，比维护增量状态简单也更不容易错。
"""
import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

# 阈值都是在测试集上量过的（见 README「阈值是怎么定的」）
# ArcFace 实测（Commons 上 4 位公众人物、跨 2008–2024 的不同照片 + 一张 6 人合影）：
#   同一个人不同照片 0.41–0.76（同一场合 0.65–0.76，隔十年 0.41–0.55）；不同的人最高 0.16（合影里 0.23）
FACE_LINK = 0.36        # 两簇平均余弦 ≥ 这个 → 同一个人。比最像的两个陌生人高 0.13，比隔十年的同一个人低 0.05
FACE_AUTO = 0.40        # 新脸和某人已确认的脸（前三像的平均）≥ 这个 → 自动归给他（写名字比分簇后果大，稍严一点）
FACE_MARGIN = 0.05      # 而且要比第二像的人高出这么多，否则宁可不归
BURST_SIM = 0.88        # SigLIP 图像余弦 ≥ 这个 → 「几乎一样」。实测：同一张轻糊 0.96 / 裁一点 0.99 / 重糊 0.85（但和轻糊那张 0.90，
                        # 单链接能串进来）；两个不同的瀑布 0.91、同一个冰河湖两个机位 0.85 —— 所以必须再靠时间和位置把关
BURST_SIM_TIGHT = 0.85  # 前后 10 秒内（真正的连拍）放宽到这个：重糊那张和它 2–4 秒外的邻居实测只有 0.852–0.872，
BURST_TIGHT = 10        # 0.88 会把它漏掉；而同一个冰河湖两个机位隔了 60 秒、0.844 —— 走的是 0.88 那道门，不受影响
BURST_GAP = 180         # 而且拍摄时间相差不超过 3 分钟
BURST_KM = 0.3          # 两张都有 GPS 时，相距不超过 300 米
MOMENT_GAP = 45 * 60    # 相邻两张隔 45 分钟以上 → 新的一段
MOMENT_KM = 2.0         # 或者位置跳了 2 公里以上
STAR_FRAC = 1 / 3       # 带 ★ 的时刻最多占三分之一
STAR_MIN = 3            # 但至少允许 3 段（相册很小的时候）


def _t(s):
    try:
        return datetime.fromisoformat(str(s)[:19]).timestamp()
    except (TypeError, ValueError):
        return None


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


class UF:
    def __init__(self, n): self.p = list(range(n))
    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]; i = self.p[i]
        return i
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


# ---------------------------------------------------------------- 人脸
def faces(rows, vec_of):
    """rows = /api/pipe/faces；vec_of(emb 字符串) → 单位向量。返回 (faces: {id: cluster}, auto: {id: person})

    聚类：平均链接层次聚类（两簇之间所有脸两两相似度的平均 ≥ FACE_LINK 才合并）—— 比单链接稳，
    不会被一张模糊脸把两个人串起来。簇 ID 尽量沿用上一轮（按成员重叠），否则页面上正要点「这是我」的那个簇会换号。
    """
    from sklearn.cluster import AgglomerativeClustering
    rows = [r for r in rows if r.get('emb')]
    V = {r['id']: vec_of(r['emb']) for r in rows}
    # 「这张不是他」标过的（confirmed 且无主）不参与；太小/太糊的脸不参与聚类，但仍可能被自动归人
    good = [r for r in rows if not (r['confirmed'] and r['person'] is None) and r['score'] >= 0.65 and min(r['w'], r['hh']) >= 0.015]
    out = {r['id']: None for r in rows}
    if len(good) >= 2:
        X = np.stack([V[r['id']] for r in good])
        lab = AgglomerativeClustering(n_clusters=None, metric='cosine', linkage='average',
                                      distance_threshold=1 - FACE_LINK).fit_predict(X)
        groups = defaultdict(list)
        for r, l in zip(good, lab):
            groups[l].append(r)
        used, nxt = set(), max([r['cluster'] or 0 for r in rows] + [0]) + 1
        for l, mem in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            if len(mem) < 2:
                continue                                 # 只出现一次的脸不成簇（人物页只列 ≥2 张的簇）
            old = Counter(r['cluster'] for r in mem if r['cluster'] is not None and r['cluster'] not in used).most_common(1)
            cid = old[0][0] if old else nxt
            if not old:
                nxt += 1
            used.add(cid)
            for r in mem:
                out[r['id']] = cid

    # 自动归人：只看人工确认过的脸（机器自己归的不算证据，否则一次归错会越滚越大）
    conf = defaultdict(list)
    for r in rows:
        if r['confirmed'] and r['person'] is not None:
            conf[r['person']].append(V[r['id']])
    auto = {}
    if conf:
        P = {p: np.stack(vs) for p, vs in conf.items()}
        # 簇 → 它里面已确认的脸大多属于谁（「这一簇你认领过其中几张」→ 剩下的也很可能是你）
        cl_person = {}
        cl_votes = defaultdict(Counter)
        for r in rows:
            if r['confirmed'] and r['person'] is not None and out.get(r['id']) is not None:
                cl_votes[out[r['id']]][r['person']] += 1
        for c, v in cl_votes.items():
            p, n = v.most_common(1)[0]
            if n >= sum(v.values()) * 0.6:
                cl_person[c] = p
        cand = defaultdict(list)                         # h → [(sim, face id, person)]
        for r in rows:
            if r['confirmed']:
                continue
            v = V[r['id']]
            sims = sorted(((float(np.sort(M @ v)[-3:].mean()), p) for p, M in P.items()), reverse=True)
            best, p = sims[0]
            second = sims[1][0] if len(sims) > 1 else -1
            if best >= FACE_AUTO and best - second >= FACE_MARGIN:
                cand[r['h']].append((best, r['id'], p))
            elif out.get(r['id']) in cl_person:
                cp = cl_person[out[r['id']]]
                s = next(s for s, q in sims if q == cp)
                if s >= 0.30:
                    cand[r['h']].append((s, r['id'], cp))
        # 同一张照片里不可能有两个同一个人：已确认的优先，其余留最像的那张脸
        taken = defaultdict(set)
        for r in rows:
            if r['confirmed'] and r['person'] is not None:
                taken[r['h']].add(r['person'])
        for h, cs in cand.items():
            for s, fid, p in sorted(cs, reverse=True):
                if p not in taken[h]:
                    taken[h].add(p)
                    auto[fid] = p
    return out, auto


# ---------------------------------------------------------------- 连拍 / 几乎一样的照片
def bursts(media, E):
    """media = /api/pipe/media；E = {h: 单位向量}。时间相近 + 画面几乎一样 → 一组，分最高的当封面。
    跨设备也算（两个人同时拍同一个场景，本来就该只看最好的那张）；视频和 AI 改过的图不参与
    （改图沿用原图的时间地点、画面又很像，不排除的话会和原图并成一组、被「收起相似」藏掉）。"""
    xs = [m for m in media if m['kind'] == 'image' and not m.get('src') and m['h'] in E and _t(m['taken'])]
    xs.sort(key=lambda m: _t(m['taken']))
    ts = [_t(m['taken']) for m in xs]
    uf = UF(len(xs))
    for i in range(len(xs)):
        j = i + 1
        while j < len(xs) and ts[j] - ts[i] <= BURST_GAP:
            a, b = xs[i], xs[j]
            near = a.get('lat') is None or b.get('lat') is None or km((a['lat'], a['lon']), (b['lat'], b['lon'])) <= BURST_KM
            if near and float(E[a['h']] @ E[b['h']]) >= (BURST_SIM_TIGHT if ts[j] - ts[i] <= BURST_TIGHT else BURST_SIM):
                uf.union(i, j)
            j += 1
    groups = defaultdict(list)
    for i, m in enumerate(xs):
        groups[uf.find(i)].append(m)
    out = {}
    for mem in groups.values():
        if len(mem) < 2:
            continue
        bid = 'b' + min(m['h'] for m in mem)[:12]
        best = max(mem, key=lambda m: (m['score'] or 0, m['sharp'] or 0))
        for m in mem:
            out[m['h']] = [bid, m['h'] == best['h']]
    return out


# ---------------------------------------------------------------- 场景
def _terms(m):
    tg = m.get('tags') or {}
    return set((tg.get('scene') or []) + (tg.get('objects') or []) + (tg.get('special') or []))


def scenes(media, E, seed=0):
    """KMeans 把整本相册按画面内容分成若干类，每类用「这类里最常见、别的类里少见」的中文标签命名。
    名字会被前端当成搜索词（点一下就搜），所以必须是标签里真有的词。"""
    from sklearn.cluster import KMeans
    xs = [m for m in media if m['h'] in E]
    if len(xs) < 8:
        return {'labels': [], 'items': {}}
    k = int(np.clip(round(math.sqrt(len(xs) / 3)), 2, 24))
    X = np.stack([E[m['h']] for m in xs])
    lab = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
    df = Counter(t for m in xs for t in _terms(m))
    N = len(xs)
    groups = defaultdict(list)
    for m, l in zip(xs, lab):
        groups[int(l)].append(m)
    labels, items, used = [], {}, set()
    for cid, (l, mem) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1])), 1):
        tf = Counter(t for m in mem for t in _terms(m))
        ranked = sorted(tf, key=lambda t: -(tf[t] / len(mem)) * math.log(1 + N / df[t]))
        name = next((t for t in ranked if t not in used and tf[t] >= max(2, len(mem) * 0.3)), None)
        if not name:
            continue
        used.add(name)
        labels.append({'id': cid, 'label': name, 'n': len(mem)})
        for m in mem:
            items[m['h']] = cid
    return {'labels': labels, 'items': items}


# ---------------------------------------------------------------- 时刻
def moments(media, titler=None):
    """按时间线切段：隔 45 分钟以上、或位置跳了 2 公里以上 → 新的一段。每段请模型起标题、打纪念价值。
    titler(caps, place, when, key) → (title, memo)；key 是成员的哈希，调用方拿它做缓存（成员没变就不重算）。"""
    xs = sorted([m for m in media if _t(m['taken'])], key=lambda m: _t(m['taken']))
    segs, cur, last_gps = [], [], None
    for m in xs:
        gps = (m['lat'], m['lon']) if m.get('lat') is not None and m.get('lon') is not None else None
        if cur:
            gap = _t(m['taken']) - _t(cur[-1]['taken'])
            jump = gps and last_gps and km(gps, last_gps) > MOMENT_KM
            if gap > MOMENT_GAP or jump:
                segs.append(cur); cur = []; last_gps = None
        cur.append(m)
        if gps:
            last_gps = gps
    if cur:
        segs.append(cur)
    labels, items = [], {}
    for i, mem in enumerate(segs, 1):
        places = Counter(m['place'] for m in mem if m.get('place'))
        place = places.most_common(1)[0][0] if places else None
        memos = [(m.get('tags') or {}).get('memo') or 0 for m in mem]
        caps = [m['caption'] for m in sorted(mem, key=lambda m: -(m['score'] or 0)) if m.get('caption')]
        title, memo = None, None
        if titler and caps:
            key = hashlib.sha1('|'.join(sorted(m['h'] for m in mem)).encode()).hexdigest()
            title, memo = titler(caps, place, f"{mem[0]['taken'][:16].replace('T', ' ')} – {mem[-1]['taken'][11:16]}", key)
        if not title:
            title = (place or '').split(' · ')[0] or None
        # 模型给整段打的分不能高过这段里最好的那张（避免一段随手拍被标成 ★）；
        # ≥4（★）还要这段里至少有两张 ≥4、或者一张 5 —— 一张好照片撑不起一整段
        mm = max(memos) if memos else 0
        memo = min(memo, mm) if memo else mm
        if memo >= 4 and not (sum(x >= 4 for x in memos) >= 2 or mm >= 5):
            memo = 3
        cover = max(mem, key=lambda m: ((m.get('tags') or {}).get('memo') or 0) + 2 * (m['score'] or 0))
        labels.append({'id': i, 'title': title, 'start': mem[0]['taken'], 'end': mem[-1]['taken'], 'place': place,
                       'n': len(mem), 'memo': memo or None, 'cover': cover['h']})
        for m in mem:
            items[m['h']] = i
    # ★ 只给最值得的那一小撮：超过三分之一（至少留 3 段）的，按分数和张数排后面的降成 3
    #  （测试集上原来 13 段里 11 段带 ★，等于没标）
    star = sorted((l for l in labels if (l['memo'] or 0) >= 4), key=lambda l: (-(l['memo'] or 0), -l['n']))
    for l in star[max(STAR_MIN, math.ceil(len(labels) * STAR_FRAC)):]:
        l['memo'] = 3
    return {'labels': labels, 'items': items}
