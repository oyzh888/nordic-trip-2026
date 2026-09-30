#!/usr/bin/env python3
"""把 trip_evaluator 的打分结果渲染成 site/eval/index.html（自包含单文件）.

Usage: python3 notes/_research/render_eval_page.py
输出: site/eval/index.html
"""
import html
import pathlib

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from trip_evaluator import DIMENSIONS, DIM_BY_ID, DIM_IDS, evaluate_plan
from trip_plans import PLANS

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "site" / "eval" / "index.html"


def esc(s):
    return html.escape(str(s))


def score_class(s):
    if s <= 2:
        return "bad"
    if s == 3:
        return "warn"
    if s == 4:
        return "ok"
    return "good"


def render():
    reports = {k: evaluate_plan(v) for k, v in PLANS.items()}
    order = ["current", "chill", "max", "safe"]

    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>行程方案评估 · Nordic Trip 2026</title>
<style>
:root { --bg:#0f1420; --card:#18202f; --line:#2a3550; --txt:#e8ecf4; --mut:#9aa6bd; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;
  line-height:1.6; padding:16px; }
.wrap { max-width:1060px; margin:0 auto; }
h1 { font-size:22px; margin:8px 0 4px; }
.sub { color:var(--mut); font-size:13px; margin-bottom:20px; }
h2 { font-size:18px; margin:28px 0 10px; border-left:4px solid #5aa2ff; padding-left:10px; }
h3 { font-size:16px; margin:20px 0 8px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px; margin-bottom:14px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { border:1px solid var(--line); padding:6px 8px; text-align:center; }
th { background:#202a40; font-weight:600; white-space:nowrap; }
td:first-child, th:first-child { text-align:left; white-space:nowrap; }
.bad { background:rgba(255,90,90,.16); color:#ff9a9a; font-weight:700; }
.warn { background:rgba(255,170,60,.14); color:#ffc578; font-weight:700; }
.ok { background:rgba(255,235,120,.10); color:#ffe9a8; }
.good { background:rgba(90,220,140,.13); color:#9df0bd; font-weight:700; }
.dim { display:inline-block; background:#202a40; border:1px solid var(--line);
  border-radius:8px; padding:8px 10px; margin:0 8px 8px 0; font-size:13px; }
.dim b { color:#8fc1ff; }
.scale { font-size:12px; color:var(--mut); }
details { margin-top:8px; }
summary { cursor:pointer; color:#8fc1ff; font-size:13px; }
.note { font-size:12.5px; color:var(--mut); margin:4px 0; }
.note b { color:var(--txt); font-weight:600; }
.total { font-size:15px; font-weight:700; }
.kv { display:flex; gap:8px; flex-wrap:wrap; font-size:13px; margin:6px 0; }
.kv span { background:#202a40; border-radius:6px; padding:2px 8px; }
a { color:#8fc1ff; }
@media (max-width:640px){ table{ font-size:11px; } th,td{ padding:4px 5px; } }
</style>
</head>
<body><div class="wrap">
<h1>🧭 行程方案评估</h1>
<div class="sub">Nordic Trip 2026 · 9/30–10/6 挪威段 · 8 维度 × 1–6 分制 · 分数由评估器对照量表给出，依据见各天备注</div>
""")

    # ---- 维度说明
    parts.append("<h2>评估维度</h2><div class='card'>")
    for d in DIMENSIONS:
        parts.append(f"<div class='dim'><b>{esc(d.name)}</b> · {esc(d.question)}</div>")
    parts.append(
        "<div class='scale'>量表：1 很差（不可行/致命）· 2 差（大问题）· 3 及格偏下（偏紧/偏累）· "
        "4 及格偏上（可接受）· 5 好 · 6 优秀</div></div>"
    )

    # ---- 横向对比
    parts.append("<h2>横向对比（维度平均分）</h2><div class='card' style='overflow-x:auto'>")
    parts.append("<table><tr><th>维度</th>" + "".join(
        f"<th>{esc(reports[k].label)}<br><span class='total'>{reports[k].overall}</span></th>"
        for k in order) + "</tr>")
    for dim in DIM_IDS:
        best = max(reports[k].dim_avg[dim] for k in order)
        row = f"<tr><td>{esc(DIM_BY_ID[dim].name)}</td>"
        for k in order:
            v = reports[k].dim_avg[dim]
            star = " ★" if v == best and v > 0 else ""
            row += f"<td class='{score_class(round(v))}'>{v:.2f}{star}</td>"
        parts.append(row + "</tr>")
    parts.append("</table><div class='scale'>★ = 该维度最高分 · 表头数字为方案总分</div></div>")

    # ---- 各方案逐天
    for k in order:
        rep = reports[k]
        parts.append(f"<h2>{esc(rep.label)} <span class='total'>总分 {rep.overall}/6</span></h2>")
        parts.append("<div class='card' style='overflow-x:auto'><table><tr><th>日期</th>" +
                     "".join(f"<th>{esc(DIM_BY_ID[d].name)}</th>" for d in DIM_IDS) + "</tr>")
        for day in rep.days:
            parts.append(f"<tr><td>{esc(day.date)}<br><span class='scale'>{esc(day.title)}</span></td>" +
                         "".join(f"<td class='{score_class(day.scores[d])}'>{day.scores[d]}</td>"
                                 for d in DIM_IDS) + "</tr>")
        parts.append("</table>")
        for day in rep.days:
            parts.append(f"<details><summary>{esc(day.date)} 打分依据</summary>")
            for d in DIM_IDS:
                parts.append(f"<div class='note'><b>{esc(DIM_BY_ID[d].name)} {day.scores[d]}：</b>"
                             f"{esc(day.notes[d])}</div>")
            parts.append("</details>")
        parts.append("</div>")

    # ---- 结论
    parts.append("""<h2>结论</h2><div class="card">
<div class="note"><b>当前计划 4.09：</b>最大三个坑 — 10/4 待定、10/5 航班未出票、10/2 转场紧+WF816未核实。</div>
<div class="note"><b>A·体力优先 4.61：</b>10/1 砍爬山早回桑拿、10/4 纯 chill 本地日；体力拉到 4.71，代价是光线只到 4.00。</div>
<div class="note"><b>B·体验拉满 4.30：</b>光线 4.57 全场最高，但体力 3.71、风险 3.57，第 7/8 天连轴转。</div>
<div class="note"><b>C·稳妥优先 4.59：</b>不改行程、只做核实动作（拿 Tromsø 入住方式、核 WF816、10/5 提前出票、10/2 提前到机场）；订单 5.29、风险 4.43 全场最高。</div>
<div class="note"><b>建议：</b>C 的核实动作是白捡分，先做；A+C 可叠加（chill 的 10/4 + C 的核实），预计 4.7+。</div>
</div>""")

    parts.append("<div class='sub'>由 trip_evaluator.py 生成 · 改行程后重跑 render_eval_page.py 即可更新</div>")
    parts.append("</div></body></html>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    render()
