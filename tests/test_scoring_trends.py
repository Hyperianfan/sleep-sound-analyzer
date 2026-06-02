"""每晚评分 + 多晚趋势的单元测试。"""
from src import scoring, trends


def _stats(snore=0, grind=0, talk=0, snore_t=0.0, grind_t=0.0, talk_t=0.0,
           duration=3600.0):
    """构造一个 statistics 字典。"""
    return {
        "total_duration": duration,
        "total_duration_hours": round(duration / 3600, 2),
        "snoring": {"count": snore, "total_time": snore_t, "percentage": 0},
        "grinding": {"count": grind, "total_time": grind_t, "percentage": 0},
        "talking": {"count": talk, "total_time": talk_t, "percentage": 0},
    }


def test_quiet_night_scores_high():
    s = scoring.compute_score(_stats())  # 全 0，1 小时
    assert s["score"] == 100.0
    assert s["label"] == "优"


def test_noisy_night_scores_lower():
    quiet = scoring.compute_score(_stats(snore=0))
    noisy = scoring.compute_score(_stats(snore=60, snore_t=120, duration=3600))
    assert noisy["score"] < quiet["score"]
    assert noisy["snore_per_hour"] == 60.0


def test_score_clamped_to_zero():
    s = scoring.compute_score(_stats(snore=10000, duration=3600))
    assert s["score"] == 0.0
    assert s["label"] == "差"


def test_trend_needs_two_nights():
    one = [{"date": "2026-06-01", "score": 80, "label": "良",
            "snore_per_hour": 1, "grind_per_hour": 0, "talk_per_hour": 0,
            "disturb_pct": 0.1}]
    out = trends.analyze_trend(one)
    assert "至少需要 2 晚" in out["verdict"]


def _summary(date, score):
    return {"date": date, "score": score, "label": "x",
            "snore_per_hour": (100 - score) / 5, "grind_per_hour": 0,
            "talk_per_hour": 0, "disturb_pct": 0.1}


def test_trend_improving_and_sorted():
    # 故意乱序输入，验证按日期排序后判定为变好
    out = trends.analyze_trend([
        _summary("2026-06-03", 85),
        _summary("2026-06-01", 60),
        _summary("2026-06-02", 72),
    ])
    assert [n["date"] for n in out["nights"]] == [
        "2026-06-01", "2026-06-02", "2026-06-03"]
    assert out["overall_direction"] == "improving"
    assert out["score_delta"] == 25
    assert out["changes"]["snore_per_hour"]["direction"] == "改善"


def test_trend_worsening():
    out = trends.analyze_trend([_summary("2026-06-01", 90), _summary("2026-06-02", 60)])
    assert out["overall_direction"] == "worsening"


def test_trend_stable_within_threshold():
    out = trends.analyze_trend([_summary("2026-06-01", 80), _summary("2026-06-02", 82)])
    assert out["overall_direction"] == "stable"
