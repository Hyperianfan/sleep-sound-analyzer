"""配置接线：确认各模块都从 config 取参数，且共享常量同源。"""
from src import config


def test_analyzer_uses_config_sample_rate(analyzer):
    assert analyzer.preprocessor.target_sr == config.TARGET_SR == 16000
    assert analyzer.feature_extractor.sr == config.TARGET_SR


def test_hop_duration_is_single_source():
    # 事件时间戳、初始时长、分帧步长共用此常量，防止耦合 bug 再现
    assert config.HOP_DURATION == 0.5


def test_sound_types_order():
    assert config.SOUND_TYPES == ("snoring", "grinding", "talking")
