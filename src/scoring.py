"""
每晚睡眠评分

把单晚分析结果（statistics）压缩成一组可跨晚比较的指标，并给出一个 0~100 的
睡眠分（越高越好）与文字等级。评分是经验启发式，非医学诊断，权重见 config。
"""
import re

from . import config

# 从文件名兜底解析录音日期（历史报告可能没有 recording_started_at 字段）
_DATE_IN_NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _date_from_filename(path):
    if not path:
        return None
    m = _DATE_IN_NAME.search(str(path))
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _label_for_score(score):
    """按 config.SCORE_LABELS 把分数映射成文字等级。"""
    for lower, label in config.SCORE_LABELS:
        if score >= lower:
            return label
    return config.SCORE_LABELS[-1][1]


def compute_score(stats):
    """
    根据统计量计算睡眠分与归一化指标。

    Args:
        stats: analyze_audio 返回的 statistics 字典。

    Returns:
        dict: 包含 score / label / 各类每小时次数 / 发声占比 等可比较指标。
    """
    hours = stats.get("total_duration_hours", 0) or 0
    # 防止极短录音把"每小时次数"放大到失真：不足 0.1 小时按 0.1 计
    safe_hours = max(hours, 0.1)

    counts = {k: stats.get(k, {}).get("count", 0) for k in config.SOUND_TYPES}
    times = {k: stats.get(k, {}).get("total_time", 0) for k in config.SOUND_TYPES}

    snore_per_hour = counts["snoring"] / safe_hours
    grind_per_hour = counts["grinding"] / safe_hours
    talk_per_hour = counts["talking"] / safe_hours

    total_dur = stats.get("total_duration", 0) or 0
    disturb_time = sum(times.values())
    disturb_pct = round((disturb_time / total_dur * 100), 2) if total_dur > 0 else 0.0

    w = config.SCORE_WEIGHTS
    penalty = (
        w["snore_per_hour"] * snore_per_hour
        + w["grind_per_hour"] * grind_per_hour
        + w["talk_per_hour"] * talk_per_hour
        + w["disturb_pct"] * disturb_pct
    )
    score = round(max(0.0, min(100.0, 100.0 - penalty)), 1)

    return {
        "score": score,
        "label": _label_for_score(score),
        "hours": round(hours, 2),
        "snore_count": counts["snoring"],
        "grind_count": counts["grinding"],
        "talk_count": counts["talking"],
        "snore_per_hour": round(snore_per_hour, 2),
        "grind_per_hour": round(grind_per_hour, 2),
        "talk_per_hour": round(talk_per_hour, 2),
        "disturb_pct": disturb_pct,
    }


def night_summary(result):
    """
    从一份完整分析结果里抽取"单晚摘要"：日期 + 评分 + 关键指标。
    日期取 metadata.recording_started_at（若有），否则用 analyzed_at。
    """
    meta = result.get("metadata", {})
    date = (
        meta.get("recording_started_at")
        or _date_from_filename(meta.get("file"))
        or meta.get("analyzed_at")
    )
    summary = {
        "date": date,
        "file": meta.get("file"),
        "backend": meta.get("backend"),
    }
    summary.update(compute_score(result["statistics"]))
    return summary
