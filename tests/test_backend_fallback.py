"""验证 yamnet/hybrid 后端在依赖缺失时优雅回退到 rule。"""
from src.analyzer import SleepSoundAnalyzer


def test_hybrid_falls_back_to_rule_when_yamnet_unavailable(make_wav):
    a = SleepSoundAnalyzer(backend="hybrid")
    # 模拟 tensorflow 不可用：_get_yamnet 返回 None
    a._get_yamnet = lambda: None

    res = a.analyze_audio(make_wav(), apply_noise_reduction=False)
    # 实际生效后端应回退为 rule（不抛异常、仍产出结果）
    assert res["metadata"]["backend"] == "rule"
    assert isinstance(res["events"], list)


def test_invalid_backend_rejected():
    import pytest
    with pytest.raises(ValueError):
        SleepSoundAnalyzer(backend="nope")
