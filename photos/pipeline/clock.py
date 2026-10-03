"""相机时钟对齐：把「不知道自己在哪个时区」的相机照片，对齐到同行手机的时间上。

为什么要这个：单反 / 微单的时钟是人手动设的，出国常常忘了改（这次两台 Canon R5 都还是北京时间），
而且相机导出的 JPEG 经常把时区标签（EXIF OffsetTimeOriginal）弄丢、也没有 GPS ——
那照片里就只剩一个「相机表盘上的钟点」，不知道比当地快了几小时。时间线上它们会跑到六个小时以后去。

手机的时间是对的（自动校时 + GPS 知道在哪个时区）。一起出去玩的时候，同一个场景通常相机拍几张、手机也拍几张，
两张照片长得很像（图像向量很接近）。所以：
  对每台相机（按机身序列号认；没有序列号就按「型号 + 上传人」）：
    1. 每张相机照片找最像的那张有 GPS 的手机照片（SigLIP 余弦 ≥ SIM）
    2. 记下「相机钟点 − 手机那张的 UTC 时间」—— 这个差只取决于相机时钟设在哪、走得准不准，和拍摄地在哪无关
       （同一台相机在冰岛、挪威拍，这个数是同一个）
    3. 取最集中的那一团的中位数 = 这台相机的时钟偏移（含走快走慢，取整到 5 分钟）
  证据不够（同场景的配对少于 MIN_PAIRS，或者太分散）→ 退回同一机身别的文件里写着的时区（比如 +08:00）；
  再没有 → 不动（当它就是当地时间）。
得到 UTC 之后，再换成拍摄地的当地时间：拍摄地 = 时间上最近的那张有 GPS 照片所在的时区（±3 小时内），
否则按行程表。

在真实数据上量过（2026-10-03，两台 R5，466 张有 GPS 的手机照片）：
  机身 …1986（_I6A，另一批文件写着 +08:00）：133 对，相机比挪威当地快 6.0～6.75 小时 → 北京时间、外加时钟快约半小时
  机身 …0423（_63A，没有任何参照）：挪威那几天 +6、冰岛那几天 +8 → 换成 UTC 是同一个数，同样是北京时间
只看时间不看画面（「±10 分钟内有没有手机照片」）是不行的：手机全天都在拍，会撞上假的峰。
精度：同一场景的相机和手机照片本来就不是同一秒拍的，量出来的偏移里混着「隔了几分钟才拍」—— 先拍后拍
大体对半时会抵消，结果取整到 5 分钟；所以对齐后的时间准到几分钟，不是准到秒。
"""
from datetime import datetime, timedelta, timezone

import numpy as np

SIM = 0.85          # 「同一个场景」的图像相似度门槛
MIN_PAIRS = 5       # 至少这么多对才相信对齐结果
WIN = 0.5           # 小时：最集中那一团的半宽
NEAR_TZ = 3 * 3600  # 秒：用多近的有 GPS 照片来定拍摄地时区


