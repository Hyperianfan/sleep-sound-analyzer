"""端到端：合成音频跑通完整分析链路。"""
import json

from src import config


def test_analyze_returns_expected_shape(analyzer, make_wav):
    res = analyzer.analyze_audio(make_wav(), apply_noise_reduction=False)
    assert set(res) == {"metadata", "statistics", "events", "suggestions"}
    assert res["metadata"]["total_frames"] > 0
    assert isinstance(res["events"], list)
    assert isinstance(res["suggestions"], list)


def test_event_timestamps_on_hop_grid(analyzer, make_wav):
    res = analyzer.analyze_audio(make_wav(seconds=6.0), apply_noise_reduction=False)
    for ev in res["events"]:
        ratio = ev["timestamp"] / config.HOP_DURATION
        assert abs(ratio - round(ratio)) < 1e-9


def test_result_is_json_serializable(analyzer, make_wav):
    res = analyzer.analyze_audio(make_wav(), apply_noise_reduction=False)
    assert json.dumps(res)  # 不抛异常即说明无 numpy 等非原生类型


def test_save_report_roundtrip(analyzer, make_wav, tmp_path):
    res = analyzer.analyze_audio(make_wav(), apply_noise_reduction=False)
    out = tmp_path / "report.json"
    analyzer.save_report(res, out)

    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["statistics"] == res["statistics"]
    assert loaded["events"] == res["events"]
