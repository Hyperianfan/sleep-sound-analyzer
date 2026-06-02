"""
睡眠声音分析 MCP Server

把 SleepSoundAnalyzer 的识别能力封装成 MCP 工具，供 Claude 等任意
LLM agent 通过 MCP 协议调用。

运行（stdio 传输，供本地客户端拉起）：
    python mcp_server.py

提供的工具：
    - analyze_sleep_audio : 分析一段睡眠录音，识别打呼/磨牙/梦话并给出建议
    - list_sleep_reports  : 列出历史报告
    - get_sleep_report    : 读取指定历史报告

注意：本服务使用 stdio 传输，stdout 被 MCP 协议独占。分析器内部的
print() 日志会被重定向到 stderr，避免污染协议。
"""
import contextlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src import trends
from src.analyzer import SleepSoundAnalyzer

# 报告保存目录。
# 默认与 Web 应用共享项目内的 output/reports；当本包被安装到别处（如 pip
# 安装进 site-packages）时，可用环境变量 SLEEP_REPORTS_DIR 指定一个可写目录。
REPORTS_FOLDER = Path(
    os.environ.get(
        "SLEEP_REPORTS_DIR", Path(__file__).parent / "output" / "reports"
    )
).expanduser()
REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)

mcp = FastMCP("sleep-sound-analyzer")

# 延迟初始化：librosa/tensorflow 等依赖较重，首次调用工具时才加载，保证 server
# 秒级启动。按后端分别缓存，避免重复载入模型。
_analyzers = {}


def _get_analyzer(backend="hybrid"):
    if backend not in _analyzers:
        _analyzers[backend] = SleepSoundAnalyzer(backend=backend)
    return _analyzers[backend]


@contextlib.contextmanager
def _quiet_stdout():
    """把内部 print() 重定向到 stderr，保护 stdio MCP 协议。"""
    with contextlib.redirect_stdout(sys.stderr):
        yield


def _build_summary(result: dict) -> str:
    """根据分析结果生成一段中文 markdown 摘要，方便 agent 直接展示给用户。"""
    stats = result["statistics"]
    lines = [
        "# 睡眠声音分析摘要",
        f"- 总时长：{stats['total_duration_hours']} 小时",
    ]
    for key, name in (("snoring", "打呼"), ("grinding", "磨牙"), ("talking", "梦话")):
        s = stats[key]
        minutes = round(s["total_time"] / 60, 1)
        lines.append(f"- {name}：{s['count']} 次，共 {minutes} 分钟（{s['percentage']}%）")

    lines.append("\n## 健康建议")
    for sug in result["suggestions"]:
        lines.append(f"- [{sug['level']}] {sug['message']}")
        for advice in sug["advice"]:
            lines.append(f"    - {advice}")

    return "\n".join(lines)


