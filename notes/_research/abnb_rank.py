#!/usr/bin/env python3
"""给每城的 Airbnb 候选打四个维度的分，并写一句中文「它的特点是什么」。

Steve 的问题（2026-09-24）：「它们的特点是什么 —— 是靠近好玩的地方，还是住宿环境好？」
所以分四个维度，每个维度的分数来源必须能说清楚：
  📍 位置   = 到这座城「好玩的核心点」的步行距离（我算的，用房源页坐标；Airbnb 坐标有几十~一两百米的模糊）
  🛋 舒适   = 页面上写了的设施：书桌 / 网速 / 空调 / 电梯 / 洗衣机 + 评论数（评论太少不确定）
  🏛 特色   = 房子本身有没有性格（老建筑、景观、设计）—— 这一项只能靠读描述判断，交给 Claude，1–5 分
  💰 性价比 = 这城候选里的价格分位
Claude 只负责「特色分 + 一句中文特点 + 缺点」，**不碰距离和价格**（那些是算出来的）。

Usage: python3 abnb_rank.py <city> [<city> ...]   → out_abnb_rank_<city>.json
"""
import json
import math
import sys

sys.path.insert(0, "/sensei-fs-3/users/zouyang/code/steve/opus5-bedrock")

# 每城「好玩的核心点」：逐日表里的锚点 + 一个城市中心。步行按 4.5 km/h、直线 × 1.3 绕路系数
CORE = {
    # 海滩 / 河边 / 公园是一条线，不是一个点 → 写成沿线几个点，取最近的那个
    #（第一版只放了 Opéra 海滩一个点，结果「Negresco 后面、海边 2 分钟」那套被算成 16 分钟）
    "nice": {"Masséna 广场": [(43.6975, 7.2703)], "老城 Cours Saleya": [(43.6955, 7.2757)],
             "海滩": [(43.6945, 7.2560), (43.6947, 7.2610), (43.6950, 7.2650), (43.6952, 7.2701),
                    (43.6945, 7.2765), (43.6925, 7.2830)],
             "Nice-Ville 火车站": [(43.7046, 7.2616)]},
    "lis": {"Rossio / Baixa": [(38.7139, -9.1394)], "Chiado": [(38.7106, -9.1426)],
            "河边": [(38.7068, -9.1403), (38.7075, -9.1366), (38.7058, -9.1447), (38.7090, -9.1300)],
            "Cais do Sodré 车站": [(38.7058, -9.1447)]},
    "lon": {"Paddington 站": [(51.5154, -0.1755)],
            "Hyde Park": [(51.5096, -0.1757), (51.5117, -0.1650), (51.5100, -0.1590), (51.5070, -0.1880)],
            "Portobello": [(51.5152, -0.2050), (51.5186, -0.2025), (51.5123, -0.2005)],
            "Marylebone": [(51.5202, -0.1520)]},
}


def km(a, b):
    r = math.pi / 180
    dl, dn = (b[0] - a[0]) * r, (b[1] - a[1]) * r
    s = math.sin(dl / 2) ** 2 + math.cos(a[0] * r) * math.cos(b[0] * r) * math.sin(dn / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(s))


def walk_min(a, b):
    return round(km(a, b) * 1.3 / 4.5 * 60)


PROMPT = """你在帮一个人挑 Airbnb。他一个人住，白天出去玩，晚上要在房间里工作 6 小时（开视频会），
不在乎吵，想要"有意思的房子"，但各方面要平衡。下面是一套房源的标题和房东描述（英文）：

标题：{title}
搜索页一句话：{st}
描述：{desc}
已知设施：{amen}

请只输出 JSON，不要别的：
{{"character": 1-5 的整数（房子本身有没有性格：老建筑/特别的景观/设计感/独特空间=高；普通公寓=1-2）,
  "hook": "一句中文，≤22 个字，说清这套房最打动人的一点（具体，别写'温馨舒适'这种空话）",
  "con": "一句中文，≤18 个字，最该注意的缺点。只能写描述或设施里**明确写了**的（没电梯、几楼、面积小、没书桌、沙发床、要爬坡等）；不许猜（不许写'可能有异味''可能不稳'这类）；他不在乎噪音，别写噪音；找不到就写'页面没写明显缺点'",
  "kind": "老建筑 / 景观 / 设计感 / 普通公寓 其中一个"}}"""


