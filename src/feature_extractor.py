"""
音频特征提取模块
"""
import numpy as np
import librosa

from . import config


class FeatureExtractor:
    """音频特征提取器"""

    def __init__(self, sr=config.TARGET_SR):
        """
        初始化特征提取器

        Args:
            sr: 采样率
        """
        self.sr = sr

    def extract_time_features(self, audio_frame):
        """
        提取时域特征

        Args:
            audio_frame: 音频帧

        Returns:
            dict: 时域特征字典
        """
        features = {}

        # 能量
        features['energy'] = np.sum(audio_frame ** 2)

        # 过零率
        zcr = librosa.feature.zero_crossing_rate(audio_frame)
        features['zcr'] = np.mean(zcr)

        # 均方根能量
        rms = librosa.feature.rms(y=audio_frame)
        features['rms'] = np.mean(rms)

        return features

    def extract_frequency_features(self, audio_frame):
        """
        提取频域特征

        Args:
            audio_frame: 音频帧

        Returns:
            dict: 频域特征字典
        """
        features = {}

        # 频谱质心
        spectral_centroid = librosa.feature.spectral_centroid(
            y=audio_frame, sr=self.sr
        )
        features['spectral_centroid'] = np.mean(spectral_centroid)

        # 频谱滚降点
        spectral_rolloff = librosa.feature.spectral_rolloff(
            y=audio_frame, sr=self.sr, roll_percent=0.85
        )
        features['spectral_rolloff'] = np.mean(spectral_rolloff)

        # 频谱带宽
        spectral_bandwidth = librosa.feature.spectral_bandwidth(
            y=audio_frame, sr=self.sr
        )
        features['spectral_bandwidth'] = np.mean(spectral_bandwidth)

        # 频谱对比度
        spectral_contrast = librosa.feature.spectral_contrast(
            y=audio_frame, sr=self.sr
        )
        features['spectral_contrast'] = np.mean(spectral_contrast)

        return features

    def extract_mfcc(self, audio_frame, n_mfcc=13):
        """
        提取 MFCC 特征

        Args:
            audio_frame: 音频帧
            n_mfcc: MFCC 系数数量

        Returns:
            dict: MFCC 特征
        """
        mfcc = librosa.feature.mfcc(
            y=audio_frame,
            sr=self.sr,
            n_mfcc=n_mfcc
        )

        return {
            'mfcc_mean': np.mean(mfcc, axis=1),
            'mfcc_std': np.std(mfcc, axis=1),
            'mfcc_var': np.var(mfcc, axis=1)
        }

    def extract_all_features(self, audio_frame):
        """
        提取所有特征

        Args:
            audio_frame: 音频帧

        Returns:
            dict: 包含所有特征的字典
        """
        features = {}

        # 时域特征
        features.update(self.extract_time_features(audio_frame))

        # 频域特征
        features.update(self.extract_frequency_features(audio_frame))

        # MFCC 特征
        mfcc_features = self.extract_mfcc(audio_frame)
        features.update(mfcc_features)

        return features

    def extract_features_batch(self, frames):
        """
        批量提取特征

        Args:
            frames: 音频帧数组 [n_frames, frame_length]

        Returns:
            list: 特征字典列表
        """
        features_list = []
        for frame in frames:
            features = self.extract_all_features(frame)
            features_list.append(features)

        return features_list
