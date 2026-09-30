#!/usr/bin/env python3
"""Trip rationality evaluator — 旅行合理性评估器.

8 个维度 x 1-6 分制. 用法::

    from trip_evaluator import DIMENSIONS, evaluate_plan, render_report, compare_plans
    from trip_plans import PLANS
    print(render_report(evaluate_plan(PLANS["current"])))
    print(compare_plans({k: evaluate_plan(v) for k, v in PLANS.items()}))

设计说明 (honest scope):
- 分数是分析师对照量表 (rubric) 给出的判断, 不是机器算出来的"客观真理".
- 每个维度的 advise() 是规则式启发检查: 根据行程字段 (驾驶时长、
  紧张转场、未出票项等) 吐出风险提示, 供打分时参考.
- DayPlan 里的 scores 必须逐项手填并附 note; 缺 note 的维度会被校验拦下.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------- 维度与量表
@dataclass(frozen=True)
class Dimension:
    id: str
    name: str
    en: str
    question: str
    rubric: dict[int, str]


DIMENSIONS: list[Dimension] = [
    Dimension(
        id="time", name="时间账", en="Time budget",
        question="这一天的时间够不够用? 有没有被赶着走?",
        rubric={
            1: "不可行: 驾驶+游玩+等候明显超出可用时间, 必定砍行程",
            2: "很紧: 几乎没有缓冲, 一个小延误就连锁崩",
            3: "偏紧: 能走完但全程赶, 午饭都可能压缩",
            4: "可接受: 有少量缓冲, 个别点可取舍",
            5: "从容: 时间充裕, 可临时加塞或发呆",
            6: "极松: 大把空闲, 甚至可以睡个午觉",
        },
    ),
    Dimension(
        id="route", name="路线账", en="Route logic",
        question="路线顺不顺? 有没有走回头路、绕路?",
        rubric={
            1: "严重折返: 大量重复路段, 纯属浪费里程",
            2: "明显绕路: 有更顺的走法却没用",
            3: "小幅折返: 有 30 分钟以上的回头路",
            4: "基本顺路: 轻微绕行但可接受",
            5: "顺路: 单向推进, 无重复路段",
            6: "极顺: 单向+每个停靠点都在主线上",
        },
    ),
    Dimension(
        id="pace", name="体力账", en="Pace & fatigue",
        question="节奏顶不顶得住? 连续作战几天了?",
        rubric={
            1: "会累垮: 连日高强度, 当天必须砍",
            2: "很累: 长驾驶+早起晚睡叠加",
            3: "偏累: 一天紧凑, 需靠次日回血",
            4: "还行: 正常旅行强度",
            5: "轻松: 半天行程+半天休息",
            6: "度假模式: 睡到自然醒, 随缘玩",
        },
    ),
    Dimension(
        id="light", name="光线账", en="Light & aurora",
        question="关键的光线窗口抓住了吗? 日落、极光?",
        rubric={
            1: "完全错过: 该看的都在开车/睡觉",
            2: "大概率错过: 时间对不上光线",
            3: "随缘: 没特意安排, 碰运气",
            4: "有安排: 留了窗口但不精确",
            5: "卡准了: 日落/极光时间点卡进去了",
            6: "拉满: 金色时刻+蓝调+极光全覆盖",
        },
    ),
    Dimension(
        id="booking", name="订单账", en="Booking consistency",
        question="机票/酒店/租车对得上吗? 都确认了吗?",
        rubric={
            1: "对不上: 时间冲突或关键订单缺失",
            2: "多处未确认: 有实质风险",
            3: "部分未核实: 候选时间当计划用",
            4: "基本确认: 个别细节待补 (如入住方式)",
            5: "已确认: 订单都在, 小项待查",
            6: "全部实锤: 逐项核对过, 单据在手",
        },
    ),
    Dimension(
        id="cost", name="钱账", en="Cost sanity",
        question="花得值吗? 有没有价格异常?",
        rubric={
            1: "明显被坑: 有实质多付且可追回",
            2: "有异常: 价格对不上, 需核查",
            3: "偏贵: 有更便宜的等价选择",
            4: "正常: 市场价, 无硬伤",
            5: "划算: 占到便宜或结构优化",
            6: "极值: 捡漏级",
        },
    ),
    Dimension(
        id="risk", name="风险账", en="Risk & contingency",
        question="最坏情况是什么? 有备份方案吗?",
        rubric={
            1: "单点致命: 一环断全盘断, 无备份",
            2: "高风险: 紧张转场+无预案",
            3: "有隐忧:  identified 风险但没预案",
            4: "可控: 风险已知, 有粗预案",
            5: "稳妥: 关键节点有缓冲/备份",
            6: "高枕无忧: 备份套备份",
        },
    ),
    Dimension(
        id="work", name="工作账", en="Work & meetings",
        question="会议撞车吗? 开会有安静地方吗?",
        rubric={
            1: "撞车: 会议和行程硬冲突",
            2: "难受: 开车途中开会或时区折磨",
            3: "凑合: 能开但体验差",
            4: "可行: 时间错开, 条件一般",
            5: "舒服: 会议前后都有缓冲",
            6: "完美: 该开的会都在酒店安静开完",
        },
    ),
]
DIM_BY_ID = {d.id: d for d in DIMENSIONS}
DIM_IDS = [d.id for d in DIMENSIONS]


# ------------------------------------------------------------ 启发式风险检查
def advise(day: dict) -> dict[str, list[str]]:
    """根据行程字段吐出各维度的风险提示 (advisory, 非最终分数)."""
    flags: dict[str, list[str]] = {d: [] for d in DIM_IDS}
    drive = day.get("drive_hours", 0)
    if drive >= 6:
        flags["time"].append(f"驾驶 {drive}h: 当天大概率走不完")
        flags["pace"].append(f"驾驶 {drive}h: 体力透支风险")
    elif drive >= 4.5:
        flags["time"].append(f"驾驶 {drive}h: 偏紧, 需压缩停留")
        flags["pace"].append(f"驾驶 {drive}h: 偏累")
    if day.get("backtrack_km", 0) >= 40:
        flags["route"].append(f"折返约 {day['backtrack_km']}km: 路线可优化")
    if day.get("tight_connections"):
        for c in day["tight_connections"]:
            flags["risk"].append(f"紧张转场: {c}")
            flags["time"].append(f"紧张转场: {c}")
    if day.get("unticketed"):
        for u in day["unticketed"]:
            flags["booking"].append(f"未出票/未确认: {u}")
            flags["risk"].append(f"未出票/未确认: {u}")
    if day.get("entry_unknown"):
        flags["booking"].append("住宿入住方式未知")
        flags["risk"].append("住宿入住方式未知: 可能被锁门外")
    if day.get("meetings_while_driving"):
        flags["work"].append("开车途中开会: 体验差且不安全")
    if day.get("lunch_risk"):
        flags["time"].append(f"午饭风险: {day['lunch_risk']}")
    if day.get("consecutive_long_days", 0) >= 3:
        flags["pace"].append(f"连续 {day['consecutive_long_days']} 天高强度: 需安排回血")
    return flags


# ------------------------------------------------------------------ 打分模型
@dataclass
class DayPlan:
    date: str
    title: str
    scores: dict[str, int] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    fields: dict = field(default_factory=dict)  # 供 advise() 用的原始字段


@dataclass
class PlanReport:
    name: str
    label: str
    days: list[DayPlan]
    dim_avg: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0


def evaluate_plan(plan: dict) -> PlanReport:
    """校验 + 汇总一个计划. 缺维度/缺 note/分数越界都会抛错."""
    days = [DayPlan(**d) for d in plan["days"]]
    for day in days:
        for dim in DIM_IDS:
            if dim not in day.scores:
                raise ValueError(f"{day.date} 缺少维度 {dim} 的分数")
            s = day.scores[dim]
            if not (1 <= s <= 6):
                raise ValueError(f"{day.date}/{dim} 分数 {s} 越界 (1-6)")
            if dim not in day.notes or not day.notes[dim].strip():
                raise ValueError(f"{day.date}/{dim} 缺少打分依据 note")
    dim_avg = {
        dim: round(sum(d.scores[dim] for d in days) / len(days), 2) for dim in DIM_IDS
    }
    overall = round(sum(dim_avg.values()) / len(dim_avg), 2)
    return PlanReport(name=plan["name"], label=plan.get("label", plan["name"]),
                      days=days, dim_avg=dim_avg, overall=overall)


# ------------------------------------------------------------------ 报告渲染
def _bar(score: float, width: int = 12) -> str:
    filled = int(round(score / 6 * width))
    return "█" * filled + "░" * (width - filled)


def render_report(rep: PlanReport, verbose: bool = False) -> str:
    lines = [f"### {rep.label}  (总分 {rep.overall}/6)", ""]
    header = "日期       " + "".join(f"{DIM_BY_ID[d].name:^6}" for d in DIM_IDS)
    lines.append(header)
    for day in rep.days:
        row = f"{day.date} " + "".join(f"{day.scores[d]:^8}" for d in DIM_IDS)
        lines.append(row)
    lines += ["", "维度平均:"]
    for dim in DIM_IDS:
        d = DIM_BY_ID[dim]
        lines.append(f"  {d.name} {rep.dim_avg[dim]:.2f} {_bar(rep.dim_avg[dim])}")
    if verbose:
        lines.append("")
        for day in rep.days:
            lines.append(f"-- {day.date} {day.title}")
            for dim in DIM_IDS:
                lines.append(f"   [{DIM_BY_ID[dim].name} {day.scores[dim]}] {day.notes[dim]}")
    return "\n".join(lines)


def compare_plans(reports: dict[str, PlanReport]) -> str:
    names = list(reports.keys())
    lines = ["### 横向对比 (维度平均分)", ""]
    lines.append("维度     " + "".join(f"{reports[n].label[:10]:^10}" for n in names))
    for dim in DIM_IDS:
        row = f"{DIM_BY_ID[dim].name}  "
        for n in names:
            v = reports[n].dim_avg[dim]
            best = v == max(reports[m].dim_avg[dim] for m in names)
            row += f"{('*' if best else ' ')}{v:^8.2f}"
        lines.append(row)
    lines.append("总体     " + "".join(f"{reports[n].overall:^10.2f}" for n in names))
    lines.append("")
    lines.append("* = 该维度最高分")
    return "\n".join(lines)


if __name__ == "__main__":
    from trip_plans import PLANS

    reports = {k: evaluate_plan(v) for k, v in PLANS.items()}
    for rep in reports.values():
        print(render_report(rep))
        print()
    print(compare_plans(reports))
