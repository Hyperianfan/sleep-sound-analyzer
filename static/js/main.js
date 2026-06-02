// 主JavaScript文件

let currentFile = null;

// DOM 元素
const fileInput = document.getElementById('fileInput');
const dropZone = document.getElementById('dropZone');
const selectedFileDiv = document.getElementById('selectedFile');
const fileName = document.getElementById('fileName');
const clearFileBtn = document.getElementById('clearFile');
const analyzeBtn = document.getElementById('analyzeBtn');
const resultSection = document.getElementById('resultSection');

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadHistoryReports();
});

function initializeEventListeners() {
    // 文件选择
    dropZone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileSelect);

    // 拖拽上传
    dropZone.addEventListener('dragover', handleDragOver);
    dropZone.addEventListener('dragleave', handleDragLeave);
    dropZone.addEventListener('drop', handleDrop);

    // 清除文件
    clearFileBtn.addEventListener('click', clearFile);

    // 分析按钮
    analyzeBtn.addEventListener('click', analyzeAudio);
}

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        setSelectedFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');

    const file = e.dataTransfer.files[0];
    if (file) {
        setSelectedFile(file);
    }
}

function setSelectedFile(file) {
    currentFile = file;
    fileName.textContent = file.name;
    dropZone.style.display = 'none';
    selectedFileDiv.style.display = 'flex';
    analyzeBtn.disabled = false;
}

function clearFile() {
    currentFile = null;
    fileInput.value = '';
    dropZone.style.display = 'block';
    selectedFileDiv.style.display = 'none';
    analyzeBtn.disabled = true;
}

async function analyzeAudio() {
    if (!currentFile) return;

    // 显示加载状态
    const btnText = analyzeBtn.querySelector('.btn-text');
    const btnLoading = analyzeBtn.querySelector('.btn-loading');
    btnText.style.display = 'none';
    btnLoading.style.display = 'flex';
    analyzeBtn.disabled = true;

    try {
        // 上传文件
        const formData = new FormData();
        formData.append('file', currentFile);

        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            displayResults(data.result);
            loadHistoryReports();
        } else {
            alert('分析失败: ' + data.error);
        }

    } catch (error) {
        console.error('Error:', error);
        alert('分析出错: ' + error.message);
    } finally {
        // 恢复按钮状态
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        analyzeBtn.disabled = false;
    }
}

function displayResults(result) {
    const stats = result.statistics;
    const events = result.events;
    const suggestions = result.suggestions;

    // 显示结果区域
    resultSection.style.display = 'block';
    resultSection.scrollIntoView({ behavior: 'smooth' });

    // 更新统计卡片
    updateStatsCards(stats);

    // 显示建议
    displaySuggestions(suggestions);

    // 显示事件列表
    displayEvents(events);
}

function updateStatsCards(stats) {
    // 打呼
    document.getElementById('snoreCount').textContent = stats.snoring.count;
    document.getElementById('snoreTime').textContent = (stats.snoring.total_time / 60).toFixed(1);
    document.getElementById('snorePercent').textContent = stats.snoring.percentage.toFixed(2);

    // 磨牙
    document.getElementById('grindCount').textContent = stats.grinding.count;
    document.getElementById('grindTime').textContent = (stats.grinding.total_time / 60).toFixed(1);
    document.getElementById('grindPercent').textContent = stats.grinding.percentage.toFixed(2);

    // 梦话
    document.getElementById('talkCount').textContent = stats.talking.count;
    document.getElementById('talkTime').textContent = (stats.talking.total_time / 60).toFixed(1);
    document.getElementById('talkPercent').textContent = stats.talking.percentage.toFixed(2);

    // 总时长
    document.getElementById('totalHours').textContent = stats.total_duration_hours.toFixed(1);
    document.getElementById('totalMinutes').textContent = `${Math.floor(stats.total_duration / 60)} 分钟`;
}

function displaySuggestions(suggestions) {
    const container = document.getElementById('suggestions');
    container.innerHTML = '<h3>💡 健康建议</h3>';

    suggestions.forEach(suggestion => {
        const div = document.createElement('div');
        div.className = `suggestion suggestion-${suggestion.level}`;

        const levelIcons = {
            'success': '✅',
            'info': 'ℹ️',
            'warning': '⚠️'
        };

        const icon = levelIcons[suggestion.level] || 'ℹ️';

        div.innerHTML = `
            <h4>${icon} ${suggestion.message}</h4>
            <ul>
                ${suggestion.advice.map(item => `<li>${item}</li>`).join('')}
            </ul>
        `;

        container.appendChild(div);
    });
}

function displayEvents(events) {
    const container = document.getElementById('eventsList');
    container.innerHTML = '';

    if (events.length === 0) {
        container.innerHTML = '<p class="empty-state">未检测到任何事件</p>';
        return;
    }

    // 只显示前50个事件
    const displayEvents = events.slice(0, 50);

    displayEvents.forEach((event, index) => {
        const div = document.createElement('div');
        div.className = 'event-item';

        const typeNames = {
            'snoring': '打呼',
            'grinding': '磨牙',
            'talking': '梦话'
        };

        const typeName = typeNames[event.type] || event.type;
        const timeStr = formatTimestamp(event.timestamp);
        const durationStr = formatDuration(event.duration);

        div.innerHTML = `
            <span class="event-type event-type-${event.type}">
                ${typeName} #${index + 1}
            </span>
            <span class="event-time">
                ${timeStr} · 持续 ${durationStr} · 置信度 ${(event.confidence * 100).toFixed(0)}%
            </span>
        `;

        container.appendChild(div);
    });

    if (events.length > 50) {
        const more = document.createElement('p');
        more.className = 'empty-state';
        more.textContent = `还有 ${events.length - 50} 个事件未显示...`;
        container.appendChild(more);
    }
}

function formatTimestamp(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds.toFixed(0)}秒`;
    } else {
        const minutes = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${minutes}分${secs}秒`;
    }
}

async function loadHistoryReports() {
    try {
        const response = await fetch('/api/reports');
        const data = await response.json();

        if (data.success) {
            displayHistory(data.reports);
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function displayHistory(reports) {
    const container = document.getElementById('historyList');

    if (reports.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无历史报告</p>';
        return;
    }

    container.innerHTML = '';

    reports.forEach(report => {
        const div = document.createElement('div');
        div.className = 'history-item';

        const date = new Date(report.date);
        const dateStr = date.toLocaleString('zh-CN');
        const durationStr = (report.duration / 3600).toFixed(1);

        div.innerHTML = `
            <div>
                <strong>${report.filename}</strong>
                <div style="font-size: 0.9rem; color: var(--text-secondary);">
                    ${dateStr} · ${durationStr} 小时
                </div>
            </div>
            <button class="btn-clear" onclick="loadReport('${report.filename}')">查看</button>
        `;

        container.appendChild(div);
    });
}

async function loadReport(filename) {
    try {
        const response = await fetch(`/api/reports/${filename}`);
        const data = await response.json();

        if (data.success) {
            displayResults(data.result);
        }
    } catch (error) {
        console.error('Error loading report:', error);
        alert('加载报告失败');
    }
}
