# 睡眠声音分析器 (Sleep Sound Analyzer)

🌙 基于 AI 的睡眠录音智能分析系统，自动检测打呼、磨牙、梦话等睡眠声音事件。

## 功能特性

✅ **三种声音检测**
- 🔊 打呼检测：识别打鼾频次、时长和严重程度
- 😬 磨牙检测：检测夜间磨牙行为
- 💬 梦话检测：识别说梦话事件

✅ **智能分析**
- 自动降噪处理
- 多维度特征提取
- 基于规则的智能分类
- 事件合并与统计

✅ **可视化报告**
- 美观的 Web 界面
- 概览统计卡片
- 详细事件列表
- 健康建议生成

✅ **历史记录**
- 自动保存分析报告
- 历史报告查看
- 趋势对比分析

## 技术架构

### 后端
- Python 3.11+
- Flask (Web 框架)
- Librosa (音频处理)
- NumPy / SciPy (科学计算)

### 前端
- HTML5 + CSS3
- JavaScript (原生)

## 快速开始

### 1. 安装依赖

```bash
cd sleep-sound-analyzer

# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

### 2. 启动应用

```bash
# 方式1：直接运行
python app.py

# 方式2：使用启动脚本
chmod +x run.sh
./run.sh
```

### 3. 访问界面

打开浏览器访问：**http://localhost:5050**

## 使用说明

### 分析录音文件

1. **上传文件**
   - 点击上传区域选择文件
   - 或直接拖拽 WAV/MP3/M4A 文件到上传区域

2. **开始分析**
   - 点击"开始分析"按钮
   - 等待分析完成（时间取决于文件大小）

3. **查看结果**
   - 概览卡片：显示各类声音的统计数据
   - 健康建议：基于检测结果的改善建议
   - 事件详情：每个检测事件的详细信息

### 查看历史报告

- 在"历史报告"区域点击任意报告
- 自动加载并显示该报告的详细内容

## 作为 MCP Server 使用（供其它 agent 调用）

除了 Web 界面，本项目还把识别能力封装成了 **MCP Server**，任何支持 MCP 的
LLM 客户端（Claude Desktop、Claude Code 等）都能直接调用，无需写代码。

### 提供的工具

| 工具 | 说明 |
| --- | --- |
| `analyze_sleep_audio(audio_path, apply_noise_reduction=True, save_report=True, backend="hybrid")` | 分析单晚录音，返回统计、事件、健康建议、**单晚睡眠分**，以及可直接展示的 `summary` markdown |
| `analyze_sleep_batch(audio_paths, apply_noise_reduction=True, save_report=True, backend="hybrid")` | **连续分析多份录音**，给出每晚睡眠分并做**多晚趋势对比**（变好/变差/持平） |
| `analyze_sleep_trend(filenames=None, date_from="", date_to="", only_dated=True)` | 对**已保存的历史报告**做趋势分析，无需重跑音频；可按文件名或录音日期范围筛选。`only_dated=True`（默认）只纳入带录音日期的正式报告，自动跳过旧报告 |
| `list_sleep_reports()` | 列出历史报告（按时间倒序） |
| `get_sleep_report(filename)` | 读取指定历史报告 |

### 每晚睡眠分与多晚趋势

- **单晚睡眠分**：把各类声音按"每小时次数"归一化后加权，得到 0~100 的睡眠分
  （越高越好）与等级（优/良/一般/差）。每份结果的 `score` 字段即此，权重见
  `src/config.py` 的 `SCORE_WEIGHTS`。**这是经验启发式，非医学诊断。**
- **多晚趋势**：把多晚的睡眠分按录音日期排序后比较，给出
  `overall_direction`（`improving`/`worsening`/`stable`）、各指标首末变化与中文结论。
  睡眠分变化超过 `TREND_SCORE_DELTA`（默认 5 分）才判定为变好/变差，否则视为持平。
- **录音日期**从文件名自动解析（如 `2026-06-02_03_06_12`）；也可调用时显式传入
  `recording_started_at`。

```text
用法示例（对 agent 说）：
  "连续分析这几段录音，看看我这几晚睡眠是变好还是变差：
   /path/a.wav /path/b.wav /path/c.wav"
  → 调 analyze_sleep_batch

  "对比我最近保存的报告，分析 2026-06-01 到 06-07 的睡眠趋势"
  → 调 analyze_sleep_trend(date_from="2026-06-01", date_to="2026-06-07")
