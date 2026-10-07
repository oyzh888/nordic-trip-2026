#!/usr/bin/env python3
"""相机时钟对齐（pipeline/clock.py）的离线测试：造一台「北京时间、还快 15 分钟」的相机，在冰岛和挪威各拍一段，
旁边有手机（有 GPS、时间准）拍同样的场景。不连服务器、不用 GPU。

    python test/clock_test.py
"""
import os, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pipeline'))
import clock  # noqa: E402

results = []
def check(name, ok, detail=''):
    results.append(ok); print(('PASS  ' if ok else 'FAIL  ') + name + (f'  — {detail}' if detail != '' else ''))

REYK, OSLO = (64.14, -21.93), (68.2, 13.6)
TZ = {REYK: 'Atlantic/Reykjavik', OSLO: 'Europe/Oslo'}
tz_at = lambda la, lo: TZ.get((la, lo))
utc_to_tz = lambda utc, tz: datetime.fromisoformat(utc).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz)).strftime('%Y-%m-%dT%H:%M:%S')
trip = lambda utc: 'Atlantic/Reykjavik' if utc < '2026-09-29T20:05' else 'Europe/Oslo'
rng = np.random.default_rng(7)
fmt = lambda d: d.strftime('%Y-%m-%dT%H:%M:%S')

def vec():
    v = rng.normal(size=64); return v / np.linalg.norm(v)

def scene(media, E, place, utc, n_cam, cser='SN1', cam_off=8.25, up=1, tzsrc='none', phones=2):
    """一个场景：手机拍 phones 张（准时间 + GPS），相机拍 n_cam 张（钟点 = UTC + cam_off，没 GPS）"""
    base = vec()
    truth = {}
    for k in range(phones):
        h = f'p{len(media)}'
        t = utc + timedelta(minutes=k)
        media.append({'h': h, 'kind': 'image', 'lat': place[0], 'lon': place[1], 'tzsrc': 'gps', 'cam': 'Apple iPhone',
                      'taken': utc_to_tz(fmt(t), TZ[place]), 'up': up})
        E[h] = base + 0.05 * vec(); E[h] /= np.linalg.norm(E[h])
    for k in range(n_cam):
        h = f'c{len(media)}'
        t = utc + timedelta(minutes=(-2, 1, 3, -1)[k % 4])          # 相机有时先拍、有时后拍（真实情况），不总在手机之后
        media.append({'h': h, 'kind': 'image', 'lat': None, 'lon': None, 'tzsrc': tzsrc, 'cam': 'Canon EOS R5', 'cser': cser,
                      'ctime': fmt(t + timedelta(hours=cam_off)), 'taken': fmt(t + timedelta(hours=cam_off)), 'up': up})
        E[h] = base + 0.08 * vec(); E[h] /= np.linalg.norm(E[h])
        truth[h] = utc_to_tz(fmt(t), TZ[place])
    return truth

# 1) 冰岛 4 个场景 + 挪威 4 个场景，相机北京时间 +15 分钟
media, E, truth = [], {}, {}
for d in range(4):
    truth |= scene(media, E, REYK, datetime(2026, 9, 26 + d, 14, 0), 3)
for d in range(4):
    truth |= scene(media, E, OSLO, datetime(2026, 9, 30, 11, 0) + timedelta(days=d), 3)
ch, rep = clock.align(media, E, tz_at, utc_to_tz, trip)
new = {h: t for h, t, _ in ch}
off = [c[2] for c in ch][:1]
check('量出相机钟比 UTC 快 8.25 小时（北京时间 + 快 15 分钟）', off == ['aligned:+8.25h'], rep)
err = max(abs((datetime.fromisoformat(new[h]) - datetime.fromisoformat(t)).total_seconds()) for h, t in truth.items())
check('24 张相机照片全部换成拍摄地当地时间（冰岛 UTC+0、挪威 UTC+2 各自对，误差 ≤ 5 分钟）', len(new) == 24 and err <= 300, f'最大误差 {err:.0f} 秒')

# 2) 再跑一遍：已经对过的不再改（不然每次聚类都在烧免费额度）
for m in media:
    if m['h'] in new:
        m['taken'] = new[m['h']]; m['tzsrc'] = dict((h, s) for h, _, s in ch)[m['h']]
ch2, _ = clock.align(media, E, tz_at, utc_to_tz, trip)
check('再跑一遍 → 一张都不改', ch2 == [], len(ch2))

# 3) 证据不够（只有 1 个场景、3 对）→ 不动
m3, E3 = [], {}
scene(m3, E3, OSLO, datetime(2026, 10, 1, 12), 3, cser='SN2')
ch3, rep3 = clock.align(m3, E3, tz_at, utc_to_tz, trip)
check('同场景配对不到 5 对 → 不动（宁可不改，不乱改）', ch3 == [], rep3)

# 4) 证据不够、但同一机身别的文件写着 +08:00 → 按标签换算
m4, E4 = [], {}
t4 = scene(m4, E4, OSLO, datetime(2026, 10, 1, 12), 3, cser='SN3', cam_off=8)
m4.append({'h': 'tagged', 'kind': 'image', 'lat': None, 'tzsrc': 'offset:+08:00', 'cser': 'SN3', 'cam': 'Canon EOS R5',
           'ctime': '2026-10-01T20:00:00', 'taken': '2026-10-01T14:00:00'})
ch4, rep4 = clock.align(m4, E4, tz_at, utc_to_tz, trip)
n4 = {h: t for h, t, _ in ch4}
check('证据不够时退回同机身的时区标签 +08:00（带标签那张本来就对，不动）',
      set(n4) == set(t4) and all(n4[h] == t4[h] for h in t4) and 'tagged' not in n4, rep4)

# 5) 手机照片不像（不同场景）→ 不会被时间上碰巧挨着的手机照片带偏
m5, E5 = [], {}
for d in range(6):
    scene(m5, E5, OSLO, datetime(2026, 10, 1 + d % 3, 9 + d), 2, cser='SN4')
for m in m5:
    if m['h'].startswith('c'):
        E5[m['h']] = vec()                                       # 相机照片换成和谁都不像的画面
ch5, rep5 = clock.align(m5, E5, tz_at, utc_to_tz, trip)
check('画面对不上 → 不对齐（只看时间会撞上假的峰）', ch5 == [], rep5)

ok = sum(results); print(f'\n{ok}/{len(results)} 通过')
sys.exit(0 if ok == len(results) else 1)
