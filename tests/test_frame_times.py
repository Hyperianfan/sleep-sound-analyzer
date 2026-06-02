"""验证去静音后，帧时间戳能正确映射回原始录音的真实时间。"""
import numpy as np

from src.preprocessor import AudioPreprocessor


def test_frame_times_skip_silence():
    """原始录音：0–1s 有声、1–3s 静音、3–4s 有声。
    去静音拼接成 2s 后分帧（hop=0.5s）。第 3、4 帧应映射回 3.0s / 3.5s，
    而不是拼接坐标下的 1.0s / 1.5s。"""
    sr = 16000
    # 非静音区间（原始样本下标）：[0,1s) 和 [3s,4s)
    intervals = np.array([[0, sr], [3 * sr, 4 * sr]])

    pre = AudioPreprocessor(target_sr=sr)
    times = pre.frame_real_times(n_frames=4, intervals=intervals, sr=sr,
                                 hop_duration=0.5)

    assert times == [0.0, 0.5, 3.0, 3.5]


def test_frame_times_no_intervals_is_linear():
    """无区间信息时退化为线性时间 i*hop。"""
    sr = 16000
    pre = AudioPreprocessor(target_sr=sr)
    times = pre.frame_real_times(n_frames=3, intervals=np.empty((0, 2)), sr=sr,
                                 hop_duration=0.5)
    assert times == [0.0, 0.5, 1.0]
