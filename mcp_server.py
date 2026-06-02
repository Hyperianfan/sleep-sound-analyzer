"""
睡眠声音分析 MCP Server

把 SleepSoundAnalyzer 的识别能力封装成 MCP 工具，供 Claude、Plaud 助手
等任意 LLM agent 通过 MCP 协议调用。

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


def _get_analyzer(backend="rule"):
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


@mcp.tool()
def analyze_sleep_audio(
    audio_path: str,
    apply_noise_reduction: bool = True,
    save_report: bool = True,
    backend: str = "rule",
) -> dict:
    """
    分析一段睡眠录音，识别打呼/磨牙/梦话事件，并给出统计与健康建议。

    Args:
        audio_path: 音频文件路径（绝对或相对），支持 wav/mp3/m4a。
        apply_noise_reduction: 是否先做降噪，默认 True。
        save_report: 是否把结果保存为 JSON 报告到 output/reports，默认 True。
        backend: 分类后端。"rule"=手工规则（默认，无额外依赖）；
            "yamnet"=预训练 YAMNet 模型（需安装 tensorflow，准确率更高，
            尤其能区分环境噪声与梦话）。

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


def main() -> None:
    """控制台入口点（pyproject 的 console_scripts 调用此函数）。"""
    mcp.run()


if __name__ == "__main__":
    main()