```

### 分类后端（hybrid / yamnet / rule）

`analyze_sleep_audio` 的 `backend` 参数可选：

- **`"hybrid"`（默认，推荐）**：YAMNet 测**打鼾/梦话** + 规则测**磨牙**，兼顾两者所长。
- **`"yamnet"`**：纯 YAMNet。打鼾/梦话很准，但磨牙基本测不到。
- **`"rule"`**：纯手工规则，无额外依赖，开箱即用。

YAMNet 基于 Google 在 AudioSet 上的预训练模型，准确率更高，尤其能把电视/风扇等
环境噪声与真正的梦话区分开（规则后端最容易在这里误判）。CPU 即可推理，无需 GPU。

`hybrid` / `yamnet` 需安装额外依赖（约几百 MB）：

```bash
pip install ".[yamnet]"
```

> 说明：
> - 首次用到 YAMNet 时会从 TF Hub 下载模型（约 17MB）并懒加载，之后缓存复用。
> - **依赖缺失时自动回退到 `rule`** 并告警，实际生效的后端见返回的
>   `metadata.backend`，因此默认值设为 `hybrid` 也不会让没装 tensorflow 的用户报错。
> - AudioSet 没有干净的**磨牙(bruxism)** 类，所以磨牙交给规则检测；这也是用
>   `hybrid` 而非纯 `yamnet` 的原因。
> - 事件时间戳已映射回**录音真实时间**（去静音拼接不再导致时间错位）。

报告与 Web 应用共用 `output/reports/`，所以 agent 分析完，用户能在网页里直接查看。

### 接入方式

参考 `mcp.example.json`，二选一：

**方式 A：安装本包后用入口命令（推荐，配置最干净）**

```bash
git clone https://github.com/haydenliu-crypto/sleep-sound-analyzer.git
cd sleep-sound-analyzer
python3 -m venv venv && source venv/bin/activate
pip install .            # 会注册 `sleep-sound-analyzer` 命令
```

```jsonc
{
  "mcpServers": {
    "sleep-sound-analyzer": {
      "command": "sleep-sound-analyzer"
    }
  }
}
```

> 注意：入口命令位于该 venv 内。客户端若不是在激活该 venv 的环境里启动，
> 请把 `command` 写成 venv 里命令的绝对路径，如
> `/abs/path/to/venv/bin/sleep-sound-analyzer`。

**方式 B：仅 clone，不安装，用 venv 的 python 直接跑脚本**

```bash
pip install -r requirements.txt
```

```jsonc
{
  "mcpServers": {
    "sleep-sound-analyzer": {
      "command": "/abs/path/to/venv/bin/python",
      "args": ["/abs/path/to/sleep-sound-analyzer/mcp_server.py"]
    }
  }
}
```

- Claude Code：放进项目根目录的 `.mcp.json`，或 `claude mcp add` 注册。
- Claude Desktop：加到 `claude_desktop_config.json` 的 `mcpServers` 字段。

接好后，直接对 agent 说「帮我分析这段睡眠录音 /path/to/xxx.wav」即可。

> 报告默认写到项目内 `output/reports/`。若本包被装到别处（如 site-packages），
> 可用环境变量 `SLEEP_REPORTS_DIR` 指定一个可写目录。
>
> 说明：本 server 走 stdio 传输，stdout 被 MCP 协议独占。分析器内部的 print
> 日志已重定向到 stderr，不会污染协议。
>
> ⚠️ `audio_path` 是**运行 server 那台机器上**的本地路径——别人接入后，要分析的
> 音频文件需放在他们自己的机器上。

### 分发给别人

1. 把仓库推到 GitHub（已含 `pyproject.toml` / `LICENSE` / `.gitignore`）。
2. 对方按上面「方式 A」clone + `pip install .` 即可使用。
3. 想被注册表搜索到（官方 MCP Registry / Smithery 等）、或做成 `uvx`
   一行安装、Docker 镜像，可在此基础上继续，详见 issue/后续计划。

## 项目结构

```
sleep-sound-analyzer/
├── app.py                  # Flask 应用主程序
├── mcp_server.py           # MCP Server（封装识别能力供 agent 调用）
├── mcp.example.json        # MCP 客户端接入配置示例
├── pyproject.toml          # 打包/安装配置（提供 sleep-sound-analyzer 命令）
├── requirements.txt        # Python 依赖
├── LICENSE                 # MIT 许可证
├── .gitignore             # 忽略 venv/录音/报告等
├── README.md              # 项目说明
├── run.sh                 # 启动脚本
├── src/                   # 核心代码
│   ├── preprocessor.py    # 音频预处理
│   ├── feature_extractor.py # 特征提取
│   ├── classifier.py      # 声音分类器
│   └── analyzer.py        # 主分析器
├── static/                # 静态资源
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
├── templates/             # HTML 模板
│   └── index.html
├── data/                  # 数据目录
│   ├── raw/              # 原始音频
│   └── processed/        # 处理后的音频
└── output/               # 输出目录
    ├── reports/          # JSON 报告
    └── visualizations/   # 可视化图表
