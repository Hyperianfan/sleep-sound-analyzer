"""
主分析器模块
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from . import config
from .preprocessor import AudioPreprocessor
from .feature_extractor import FeatureExtractor
from .classifier import SoundClassifier

logger = logging.getLogger(__name__)


class SleepSoundAnalyzer:
    """睡眠声音分析器"""

    def __init__(self):
        """初始化分析器"""
        self.preprocessor = AudioPreprocessor(target_sr=config.TARGET_SR)
        self.feature_extractor = FeatureExtractor(sr=config.TARGET_SR)
        self.classifier = SoundClassifier()

    def analyze_audio(self, audio_path, apply_noise_reduction=True):
        """
        分析音频文件

        Args:
            audio_path: 音频文件路径
            apply_noise_reduction: 是否应用降噪

        Returns:
            dict: 分析结果
        """
        logger.info("[1/4] 预处理音频: %s", audio_path)
        # 1. 预处理
        preprocessed = self.preprocessor.preprocess(
            audio_path,
            apply_noise_reduction=apply_noise_reduction
        )

        logger.info("[2/4] 提取特征 (%d 帧)", len(preprocessed['frames']))
        # 2. 提取特征
        features_list = self.feature_extractor.extract_features_batch(
            preprocessed['frames']
        )

        logger.info("[3/4] 声音分类")
        # 3. 分类识别
        classifications = self.classifier.classify_batch(features_list)

        logger.info("[4/4] 事件合并与统计")
        # 4. 生成事件列表（带时间戳）
        # 时间戳与初始时长都按帧步长计算，与预处理分帧保持一致（见 config.HOP_DURATION）
        events = []
        for i, (sound_type, confidence) in enumerate(classifications):
            if sound_type != 'unknown':
                event = {
                    'type': sound_type,
                    'timestamp': i * config.HOP_DURATION,
                    'confidence': round(confidence, 3),
                    'duration': config.HOP_DURATION
                }
                events.append(event)

        # 5. 合并连续事件
        merged_events = self._merge_events(events, gap_threshold=config.EVENT_GAP_THRESHOLD)

        # 6. 统计分析
        stats = self._calculate_statistics(
            merged_events,
            preprocessed['duration']
        )

        # 7. 生成建议
        suggestions = self._generate_suggestions(stats)

        return {
            'metadata': {
                'file': str(audio_path),
                'analyzed_at': datetime.now().isoformat(),
                'total_duration': preprocessed['duration'],
                'total_frames': len(preprocessed['frames'])
            },
            'statistics': stats,
            'events': merged_events,
            'suggestions': suggestions
        }

    def _merge_events(self, events, gap_threshold=config.EVENT_GAP_THRESHOLD):
        """
        合并连续的同类事件

        Args:
            events: 事件列表
            gap_threshold: 间隔阈值（秒）

        Returns:
            list: 合并后的事件列表
        """
        if not events:
            return []

        merged = []
        current = events[0].copy()

        for event in events[1:]:
            # 同类型且时间接近
            time_gap = event['timestamp'] - (current['timestamp'] + current['duration'])

            if (event['type'] == current['type'] and time_gap < gap_threshold):
                # 合并：延长持续时间
                current['duration'] += (time_gap + event['duration'])
                # 更新置信度为最大值
                current['confidence'] = max(current['confidence'], event['confidence'])
            else:
                # 保存当前事件，开始新事件
                merged.append(current)
                current = event.copy()

        # 添加最后一个事件
        merged.append(current)

        return merged

    def _calculate_statistics(self, events, total_duration):
        """
        计算统计信息

        Args:
            events: 事件列表
            total_duration: 总时长（秒）

        Returns:
            dict: 统计信息
        """
        stats = {
            'total_duration': round(total_duration, 2),
            'total_duration_hours': round(total_duration / 3600, 2),
        }
        for sound_type in config.SOUND_TYPES:
            stats[sound_type] = {'count': 0, 'total_time': 0, 'percentage': 0}

        # 统计各类声音
        for event in events:
            event_type = event['type']
            if event_type in stats:
                stats[event_type]['count'] += 1
                stats[event_type]['total_time'] += event['duration']

        # 计算占比
        if total_duration > 0:
            for sound_type in config.SOUND_TYPES:
                stats[sound_type]['total_time'] = round(
                    stats[sound_type]['total_time'], 2
                )
                stats[sound_type]['percentage'] = round(
                    (stats[sound_type]['total_time'] / total_duration) * 100,
                    2
                )

        return stats

    def _generate_suggestions(self, stats):
        """
        生成健康建议

        Args:
            stats: 统计信息

        Returns:
            list: 建议列表
        """
        suggestions = []
        thresholds = config.SUGGESTION_THRESHOLDS

        # 打呼建议
        if stats['snoring']['count'] > thresholds['snoring']['info']:
            if stats['snoring']['count'] > thresholds['snoring']['warning']:
                suggestions.append({
                    'level': 'warning',
                    'type': 'snoring',
                    'message': '打呼次数较多（>60次），可能影响睡眠质量',
                    'advice': [
                        '建议调整睡姿，避免仰卧',
                        '保持健康体重',
                        '睡前避免饮酒',
                        '如持续严重建议就医检查'
                    ]
                })
            else:
                suggestions.append({
                    'level': 'info',
                    'type': 'snoring',
                    'message': '打呼次数偏多（30-60次）',
                    'advice': [
                        '注意睡姿，侧卧更佳',
                        '保持鼻腔通畅'
                    ]
                })

        # 磨牙建议
        if stats['grinding']['count'] > thresholds['grinding']['info']:
            if stats['grinding']['count'] > thresholds['grinding']['warning']:
                suggestions.append({
                    'level': 'warning',
                    'type': 'grinding',
                    'message': '磨牙频繁（>20次），可能与压力或牙齿问题有关',
                    'advice': [
                        '建议就诊口腔科，检查牙齿咬合',
                        '睡前放松，减轻压力',
                        '可考虑佩戴牙套保护牙齿'
                    ]
                })
            else:
                suggestions.append({
                    'level': 'info',
                    'type': 'grinding',
                    'message': '磨牙次数偏多（10-20次）',
                    'advice': [
                        '注意放松，睡前冥想或听轻音乐',
                        '减少咖啡因摄入'
                    ]
                })

        # 梦话建议
        if stats['talking']['count'] > thresholds['talking']['info']:
            suggestions.append({
                'level': 'info',
                'type': 'talking',
                'message': '梦话较多，可能睡眠质量欠佳',
                'advice': [
                    '改善睡眠环境（温度、光线、噪音）',
                    '规律作息，避免过度疲劳',
                    '睡前避免剧烈运动或兴奋性活动'
                ]
            })

        # 如果一切正常
        if not suggestions:
            suggestions.append({
                'level': 'success',
                'type': 'general',
                'message': '睡眠质量良好，未发现明显异常',
                'advice': ['保持良好的睡眠习惯']
            })

        return suggestions

    def save_report(self, result, output_path):
        """
        保存分析报告

        Args:
            result: 分析结果
            output_path: 输出文件路径
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info("报告已保存: %s", output_path)