def main():
    import claude_bedrock as cb
    for city in [a for a in sys.argv[1:] if not a.startswith("--")]:
        rows = [r for r in json.load(open(f"out_abnb_detail_{city}.json"))
                if not r.get("err") and not r.get("unavailable") and r.get("lat")]
        core = CORE[city]
        prices = sorted(r["total_eur"] for r in rows)
        for r in rows:
            ll = (r["lat"], r["lng"])
            r["walk"] = {k: min(walk_min(ll, p) for p in v) for k, v in core.items()}
            r["walk_mean"] = round(sum(r["walk"].values()) / len(core))
            amen = [n for n, ok in (("书桌", r["workspace"]), ("空调", r["ac"]), ("电梯", r["elevator"]),
                                    ("洗衣机", r["washer"])) if ok]
            if r.get("wifi_mbps"):
                amen.append(f"Wi-Fi {r['wifi_mbps']} Mbps")
            r["amen"] = amen
            # 舒适分 0–5：每项设施 1 分，网速写了再加 1；评论 <10 条打折（信息不足，不是差）
            c = sum([r["workspace"], r["ac"], r["elevator"], r["washer"], bool(r.get("wifi_mbps"))])
            r["comfort"] = round(c * (0.8 if (r.get("reviews") or 0) < 10 else 1.0), 1)
            # 位置分 0–5：平均步行 ≤8 分钟 = 5，每多 5 分钟减 1
            r["loc"] = max(0.0, min(5.0, 5 - (r["walk_mean"] - 8) / 5))
            r["value"] = round(5 * (1 - prices.index(r["total_eur"]) / max(1, len(prices) - 1)), 1)
        prev = {}
        try:
            prev = {x["room"]: x for x in json.load(open(f"out_abnb_rank_{city}.json"))}
        except FileNotFoundError:
            pass
        todo = [r for r in rows if not (r["room"] in prev and prev[r["room"]].get("hook") and "--reuse" in sys.argv)]
        for r in rows:
            if r not in todo:
                r.update({k: prev[r["room"]][k] for k in ("character", "hook", "con", "kind")})
        items = [(r, PROMPT.format(title=r["title"], st=r["search_title"], desc=r["desc"][:900],
                                   amen="、".join(r["amen"]) or "页面没写")) for r in todo]
        outs = [] if not items else cb.amap([p for _, p in items], lambda p: p, model="sonnet-5", effort="low", workers=8)
        for (r, _), o in zip(items, outs):
            try:
                t = o if isinstance(o, str) else str(o)
                j = json.loads(t[t.find("{"): t.rfind("}") + 1])
            except Exception:  # noqa: BLE001
                j = {"character": 2, "hook": r["search_title"][:22], "con": "（没解析出来）", "kind": "普通公寓"}
            r.update(character=int(j.get("character", 2)), hook=j.get("hook", ""), con=j.get("con", ""),
                     kind=j.get("kind", ""))
        for r in rows:
            # 平衡分：四项等权，评分 <4.85 小扣
            r["balanced"] = round((r["loc"] + r["comfort"] + r["character"] + r["value"]) / 4
                                  - (0.3 if float(r["rating"]) < 4.85 else 0), 2)
        rows.sort(key=lambda r: -r["balanced"])
        json.dump(rows, open(f"out_abnb_rank_{city}.json", "w"), ensure_ascii=False, indent=1)
        print("==", city, len(rows))
        for r in rows[:14]:
            print(f"{r['balanced']:.2f} L{r['loc']:.1f} C{r['comfort']} X{r['character']} V{r['value']} €{r['total_eur']} "
                  f"★{r['rating']} ({r.get('reviews')}) 步行{r['walk_mean']}分 | {r['hook']} | {r['con']} | {r['room']}")


if __name__ == "__main__":
    main()
