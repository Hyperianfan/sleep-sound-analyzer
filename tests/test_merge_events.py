"""_merge_events 合并逻辑锁定。"""
from src import config


def test_empty_returns_empty(analyzer):
    assert analyzer._merge_events([]) == []


def test_merges_adjacent_same_type_and_keeps_max_confidence(analyzer):
    events = [
        {"type": "snoring", "timestamp": 0.0, "confidence": 0.6, "duration": 0.5},
        {"type": "snoring", "timestamp": 0.5, "confidence": 0.8, "duration": 0.5},
    ]
    merged = analyzer._merge_events(events)
    assert len(merged) == 1
    assert merged[0]["confidence"] == 0.8


def test_different_types_not_merged(analyzer):
    events = [
        {"type": "snoring", "timestamp": 0.0, "confidence": 0.6, "duration": 0.5},
        {"type": "talking", "timestamp": 0.5, "confidence": 0.6, "duration": 0.5},
    ]
    assert len(analyzer._merge_events(events)) == 2


def test_large_gap_splits_events(analyzer):
    gap = config.EVENT_GAP_THRESHOLD + 1.0
    events = [
        {"type": "snoring", "timestamp": 0.0, "confidence": 0.6, "duration": 0.5},
        {"type": "snoring", "timestamp": 0.5 + gap, "confidence": 0.6, "duration": 0.5},
    ]
    assert len(analyzer._merge_events(events)) == 2