def _save_one(analyzer, result) -> str:
    """保存一份报告，文件名带微秒避免批量时秒级冲突。返回路径字符串。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_path = REPORTS_FOLDER / f"report_{timestamp}.json"
    analyzer.save_report(result, report_path)
    return str(report_path)


def _compact_report(result: dict) -> dict:
    """批量返回时压缩单份结果：去掉逐事件明细，只留元数据/统计/评分/路径。"""
    meta = result.get("metadata", {})
    return {
        "file": meta.get("file"),
        "recording_started_at": meta.get("recording_started_at"),
        "backend": meta.get("backend"),
        "report_path": result.get("report_path"),
        "score": result.get("score"),
        "statistics": result.get("statistics"),
    }


def _build_trend_summary(trend: dict) -> str:
    """把趋势结果渲染成可直接展示的中文 markdown。"""
    nights = trend.get("nights", [])
    lines = ["# 多晚睡眠趋势", "", trend.get("verdict", "")]
    if nights:
        lines.append("")
        lines.append("| 日期 | 睡眠分 | 等级 | 打鼾/h | 磨牙/h | 梦话/h | 发声占比 |")
        lines.append("|---|---|---|---|---|---|---|")
        for s in nights:
            d = (s.get("date") or "")[:16]
            lines.append(
                f"| {d} | {s['score']} | {s['label']} | {s['snore_per_hour']} "
                f"| {s['grind_per_hour']} | {s['talk_per_hour']} | {s['disturb_pct']}% |"
            )
    return "\n".join(lines)


@mcp.tool()
def analyze_sleep_audio(
    audio_path: str,
    apply_noise_reduction: bool = True,
    save_report: bool = True,
    backend: str = "hybrid",
) -> dict:
    """
    分析一段睡眠录音，识别打呼/磨牙/梦话事件，并给出统计与健康建议。

    Args:
        audio_path: 音频文件路径（绝对或相对），支持 wav/mp3/m4a。
        apply_noise_reduction: 是否先做降噪，默认 True。
        save_report: 是否把结果保存为 JSON 报告到 output/reports，默认 True。
        backend: 分类后端，默认 "hybrid"。
            "hybrid"=YAMNet 测打鼾/梦话 + 规则测磨牙（推荐，准确率最高）；
            "yamnet"=纯 YAMNet（磨牙基本测不到）；
            "rule"=纯手工规则（无额外依赖）。
            yamnet/hybrid 需安装 tensorflow（pip install ".[yamnet]"）；
            依赖缺失时自动回退到 rule，实际生效的后端见返回的 metadata.backend。

    Returns:
        dict: 包含以下字段
            - metadata: 文件信息、分析时间、总时长、总帧数、所用 backend
            - statistics: 各类声音的次数/时长/占比
            - events: 带时间戳的事件列表
            - suggestions: 健康建议列表
            - summary: 一段可直接展示的中文 markdown 摘要
            - report_path: 已保存报告的路径（save_report=False 时为 null）
    """
    path = Path(audio_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    with _quiet_stdout():
        analyzer = _get_analyzer(backend)
        result = analyzer.analyze_audio(
            str(path), apply_noise_reduction=apply_noise_reduction
        )

        report_path = None
        if save_report:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = REPORTS_FOLDER / f"report_{timestamp}.json"
            analyzer.save_report(result, report_path)

    result["summary"] = _build_summary(result)
    result["report_path"] = str(report_path) if report_path else None
    return result


@mcp.tool()
def list_sleep_reports() -> list:
    """列出已保存的历史分析报告（按时间倒序）。"""
    reports = []
    for report_file in sorted(REPORTS_FOLDER.glob("*.json"), reverse=True):
        with open(report_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        reports.append(
            {
                "filename": report_file.name,
                "analyzed_at": data["metadata"]["analyzed_at"],
                "total_duration": data["metadata"]["total_duration"],
            }
        )
    return reports


@mcp.tool()
def get_sleep_report(filename: str) -> dict:
    """
    按文件名读取一份已保存的分析报告。

    Args:
        filename: 报告文件名，如 report_20260602_113551.json
    """
    # 仅允许读取报告目录下的文件，防止路径穿越
    safe_name = Path(filename).name
    report_path = REPORTS_FOLDER / safe_name
    if not report_path.exists():
        raise FileNotFoundError(f"报告不存在: {filename}")
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


@mcp.tool()
def analyze_sleep_batch(
    audio_paths: list[str],
    apply_noise_reduction: bool = True,
    save_report: bool = True,
    backend: str = "hybrid",
) -> dict:
    """
    连续分析一份或多份睡眠录音，给出每晚睡眠分，并对多晚做趋势对比
    （判断整体变好/变差/持平）。

    Args:
        audio_paths: 一个或多个音频文件路径。
        apply_noise_reduction: 是否降噪，默认 True。
        save_report: 是否把每晚结果保存为 JSON 报告，默认 True。
        backend: 分类后端，默认 "hybrid"（同 analyze_sleep_audio）。

    Returns:
        dict:
            - nights: 各晚摘要（日期、睡眠分、等级、各类每小时次数、发声占比），按日期排序
            - trend: 趋势分析（overall_direction=improving/worsening/stable、各指标变化、中文 verdict）
            - reports: 各份压缩结果（统计/评分/报告路径，不含逐事件明细）
            - summary: 可直接展示的中文 markdown 趋势表
    """
    paths = []
    for p in audio_paths:
        pp = Path(p).expanduser()
        if not pp.exists():
            raise FileNotFoundError(f"音频文件不存在: {p}")
        paths.append(str(pp))

    with _quiet_stdout():
        analyzer = _get_analyzer(backend)
        cb = (lambda r: _save_one(analyzer, r)) if save_report else None
        batch = analyzer.analyze_batch(
            paths, apply_noise_reduction=apply_noise_reduction, save_report=cb
        )

    batch["reports"] = [_compact_report(r) for r in batch["reports"]]
    batch["summary"] = _build_trend_summary(batch["trend"])
    return batch


@mcp.tool()
def analyze_sleep_trend(
    filenames: list[str] | None = None,
    date_from: str = "",
    date_to: str = "",
) -> dict:
    """
    对**已保存的历史报告**做多晚趋势分析，无需重新跑音频。

    Args:
        filenames: 指定要对比的报告文件名列表（report_*.json）。为空则扫描全部报告。
        date_from: 起始日期（YYYY-MM-DD，含）。仅在未指定 filenames 时按录音日期过滤。
        date_to: 结束日期（YYYY-MM-DD，含）。

    Returns:
        dict: nights、trend（含变好/变差结论）、summary（中文 markdown）。
    """
    results = []
    if filenames:
        for fn in filenames:
            fp = REPORTS_FOLDER / Path(fn).name
            if not fp.exists():
                raise FileNotFoundError(f"报告不存在: {fn}")
            with open(fp, "r", encoding="utf-8") as f:
                results.append(json.load(f))
    else:
        for fp in REPORTS_FOLDER.glob("*.json"):
            with open(fp, "r", encoding="utf-8") as f:
                results.append(json.load(f))

    out = SleepSoundAnalyzer.trend_from_results(results)

    # 按录音日期过滤（仅在未显式指定 filenames 时生效）
    if not filenames and (date_from or date_to):
        def _in_range(s):
            d = (s.get("date") or "")[:10]
            if date_from and d < date_from:
                return False
            if date_to and d > date_to:
                return False
            return True
        nights = [s for s in out["nights"] if _in_range(s)]
        out = {"nights": nights, "trend": trends.analyze_trend(nights)}

    out["summary"] = _build_trend_summary(out["trend"])
    return out


def main() -> None:
    """控制台入口点（pyproject 的 console_scripts 调用此函数）。"""
    mcp.run()


if __name__ == "__main__":
    main()
