"""_generate_suggestions 阈值行为锁定（阈值来自 config.SUGGESTION_THRESHOLDS）。"""
import pytest


def _levels(analyzer, snore=0, grind=0, talk=0):
    stats = {
        "snoring": {"count": snore},
        "grinding": {"count": grind},
        "talking": {"count": talk},
    }
    return [(s["type"], s["level"]) for s in analyzer._generate_suggestions(stats)]


def test_no_issues_gives_single_success(analyzer):
    assert _levels(analyzer) == [("general", "success")]


def test_thresholds_are_strictly_greater(analyzer):
    # 恰好等于阈值（30/10/5）不应触发任何建议
    assert _levels(analyzer, snore=30, grind=10, talk=5) == [("general", "success")]


@pytest.mark.parametrize("count,level", [(31, "info"), (60, "info"), (61, "warning")])
def test_snoring_levels(analyzer, count, level):
    assert ("snoring", level) in _levels(analyzer, snore=count)


@pytest.mark.parametrize("count,level", [(11, "info"), (20, "info"), (21, "warning")])
def test_grinding_levels(analyzer, count, level):
    assert ("grinding", level) in _levels(analyzer, grind=count)


def test_talking_info_only(analyzer):
    assert ("talking", "info") in _levels(analyzer, talk=6)


def test_multiple_issues_combine(analyzer):
    levels = _levels(analyzer, snore=61, grind=21, talk=6)
    types = {t for t, _ in levels}
    assert {"snoring", "grinding", "talking"} <= types
    # 有问题时不应再附带 general/success
    assert ("general", "success") not in levels
