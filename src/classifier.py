"""
声音分类器模块
"""
import numpy as np


class SoundClassifier:
    """基于规则的声音分类器"""

    def __init__(self):
        """初始化分类器"""
        # 分类阈值配置
        self.config = {
            'snoring': {
                'min_freq': 50,
                'max_freq': 500,
                'min_rms': 0.02,
                'max_bandwidth': 500,
                'min_duration': 0.5,
                'confidence_base': 0.75
            },
            'grinding': {
                'min_freq': 500,
                'max_freq': 3000,
                'min_bandwidth': 800,
                'min_zcr': 0.15,
                'min_rms': 0.01,
                'max_duration': 2.0,
                'confidence_base': 0.70
            },
            'talking': {
                'min_freq': 200,
                'max_freq': 4000,
                'min_mfcc_var': 0.5,
                'min_rms': 0.01,
                'max_rms': 0.05,
                'confidence_base': 0.65
            }
        }

    def classify_snoring(self, features):
        """
        打呼检测

        Args:
            features: 特征字典

        Returns:
            tuple: (类别, 置信度)
        """
        config = self.config['snoring']
        score = 0.0
        max_score = 4.0

        # 条件1：低频能量占优（权重：1.5）
        if config['min_freq'] < features['spectral_centroid'] < config['max_freq']:
            score += 1.5

        # 条件2：能量足够大（权重：1.0）
        if features['rms'] > config['min_rms']:
            score += 1.0

        # 条件3：频谱集中度（非噪声）（权重：1.0）
        if features['spectral_bandwidth'] < config['max_bandwidth']:
            score += 1.0

        # 条件4：低过零率（平滑信号）（权重：0.5）
        if features['zcr'] < 0.1:
            score += 0.5

        confidence = (score / max_score) * config['confidence_base']

        if confidence > 0.6:
            return 'snoring', confidence
        return 'unknown', 0.0

    def classify_grinding(self, features):
        """
        磨牙检测

        Args:
            features: 特征字典

        Returns:
            tuple: (类别, 置信度)
        """
        config = self.config['grinding']
        score = 0.0
        max_score = 4.0

        # 条件1：高频能量（摩擦音）（权重：1.5）
        if features['spectral_centroid'] > config['min_freq']:
            score += 1.5

        # 条件2：宽频带（噪声特性）（权重：1.0）
        if features['spectral_bandwidth'] > config['min_bandwidth']:
            score += 1.0

        # 条件3：高过零率（摩擦感）（权重：1.0）
        if features['zcr'] > config['min_zcr']:
            score += 1.0

        # 条件4：适中的能量（权重：0.5）
        if features['rms'] > config['min_rms']:
            score += 0.5

        confidence = (score / max_score) * config['confidence_base']

        if confidence > 0.55:
            return 'grinding', confidence
        return 'unknown', 0.0

    def classify_talking(self, features):
        """
        梦话检测

        Args:
            features: 特征字典

        Returns:
            tuple: (类别, 置信度)
        """
        config = self.config['talking']
        score = 0.0
        max_score = 4.0

        # 条件1：语音频率范围（权重：1.5）
        freq = features['spectral_centroid']
        if config['min_freq'] < freq < config['max_freq']:
            score += 1.5

        # 条件2：MFCC 变化（语音特有）（权重：1.0）
        if 'mfcc_var' in features:
            mfcc_var = np.mean(features['mfcc_var'])
            if mfcc_var > config['min_mfcc_var']:
                score += 1.0

        # 条件3：适中的能量（权重：1.0）
        rms = features['rms']
        if config['min_rms'] < rms < config['max_rms']:
            score += 1.0

        # 条件4：频谱对比度（语音有明显共振峰）（权重：0.5）
        if features['spectral_contrast'] > 20:
            score += 0.5

        confidence = (score / max_score) * config['confidence_base']

        if confidence > 0.5:
            return 'talking', confidence
        return 'unknown', 0.0

    def classify(self, features):
        """
        综合分类

        Args:
            features: 特征字典

        Returns:
            tuple: (最佳类别, 置信度)
        """
        # 尝试所有分类器
        snore_result = self.classify_snoring(features)
        grind_result = self.classify_grinding(features)
        talk_result = self.classify_talking(features)

        # 选择置信度最高的结果
        results = [snore_result, grind_result, talk_result]
        best_result = max(results, key=lambda x: x[1])

        # 如果最高置信度仍然很低，返回 unknown
        if best_result[1] < 0.5:
            return 'unknown', 0.0

        return best_result

    def classify_batch(self, features_list):
        """
        批量分类

        Args:
            features_list: 特征字典列表

        Returns:
            list: 分类结果列表
        """
        results = []
        for features in features_list:
            result = self.classify(features)
            results.append(result)

        return results
