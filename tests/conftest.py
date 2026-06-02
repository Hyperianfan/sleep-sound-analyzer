"""共享 fixtures。"""
import numpy as np
import soundfile as sf
import pytest

from src import config
from src.analyzer import SleepSoundAnalyzer


@pytest.fixture(scope="session")
def analyzer():
    """整套测试共用一个分析器实例。固定用规则后端：单测验证的是规则管线与
    事件合并/统计逻辑，不应依赖 YAMNet 模型下载。"""
    return SleepSoundAnalyzer(backend="rule")


@pytest.fixture
def make_wav(tmp_path):
    """生成一段短合成音频，返回文件路径（默认 6 秒、150Hz 正弦）。"""
    def _make(seconds=6.0, freq=150.0, sr=config.TARGET_SR, name="clip.wav"):
        t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
        sig = (0.1 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        path = tmp_path / name
        sf.write(path, sig, sr)
        return str(path)
    return _make
