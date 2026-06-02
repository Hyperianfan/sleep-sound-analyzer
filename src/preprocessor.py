"""
音频预处理模块
"""
import numpy as np
import librosa
import noisereduce as nr
from scipy import signal

from . import config


class AudioPreprocessor:
    """音频预处理器"""

    def __init__(self, target_sr=config.TARGET_SR):
        """
        初始化预处理器

        Args:
            target_sr: 目标采样率
        """
        self.target_sr = target_sr

    def load_audio(self, audio_path):
        """
        加载音频文件

        Args:
            audio_path: 音频文件路径

        Returns:
            audio: 音频数据
            sr: 采样率
        """
        audio, sr = librosa.load(audio_path, sr=self.target_sr)
        return audio, sr

    def reduce_noise(self, audio, sr):
        """
        降噪处理

        Args:
            audio: 音频数据
            sr: 采样率

        Returns:
            降噪后的音频
        """
        # 使用 noisereduce 库进行降噪
        reduced_noise = nr.reduce_noise(
            y=audio,
            sr=sr,
            stationary=True,
            prop_decrease=config.NOISE_PROP_DECREASE
        )
        return reduced_noise

    def normalize(self, audio):
        """
        音量归一化

        Args:
            audio: 音频数据

        Returns:
            归一化后的音频
        """
        return librosa.util.normalize(audio)

    def remove_silence(self, audio, top_db=config.SILENCE_TOP_DB,
                       frame_length=config.SILENCE_FRAME_LENGTH,
                       hop_length=config.SILENCE_HOP_LENGTH):
        """
        去除静音段

        Args:
            audio: 音频数据
            top_db: 静音阈值（dB）
            frame_length: 帧长度
            hop_length: 跳跃长度

        Returns:
            audio_trimmed: 去除静音后的音频
            intervals: 非静音区间列表
        """
        # 检测非静音区间
        intervals = librosa.effects.split(
            audio,
            top_db=top_db,
            frame_length=frame_length,
            hop_length=hop_length
        )

        # 拼接非静音段
        if len(intervals) > 0:
            audio_trimmed = np.concatenate([audio[start:end] for start, end in intervals])
        else:
            audio_trimmed = audio

        return audio_trimmed, intervals

    def create_frames(self, audio, sr, frame_duration=config.FRAME_DURATION,
                      hop_duration=config.HOP_DURATION):
        """
        分帧

        Args:
            audio: 音频数据
            sr: 采样率
            frame_duration: 帧长度（秒）
            hop_duration: 跳跃长度（秒）

        Returns:
            frames: 分帧后的音频数组
        """
        frame_length = int(sr * frame_duration)
        hop_length = int(sr * hop_duration)

        frames = librosa.util.frame(
            audio,
            frame_length=frame_length,
            hop_length=hop_length
        )

        return frames.T  # 转置，返回 [n_frames, frame_length]

    def frame_real_times(self, n_frames, intervals, sr,
                         hop_duration=config.HOP_DURATION):
        """
        计算每一帧在**原始录音**中的真实起始时间（秒）。

        去静音会把多个非静音区间拼接起来再分帧，因此帧在拼接音频里的位置
        ≠ 原始录音里的位置。这里把每帧起始样本从“拼接坐标”映射回“原始坐标”，
        让事件时间戳对应录音真实钟点（而不是拼接后的相对时间）。

        Args:
            n_frames: 帧数
            intervals: librosa.effects.split 返回的非静音区间（原始样本下标）
            sr: 采样率
            hop_duration: 帧移（秒）

        Returns:
            list[float]: 长度 n_frames，每帧的真实起始时间（秒）
        """
        hop_length = int(sr * hop_duration)

        # 没有去静音信息时，退化为线性时间
        if intervals is None or len(intervals) == 0:
            return [round(i * hop_length / sr, 3) for i in range(n_frames)]

        starts = [int(s) for s, _ in intervals]          # 每个区间在原始音频的起点
        lengths = [int(e) - int(s) for s, e in intervals]  # 每个区间长度（样本）
        cum = np.cumsum([0] + lengths)                    # 拼接坐标下各区间的起点

        times = []
        for i in range(n_frames):
            t = i * hop_length                            # 帧起点在“拼接音频”中的样本下标
            k = int(np.searchsorted(cum, t, side='right')) - 1
            k = min(max(k, 0), len(starts) - 1)
            orig_sample = starts[k] + (t - cum[k])        # 映射回原始音频样本下标
            times.append(round(orig_sample / sr, 3))
        return times

    def preprocess(self, audio_path, apply_noise_reduction=True):
        """
        完整预处理流程

        Args:
            audio_path: 音频文件路径
            apply_noise_reduction: 是否应用降噪

        Returns:
            dict: 包含预处理结果的字典
        """
        # 加载音频
        audio, sr = self.load_audio(audio_path)

        # 降噪（可选）
        if apply_noise_reduction:
            audio = self.reduce_noise(audio, sr)

        # 归一化
        audio = self.normalize(audio)

        # 去除静音
        audio_trimmed, intervals = self.remove_silence(audio)

        # 分帧
        frames = self.create_frames(audio_trimmed, sr)

        # 每帧映射回原始录音的真实时间（供事件时间戳使用）
        frame_times = self.frame_real_times(len(frames), intervals, sr)

        return {
            'audio': audio_trimmed,
            'sr': sr,
            'frames': frames,
            'frame_times': frame_times,
            'intervals': intervals,
            'duration': len(audio) / sr  # 原始总时长
        }
