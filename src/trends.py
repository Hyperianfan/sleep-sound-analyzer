"""
多晚睡眠趋势分析

输入若干"单晚摘要"（scoring.night_summary 产出），按日期排序后比较，判断整体
是在变好还是变差，并给出每项指标的变化与一段中文结论。
"""
from . import config


def _slope(values):
    """对 y=values、x=0..n-1 做最小二乘，返回斜率（每晚变化量）。n<2 返回 0。"""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den else 0.0


def _metric_change(nights, key, higher_is_better):
    """计算单项指标的首末值、变化量与方向。"""
    series = [n[key] for n in nights]
    first, last = series[0], series[-1]
    delta = round(last - first, 2)
    improved = (delta > 0) if higher_is_better else (delta < 0)
    worsened = (delta < 0) if higher_is_better else (delta > 0)
    direction = "改善" if (improved and delta != 0) else ("恶化" if worsened else "持平")
    return {
        "first": first,
        "last": last,
        "delta": delta,
        "slope_per_night": round(_slope(series), 3),
        "direction": direction,
    }


def analyze_trend(summaries):
    """
    Args:
        summaries: 单晚摘要列表（每个含 date/score/*_per_hour/disturb_pct）。

    Returns:
        dict: nights（按日期排序）、各指标变化、总体方向与中文结论。
    """
    nights = sorted(summaries, key=lambda s: (s.get("date") or ""))
    n = len(nights)

    if n == 0:
        return {"nights": [], "verdict": "没有可分析的记录。"}
    if n == 1:
        s = nights[0]
        return {
            "nights": nights,
            "verdict": (
                f"只有 1 晚记录（{s.get('date')}），睡眠分 {s['score']}（{s['label']}）。"
                "至少需要 2 晚才能比较趋势。"
            ),
        }

    # 睡眠分越高越好；其余三项（每小时次数、发声占比）越低越好
    changes = {
        "score": _metric_change(nights, "score", higher_is_better=True),
        "snore_per_hour": _metric_change(nights, "snore_per_hour", higher_is_better=False),
        "grind_per_hour": _metric_change(nights, "grind_per_hour", higher_is_better=False),
        "talk_per_hour": _metric_change(nights, "talk_per_hour", higher_is_better=False),
        "disturb_pct": _metric_change(nights, "disturb_pct", higher_is_better=False),
    }

    score_delta = changes["score"]["delta"]
    thr = config.TREND_SCORE_DELTA
    if score_delta >= thr:
        overall = "improving"
        zh = "变好"
    elif score_delta <= -thr:
        overall = "worsening"
        zh = "变差"
    else:
        overall = "stable"
        zh = "基本持平"

    best = max(nights, key=lambda s: s["score"])
    worst = min(nights, key=lambda s: s["score"])
    avg_score = round(sum(s["score"] for s in nights) / n, 1)

    verdict = (
        f"共 {n} 晚：睡眠分从 {changes['score']['first']} → {changes['score']['last']} "
        f"（{'+' if score_delta >= 0 else ''}{score_delta}），整体**{zh}**。"
        f"平均分 {avg_score}；最佳 {best['date']}（{best['score']}），"
        f"最差 {worst['date']}（{worst['score']}）。"
    )

    return {
        "nights": nights,
        "overall_direction": overall,
        "score_first": changes["score"]["first"],
        "score_last": changes["score"]["last"],
        "score_delta": score_delta,
        "score_slope_per_night": changes["score"]["slope_per_night"],
        "avg_score": avg_score,
        "best_night": {"date": best["date"], "score": best["score"]},
        "worst_night": {"date": worst["date"], "score": worst["score"]},
        "changes": changes,
        "verdict": verdict,
    }
