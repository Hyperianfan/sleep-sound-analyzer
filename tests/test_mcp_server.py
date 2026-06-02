"""MCP Server 工具行为，含 stdout 协议保护与路径穿越防护。"""
import asyncio
import contextlib
import io
import json

import pytest

import mcp_server


def test_tools_registered():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert {"analyze_sleep_audio", "list_sleep_reports", "get_sleep_report"} <= names


def test_analyze_returns_summary_and_keeps_stdout_clean(make_wav, tmp_path, monkeypatch):
    # 报告写入临时目录，避免污染真实 output/reports
    monkeypatch.setattr(mcp_server, "REPORTS_FOLDER", tmp_path)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = mcp_server.analyze_sleep_audio(
            make_wav(), apply_noise_reduction=False, save_report=True
        )

    # stdio MCP 协议独占 stdout——分析过程绝不能往 stdout 写东西
    assert buf.getvalue() == ""
    assert isinstance(res["summary"], str) and res["summary"]
    assert res["report_path"] is not None
    assert json.dumps(res)


def test_analyze_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        mcp_server.analyze_sleep_audio("/no/such/file.wav")


def test_list_and_get_report(make_wav, tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "REPORTS_FOLDER", tmp_path)

    mcp_server.analyze_sleep_audio(make_wav(), apply_noise_reduction=False)
    reports = mcp_server.list_sleep_reports()
    assert len(reports) == 1

    data = mcp_server.get_sleep_report(reports[0]["filename"])
    assert "statistics" in data


def test_get_report_blocks_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "REPORTS_FOLDER", tmp_path)
    with pytest.raises(FileNotFoundError):
        mcp_server.get_sleep_report("../../etc/passwd")
