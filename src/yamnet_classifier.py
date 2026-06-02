"""
YAMNet 分类器后端

用 Google 在 AudioSet（521 类）上预训练的 YAMNet 模型做声音识别，替代手工规则。
YAMNet 直接带有 `Snoring`、`Speech` 等类，对打鼾/梦话几乎可零样本识别，并且天然
能把环境噪声（电视、风扇等）与目标声音区分开。

设计要点：
    - 只在选用 yamnet 后端时才 import tensorflow（重依赖，懒加载）。
    - 输出对齐到分析器现有的帧网格：返回长度 == n_frames 的
      [(类型, 置信度), ...]，类型 ∈ {snoring, grinding, talking, unknown}，
      使得 analyzer 的事件合并/统计/建议逻辑可原样复用。

模型 I/O（YAMNet）：
    输入 : 1-D float32 波形，16kHz 单声道，幅值 [-1, 1]
    输出 : scores (T, 521)，帧窗 0.96s、帧移 ~0.48s；以及 embeddings、log-mel
"""
import logging

import numpy as np

from . import config

logger = logging.getLogger(__name__)

# YAMNet 固有参数
YAMNET_SR = 16000
YAMNET_HOP_SECONDS = 0.48  # 相邻输出帧的时间间隔


class YAMNetClassifier:
    """基于预训练 YAMNet 的声音分类器。"""

    def __init__(
        self,
        model_handle=config.YAMNET_MODEL_HANDLE,
        class_keywords=None,
        thresholds=None,
    ):
        self.model_handle = model_handle
        self.class_keywords = class_keywords or config.YAMNET_CLASS_KEYWORDS
        self.thresholds = thresholds or config.YAMNET_THRESHOLDS
        self._model = None
        self._class_names = None
        # category -> 命中的 AudioSet 类下标数组
        self._category_indices = None

    # ------------------------------------------------------------------ #
    # 懒加载：第一次用到才下载/载入模型，避免 import 即拉起 tensorflow
    # ------------------------------------------------------------------ #
    def _ensure_loaded(self):
        if self._model is not None:
            return

        import csv

        import tensorflow as tf  # noqa: F401  确保 TF 已可用
        import tensorflow_hub as hub

        logger.info("加载 YAMNet 模型: %s", self.model_handle)
        self._model = hub.load(self.model_handle)

        # 读取模型自带的类名表（AudioSet 521 类）
        class_map_path = self._model.class_map_path().numpy().decode("utf-8")
        names = []
        with tf.io.gfile.GFile(class_map_path) as f:
            for row in csv.DictReader(f):
                names.append(row["display_name"])
        self._class_names = names

        self._category_indices = self._build_category_indices(names)
        for category, idxs in self._category_indices.items():
            hit = [names[i] for i in idxs]
            logger.info("类别 %s 命中 %d 个 AudioSet 类: %s", category, len(idxs), hit)
            if not idxs:
                logger.warning("类别 %s 未命中任何 AudioSet 类，将永远不会被检出", category)

    def _build_category_indices(self, names):
        """按关键词（不区分大小写、子串匹配）把 AudioSet 类映射到我们的类别。"""
        lowered = [n.lower() for n in names]
        mapping = {}
        for category, keywords in self.class_keywords.items():
            idxs = [
                i
                for i, name in enumerate(lowered)
                if any(kw.lower() in name for kw in keywords)
            ]
            mapping[category] = idxs
        return mapping

    # ------------------------------------------------------------------ #
    # 推理
    # ------------------------------------------------------------------ #
    def classify_waveform(self, waveform, n_frames, hop_duration):
        """
        对整段波形做分类，并对齐到分析器的帧网格。

        Args:
            waveform: 1-D float32 波形（16kHz 单声道）。
            n_frames: 分析器侧的帧数（输出长度需与之一致）。
            hop_duration: 分析器侧帧移（秒），用于把帧序号换算成时间再对齐。

        Returns:
            list[tuple[str, float]]: 长度为 n_frames 的 (类型, 置信度) 列表。
        """
        self._ensure_loaded()

        waveform = np.asarray(waveform, dtype=np.float32)
        if waveform.ndim > 1:
            waveform = waveform.mean(axis=1)  # 转单声道兜底

        # YAMNet: scores 形状 (T, 521)
        scores, _embeddings, _spectro = self._model(waveform)
        scores = np.asarray(scores)
        n_yamnet = scores.shape[0]
        if n_yamnet == 0:
            return [("unknown", 0.0)] * n_frames

        # 预先把每个 YAMNet 帧的「各类别得分」算出来：
        # category_score[t, c] = 该帧内属于类别 c 的所有 AudioSet 类的最大概率
        categories = list(self.class_keywords.keys())
        cat_scores = np.zeros((n_yamnet, len(categories)), dtype=np.float32)
        for c, category in enumerate(categories):
            idxs = self._category_indices.get(category, [])
            if idxs:
                cat_scores[:, c] = scores[:, idxs].max(axis=1)

        results = []
        for i in range(n_frames):
            # 分析器第 i 帧的中心时间，映射到最近的 YAMNet 帧
            center_t = i * hop_duration + hop_duration / 2.0
            t = int(round(center_t / YAMNET_HOP_SECONDS))
            t = min(max(t, 0), n_yamnet - 1)

            row = cat_scores[t]
            best_c = int(np.argmax(row))
            best_score = float(row[best_c])
            category = categories[best_c]

            if best_score >= self.thresholds.get(category, 0.5):
                results.append((category, round(best_score, 3)))
            else:
                results.append(("unknown", 0.0))

        return results