```

## 算法说明

### 预处理流程

1. **音频加载**：统一采样率到 16kHz
2. **降噪**：使用 noisereduce 去除环境噪音
3. **归一化**：音量标准化
4. **静音去除**：删除长时间静音段
5. **分帧**：1秒窗口，0.5秒步长

### 分类（默认 hybrid）

默认采用 **hybrid 后端**，按声音类型分工：

- **打鼾 / 梦话 → YAMNet**：用 Google 在 AudioSet 上预训练的 YAMNet 模型，
  直接对应 AudioSet 的 `Snoring` / `Speech` 等类，准确率高，并能把电视、风扇等
  环境噪声与目标声音区分开。
- **磨牙 → 轻量规则兜底**：AudioSet 没有干净的磨牙(bruxism)类，故磨牙仍由规则
  检测（中高频、宽频带、高过零率等特征）。

其它可选后端见上文《[分类后端](#分类后端hybrid--yamnet--rule)》：`yamnet`（纯模型）、
`rule`（纯手工规则）。

### 特征提取（供规则/磨牙检测使用）

以下手工特征用于规则后端与 hybrid 的磨牙检测；YAMNet 不依赖它们，而是直接在
对数梅尔频谱上推理：

- **时域特征**：能量、过零率、RMS
- **频域特征**：频谱质心、滚降点、带宽、对比度
- **MFCC**：梅尔频率倒谱系数（13维）

## 性能指标

- **处理速度**：**远快于实时**。实测在 Apple Silicon（CPU）上，一段 3.86 小时
  / 424MB 的录音约 **40 秒**完成分析（降噪约占 3/4 耗时，YAMNet 推理+特征约 10 秒），
  折算约 1 小时录音 ≈ 10 秒，提速约数百倍。
- **内存占用**：< 500MB（处理500MB文件）
- **准确率**：默认 hybrid 后端下，打鼾/梦话由 AudioSet 预训练的 YAMNet 识别，
  对环境噪声的区分明显优于规则方案；磨牙仍是弱项（无对应预训练类）。
  > 注：目前尚无带标注的测试集，暂未给出量化的 precision/recall。建议后续标注
  > 1–2 晚录音作为评测集，再用实测数字替换此处描述。

## 常见问题

### Q: 支持哪些音频格式？
A: 主要支持 WAV 格式，也支持 MP3、M4A（会自动转换）

### Q: 文件太大怎么办？
A: 建议将超过1小时的录音分段处理，或使用降采样

### Q: 准确率如何提升？
A: 可以考虑：
- 收集标注数据训练机器学习模型
- 调整分类阈值参数
- 改善录音环境（减少噪音）

### Q: 如何通过 HTTP API 分析指定文件？
A: 在 API 请求中传入 `file_path` 参数即可：

```python
import requests

response = requests.post('http://localhost:5050/api/analyze', 
    json={'file_path': '/path/to/recording.wav'})
```

## 未来计划

### 第二期功能
- [ ] 整合 Apple Watch 睡眠数据
- [ ] 睡眠质量综合评分
- [ ] 呼吸暂停检测
- [ ] 主动健康预警推送

### 算法优化
- [ ] 训练深度学习模型
- [ ] 增加更多声音类型检测
- [ ] 实时分析模式

## 开发团队

Sleep Sound Analyzer v1.0  

## License

MIT License

---

**注意**: 本系统仅供参考，不能替代专业医疗诊断。如有严重睡眠问题，请及时就医。