def _ts(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()      # 当成 UTC 读钟点，只用来做差


def _fmt(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')


def group_key(m):
    """同一台相机：机身序列号最可靠；没有就退回「型号 + 上传人」"""
    if m.get('cser'):
        return f"sn:{m['cser']}"
    return f"{m.get('cam') or '?'}|{m.get('up')}"


def offset_of(tzsrc):
    """'offset:+08:00' → 8.0（小时）"""
    if not tzsrc or not tzsrc.startswith('offset:'):
        return None
    s = tzsrc[7:]
    sign = -1 if s[0] == '-' else 1
    hh, mm = s.lstrip('+-').split(':')
    return sign * (int(hh) + int(mm) / 60)


def estimate(values):
    """一组「相机 − 手机」小时差 → (偏移, 支持的对数)。找 ±WIN 小时内点最多的那一团，取中位数"""
    v = np.sort(np.asarray(values, dtype=float))
    if len(v) < MIN_PAIRS:
        return None, len(v)
    lo = np.searchsorted(v, v - WIN, 'left')
    hi = np.searchsorted(v, v + WIN, 'right')
    i = int(np.argmax(hi - lo))
    core = v[lo[i]:hi[i]]
    if len(core) < MIN_PAIRS or len(core) < 0.35 * len(v):
        return None, len(core)
    return round(float(np.median(core)) * 12) / 12, len(core)          # 取整到 5 分钟


def align(media, E, tz_at, utc_to_tz, trip_tz):
    """media：/api/pipe/media 的行（要有 h, kind, taken, ctime, cser, tzsrc, cam, up, lat, lon, src）
    E：h → 单位化的图像向量。tz_at(lat, lon) → IANA 时区；utc_to_tz(utc_str, tz) → 当地钟点；
    trip_tz(utc_str) → 按行程表猜的 IANA 时区或 None。
    返回 (changes, report)：changes = [(h, 新的 taken, tzsrc)]，report = 每台相机一行说明"""
    # 参照点：有 GPS、时间可信的照片（手机）→ UTC
    refs = []
    for m in media:
        if m.get('src') or m.get('lat') is None or not m.get('taken') or m.get('tzsrc') == 'none':
            continue
        tz = tz_at(m['lat'], m['lon'])
        if not tz:
            continue
        local = datetime.fromisoformat(m['taken'])
        try:
            from zoneinfo import ZoneInfo
            utc = local.replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc).timestamp()
        except Exception:        # noqa: BLE001
            continue
        refs.append((m['h'], utc, tz))
    refs.sort(key=lambda r: r[1])
    rts = np.array([r[1] for r in refs]) if refs else np.zeros(0)
    rh = [r[0] for r in refs if r[0] in E]
    RM = np.stack([E[h] for h in rh]) if rh else None
    rutc = {r[0]: r[1] for r in refs}

    def tz_near(utc):
        if len(rts):
            i = int(np.searchsorted(rts, utc))
            best = min((j for j in (i - 1, i) if 0 <= j < len(rts)), key=lambda j: abs(rts[j] - utc), default=None)
            if best is not None and abs(rts[best] - utc) <= NEAR_TZ:
                return refs[best][2]
        return trip_tz(_fmt(utc))

    # 已知时区：同一机身别的文件里写着的
    zone = {}
    for m in media:
        o = offset_of(m.get('tzsrc'))
        if o is not None and m.get('cser'):
            zone.setdefault(f"sn:{m['cser']}", o)

    groups = {}
    for m in media:
        src = m.get('tzsrc') or ''
        if m.get('src') or m.get('kind') != 'image' or not m.get('ctime') or m.get('lat') is not None \
                or not (src == 'none' or src.startswith('aligned:') or src.startswith('offset:')):
            continue                                # 没 GPS 的相机照片（有时区标签的也算进来：同一机身的时钟走快走慢它也一样）
        groups.setdefault(group_key(m), []).append(m)

    changes, report = [], []
    for g, ms in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        vals = []
        if RM is not None:
            hs = [m['h'] for m in ms if m['h'] in E]
            if hs:
                S = np.stack([E[h] for h in hs]) @ RM.T
                j, s = S.argmax(1), S.max(1)
                ct = {m['h']: _ts(m['ctime']) for m in ms}
                vals = [(ct[h] - rutc[rh[jj]]) / 3600 for h, jj, ss in zip(hs, j, s) if ss >= SIM]
        off, n = estimate(vals)
        why = f'{n} 对同场景照片' if off is not None else None
        if off is None and g in zone:
            off, why = zone[g], '同机身其它文件的时区标签'
        how = f'aligned:{off:+.2f}h' if off is not None else None   # 只含偏移本身：证据数变了不算变化，免得每次聚类都重写
        if off is None:
            report.append(f'{g}: {len(ms)} 张 · 证据不够（同场景配对 {len(vals)}，最集中 {n}），不动')
            continue
        moved = 0
        # 对齐量出来的偏移含时钟走快走慢 → 整台相机都用它；只靠时区标签兜底时，带标签的文件本来就是对的，不动
        for m in (ms if why and '同场景' in why else [m for m in ms if not (m.get('tzsrc') or '').startswith('offset:')]):
            utc = _ts(m['ctime']) - off * 3600
            tz = tz_near(utc)
            new = utc_to_tz(_fmt(utc), tz) if tz else _fmt(utc + off * 3600)
            if not m.get('taken') or abs(_ts(new) - _ts(m['taken'])) >= 300 or m.get('tzsrc') != how:
                changes.append((m['h'], new, how))
                moved += 1
        report.append(f'{g}: {len(ms)} 张 · 相机钟比 UTC 快 {off:+.2f} 小时（依据：{why}）· 要改 {moved} 张')
    return changes, report
