"""
主分析器模块
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from . import config
from . import scoring
from . import trends
from .preprocessor import AudioPreprocessor
from .feature_extractor import FeatureExtractor
from .classifier import SoundClassifier

logger = logging.getLogger(__name__)

# 从文件名里提取录音起始时间，支持如 2026-06-02_03_06_12 / 2026-06-02 03:06:12
_DATETIME_IN_NAME = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[:_](\d{2})[:_](\d{2})"
)
_DATE_IN_NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _parse_recording_time(audio_path):
    """从文件名推断录音起始时间，返回 ISO 字符串；无法识别返回 None。"""
    name = Path(audio_path).name
    m = _DATETIME_IN_NAME.search(name)
    if m:
        y, mo, d, h, mi, s = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:{s}"
    m = _DATE_IN_NAME.search(name)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{mo}-{d}T00:00:00"
    return None


class SleepSoundAnalyzer:
    """睡眠声音分析器"""

    VALID_BACKENDS = ("rule", "yamnet", "hybrid")

    def __init__(self, backend="hybrid"):
        """
        初始化分析器

        Args:
            backend: 分类后端。
                "hybrid" —— 默认。YAMNet 测打鼾/梦话 + 规则测磨牙，兼顾两者所长。
                "yamnet" —— 纯预训练 YAMNet（磨牙基本测不到）。
                "rule"   —— 纯手工规则，无额外依赖。
            注：yamnet/hybrid 需安装 tensorflow（pip install ".[yamnet]"）；
            若依赖缺失，会自动回退到 "rule" 并告警。
        """
        if backend not in self.VALID_BACKENDS:
            raise ValueError(
                f"未知的分类后端: {backend}（应为 {self.VALID_BACKENDS} 之一）"
            )
        self.backend = backend
        self.preprocessor = AudioPreprocessor(target_sr=config.TARGET_SR)
        self.feature_extractor = FeatureExtractor(sr=config.TARGET_SR)
        self.classifier = SoundClassifier()
        # YAMNet 后端懒加载，避免无谓地拉起 tensorflow
        self._yamnet = None

    def analyze_audio(self, audio_path, apply_noise_reduction=True,
                      recording_started_at=None):
        """
        分析音频文件

        Args:
            audio_path: 音频文件路径
            apply_noise_reduction: 是否应用降噪
            recording_started_at: 录音起始时间（ISO 字符串）。不传则尝试从文件名
                解析（如 2026-06-02_03_06_12）。用于多晚趋势的日期排序。

        Returns:
            dict: 分析结果
        """
        logger.info("[1/4] 预处理音频: %s", audio_path)
        # 1. 预处理
        preprocessed = self.preprocessor.preprocess(
            audio_path,
            apply_noise_reduction=apply_noise_reduction
        )

        n_frames = len(preprocessed['frames'])

        # 后端可用性：yamnet/hybrid 需要 tensorflow，缺失则回退到规则
        backend = self.backend
        yamnet = None
        if backend in ("yamnet", "hybrid"):
            yamnet = self._get_yamnet()
            if yamnet is None:
                backend = "rule"

        # 2~3. 提取特征 + 分类识别（按后端分流）
        logger.info("[2/4] 特征/推理 (%d 帧, backend=%s)", n_frames, backend)
        logger.info("[3/4] 声音分类 (backend=%s)", backend)
        if backend == "rule":
            features_list = self.feature_extractor.extract_features_batch(
                preprocessed['frames']
            )
            classifications = self.classifier.classify_batch(features_list)
        elif backend == "yamnet":
            classifications = yamnet.classify_waveform(
                preprocessed['audio'],
                n_frames=n_frames,
                hop_duration=config.HOP_DURATION,
            )
        else:  # hybrid: YAMNet 测打鼾/梦话，规则补测磨牙
            classifications = yamnet.classify_waveform(
                preprocessed['audio'],
                n_frames=n_frames,
                hop_duration=config.HOP_DURATION,
            )
            features_list = self.feature_extractor.extract_features_batch(
                preprocessed['frames']
            )
            # 仅在 YAMNet 判为 unknown 的帧上用规则补磨牙，避免抢占高置信的打鼾/梦话
            for i, (sound_type, _conf) in enumerate(classifications):
                if sound_type == 'unknown':
                    g_type, g_conf = self.classifier.classify_grinding(
                        features_list[i]
                    )
                    if g_type == 'grinding':
                        classifications[i] = (g_type, g_conf)

        logger.info("[4/4] 事件合并与统计")
        # 4. 生成事件列表（时间戳映射回原始录音真实时间，见 preprocessor.frame_real_times）
        frame_times = preprocessed['frame_times']
        events = []
        for i, (sound_type, confidence) in enumerate(classifications):
            if sound_type != 'unknown':
                event = {
                    'type': sound_type,
                    'timestamp': frame_times[i],
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

        result = {
            'metadata': {
                'file': str(audio_path),
                'analyzed_at': datetime.now().isoformat(),
                'recording_started_at': (
                    recording_started_at or _parse_recording_time(audio_path)
                ),
                'total_duration': preprocessed['duration'],
                'total_frames': len(preprocessed['frames']),
                'backend': backend  # 实际生效的后端（依赖缺失回退时与 self.backend 不同）
            },
            'statistics': stats,
            'events': merged_events,
            'suggestions': suggestions
        }
        # 8. 单晚评分（可跨晚比较）
        result['score'] = scoring.compute_score(stats)
        return result

    def analyze_batch(self, audio_paths, apply_noise_reduction=True,
                      save_report=None):
        """
        连续分析多份录音，并对各晚做趋势对比。

        Args:
            audio_paths: 音频文件路径列表（一个或多个）。
            apply_noise_reduction: 是否降噪。
            save_report: 可选回调 (result) -> report_path，用于逐份保存报告。

        Returns:
            dict:
                - nights: 各晚摘要（按日期排序）
                - trend: 趋势分析（含变好/变差结论）
                - reports: 各份完整结果（按输入顺序）
        """
        results = []
        summaries = []
        for path in audio_paths:
            result = self.analyze_audio(
                path, apply_noise_reduction=apply_noise_reduction
            )
            if save_report is not None:
                result['report_path'] = save_report(result)
            results.append(result)
            summaries.append(scoring.night_summary(result))

        return {
            'nights': sorted(summaries, key=lambda s: (s.get('date') or '')),
            'trend': trends.analyze_trend(summaries),
            'reports': results,
        }

    @staticmethod
    def trend_from_results(results):
        """对一组已有的完整分析结果做趋势分析（供历史报告复用）。"""
        summaries = [scoring.night_summary(r) for r in results]
        return {
            'nights': sorted(summaries, key=lambda s: (s.get('date') or '')),
            'trend': trends.analyze_trend(summaries),
        }

    def _get_yamnet(self):
        """
        懒加载 YAMNet 分类器（首次调用时才 import tensorflow 并载入模型）。
        若 tensorflow / tensorflow-hub 未安装，返回 None（调用方据此回退到规则）。
        """
        if self._yamnet is None:
            import importlib.util
            missing = [
                m for m in ("tensorflow", "tensorflow_hub")
                if importlib.util.find_spec(m) is None
            ]
            if missing:
                logger.warning(
                    "YAMNet 依赖缺失 %s，回退到规则后端。安装：pip install \".[yamnet]\"",
                    missing,
                )
                return None
            from .yamnet_classifier import YAMNetClassifier
            self._yamnet = YAMNetClassifier()
        return self._yamnet

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
