"""
集中配置

把散落在各模块里的魔法数字收敛到一处。特别是 HOP_DURATION——它同时被
预处理（分帧步长）和分析器（事件时间戳、初始时长）使用，两边必须一致，
否则时间戳计算会悄悄错位。集中定义可避免改一处忘改另一处。
"""

# ---- 音频处理 ----
TARGET_SR = 16000          # 目标采样率（Hz）
FRAME_DURATION = 1.0       # 帧长（秒）
HOP_DURATION = 0.5         # 帧间步长（秒）——分帧、事件时间戳与初始时长共用

# ---- 静音检测 ----
SILENCE_TOP_DB = 30        # 静音阈值（dB）
SILENCE_FRAME_LENGTH = 2048
SILENCE_HOP_LENGTH = 512

# ---- 降噪 ----
NOISE_PROP_DECREASE = 0.8

# ---- 事件合并 ----
EVENT_GAP_THRESHOLD = 2.0  # 合并同类连续事件的最大间隔（秒）

# ---- 声音类型 ----
# 统一的类型顺序，供统计、占比计算等复用
SOUND_TYPES = ("snoring", "grinding", "talking")

# ---- 健康建议阈值（按检测次数）----
SUGGESTION_THRESHOLDS = {
    "snoring": {"info": 30, "warning": 60},
    "grinding": {"info": 10, "warning": 20},
    "talking": {"info": 5},
}
