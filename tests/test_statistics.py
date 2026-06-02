"""_calculate_statistics 行为锁定。"""


def test_counts_times_and_percentages(analyzer):
    events = [
        {"type": "snoring", "timestamp": 0, "confidence": 0.7, "duration": 0.5},
        {"type": "snoring", "timestamp": 1, "confidence": 0.7, "duration": 1.5},
        {"type": "talking", "timestamp": 5, "confidence": 0.6, "duration": 2.0},
    ]
    st = analyzer._calculate_statistics(events, total_duration=100.0)

    # 键顺序固定（影响报告 JSON 结构）
    assert list(st.keys()) == [
        "total_duration", "total_duration_hours", "snoring", "grinding", "talking",
    ]
    assert st["snoring"] == {"count": 2, "total_time": 2.0, "percentage": 2.0}
    assert st["talking"] == {"count": 1, "total_time": 2.0, "percentage": 2.0}
    assert st["grinding"] == {"count": 0, "total_time": 0, "percentage": 0}


def test_total_duration_hours(analyzer):
    st = analyzer._calculate_statistics([], total_duration=3600.0)
    assert st["total_duration"] == 3600.0
    assert st["total_duration_hours"] == 1.0


def test_zero_duration_no_division_error(analyzer):
    st = analyzer._calculate_statistics([], total_duration=0.0)
    assert st["snoring"]["percentage"] == 0
    assert st["grinding"]["percentage"] == 0
    assert st["talking"]["percentage"] == 0


def test_unknown_event_type_ignored(analyzer):
    events = [{"type": "unknown", "timestamp": 0, "confidence": 0.1, "duration": 0.5}]
    st = analyzer._calculate_statistics(events, total_duration=10.0)
    assert st["snoring"]["count"] == 0
