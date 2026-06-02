"""
Web 应用主程序
"""
import os
import logging
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from src.analyzer import SleepSoundAnalyzer

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)


def _error(message, status=500):
    """统一的错误响应。"""
    return jsonify({'success': False, 'error': message}), status

# 配置
UPLOAD_FOLDER = Path('data/raw')
REPORTS_FOLDER = Path('output/reports')
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
REPORTS_FOLDER.mkdir(parents=True, exist_ok=True)

# 初始化分析器
analyzer = SleepSoundAnalyzer()


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    分析音频文件
    """
    try:
        # 兼容两种请求：
        # 1) application/json: {"file_path": "..."}
        # 2) multipart/form-data: file=<uploaded file> 或 file_path=<...>
        data = request.get_json(silent=True) or {}

        audio_path = None
        if isinstance(data, dict) and data.get('file_path'):
            audio_path = data['file_path']
        elif request.form.get('file_path'):
            audio_path = request.form.get('file_path')
        elif 'file' in request.files:
            file = request.files['file']
            if not file or not file.filename:
                return _error('未提供音频文件', 400)
            safe_name = secure_filename(file.filename)
            if not safe_name:
                return _error('文件名无效', 400)
            audio_path = UPLOAD_FOLDER / safe_name
            file.save(audio_path)

        if not audio_path:
            return _error('未提供音频文件', 400)

        # 执行分析
        result = analyzer.analyze_audio(audio_path)

        # 保存报告
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = REPORTS_FOLDER / f'report_{timestamp}.json'
        analyzer.save_report(result, report_path)

        return jsonify({
            'success': True,
            'result': result,
            'report_path': str(report_path)
        })

    except Exception as e:
        app.logger.exception('分析失败')
        return _error(str(e))


@app.route('/api/reports')
def list_reports():
    """
    获取所有报告列表
    """
    try:
        reports = []
        for report_file in sorted(REPORTS_FOLDER.glob('*.json'), reverse=True):
            with open(report_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                reports.append({
                    'filename': report_file.name,
                    'date': data['metadata']['analyzed_at'],
                    'duration': data['metadata']['total_duration']
                })

        return jsonify({
            'success': True,
            'reports': reports
        })

    except Exception as e:
        app.logger.exception('读取报告列表失败')
        return _error(str(e))


@app.route('/api/reports/<filename>')
def get_report(filename):
    """
    获取指定报告
    """
    try:
        report_path = REPORTS_FOLDER / filename
        if not report_path.exists():
            return jsonify({'error': '报告不存在'}), 404

        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        return jsonify({
            'success': True,
            'result': data
        })

    except Exception as e:
        app.logger.exception('读取报告失败')
        return _error(str(e))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5050'))
    app.run(debug=True, host='0.0.0.0', port=port)
