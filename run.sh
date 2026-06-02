#!/bin/bash
set -euo pipefail

# 睡眠声音分析器启动脚本

echo "🌙 Sleep Sound Analyzer - 启动中..."
echo "================================"

# 检查Python版本
python_version_full=$(python3 --version 2>&1)
python_version=$(echo "$python_version_full" | awk '{print $2}')
echo "Python 版本: $python_version"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    # 只有在创建 venv 时才要求系统 python3 足够新
    python_major=$(echo "$python_version" | awk -F. '{print $1}')
    python_minor=$(echo "$python_version" | awk -F. '{print $2}')
    if [ "${python_major:-0}" -lt 3 ] || { [ "${python_major:-0}" -eq 3 ] && [ "${python_minor:-0}" -lt 11 ]; }; then
        echo "❌ 当前 python3 版本过低: $python_version_full"
        echo "   请使用 Python >= 3.11（推荐 3.13），或先安装/切换到新版本后再运行。"
        exit 1
    fi

    echo "⚠️  未发现虚拟环境，正在创建..."
    python3 -m venv venv
    echo "✅ 虚拟环境创建完成"
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate
echo "虚拟环境 Python: $(python --version 2>&1)"

# 检查依赖
if ! python -c "import flask" >/dev/null 2>&1; then
    echo "📦 安装依赖包..."
    python -m pip install --upgrade pip setuptools wheel
    python -m pip install -r requirements.txt
    echo "✅ 依赖安装完成"
else
    echo "✅ 依赖已安装"
fi

# 创建必要的目录
mkdir -p data/raw data/processed output/reports output/visualizations

echo ""
echo "================================"
echo "🚀 启动 Web 服务..."
echo "================================"
echo ""
PORT="${PORT:-5050}"
echo "访问地址: http://localhost:$PORT"
echo "按 Ctrl+C 停止服务"
echo ""

# 启动应用
PORT="$PORT" python app.py
