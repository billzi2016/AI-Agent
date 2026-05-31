# PRD — 本地视频/音频字幕生成与中文翻译工具

## 背景

在 Apple Silicon Mac 上，利用 MLX 加速的 Whisper 模型将 `media/` 文件夹中的视频和音频文件转为字幕，再通过本地 Ollama 大模型将非中文字幕翻译为中文，全程离线、无需联网。

---

## 目标

1. 扫描 `media/` 文件夹，自动识别音视频文件
2. 使用 MLX 加速的 Whisper large 模型进行语音识别，输出 SRT 字幕
3. 自动检测语言：若原始语言为中文则跳过翻译
4. 调用本地 Ollama `gpt-oss:120b` 模型将非中文字幕翻译成中文
5. 全程显示 tqdm 进度条，方便追踪处理进度
6. `media/` 及字幕文件不进入 Git（版权保护）

---

## 技术选型

| 组件 | 选型 | 备注 |
|------|------|------|
| 语音识别框架 | [`mlx-whisper`](https://pypi.org/project/mlx-whisper/) | Apple MLX 原生加速，充分利用 M 系列 GPU/ANE |
| Whisper 模型 | `mlx-community/whisper-large-v3-mlx` | Whisper large-v3，目前 MLX 生态最高精度模型 |
| 翻译模型 | Ollama `gpt-oss:120b` | OpenAI 开源 120B 模型，本地运行 |
| Ollama API | `http://localhost:11434` | 标准 REST 接口 |
| 进度显示 | `tqdm` | 文件级 + 字幕段级双层进度条 |
| 字幕格式 | SRT | 主流字幕格式，兼容性最好 |
| 语言 | Python 3.11+ | |

---

## 目录结构

```
Whisper/
├── PRD.md
├── README.md
├── .gitignore            # 排除 media/ 和 subtitles/
├── requirements.txt
├── main.py               # 入口，CLI 参数解析
├── transcribe.py         # MLX Whisper 转录逻辑
├── translate.py          # Ollama 翻译逻辑
├── subtitle.py           # SRT 解析与生成工具
├── media/                # ⚠️ gitignored — 放音视频源文件
└── subtitles/            # ⚠️ gitignored — 输出字幕文件
```

---

## 功能详情

### 1. 文件扫描

- 递归扫描 `media/` 文件夹
- 支持格式：**不限定扩展名白名单**，通过 `ffprobe` 探测文件是否包含音频流，支持任意 ffmpeg 可解码的格式
  - 典型格式包括但不限于：`.mp4` `.mov` `.mkv` `.avi` `.webm` `.m4v` `.mp3` `.wav` `.m4a` `.flac` `.aac` `.ogg` `.ts` `.rmvb` 等
- 跳过已有对应 SRT 的文件（可用 `--force` 覆盖）

### 2. 语音转录（MLX Whisper）

- 模型：`mlx-community/whisper-large-v3-mlx`（首次运行自动下载缓存）
- 自动检测语言
- 输出 SRT 到 `subtitles/<原文件名带扩展名>.srt`
- 支持长音频自动分段
- tqdm 显示当前文件处理进度

### 3. 语言判断

- Whisper 识别结果包含 `language` 字段
- 若 `language == "zh"`（中文）→ 直接保存 SRT，跳过翻译
- 其余语言 → 进入翻译流程

### 4. 字幕翻译（Ollama gpt-oss:120b）

- 调用 `http://localhost:11434/api/chat`
- 每次翻译一个 SRT 字幕段（保持时间轴不变，只替换文本）
- Prompt 策略：
  - 系统提示：要求输出纯中文译文，保持语气和标点，不添加解释
  - 批量翻译（每批 20 条字幕段），减少 API 调用次数
- 输出：`subtitles/<原文件名带扩展名>.zh.srt`
- tqdm 显示翻译进度（字幕段数）

### 5. 进度显示

```
[1/5] video.mp4
Transcribing:  ████████████████░░░░  78%  |  00:02:31 < 00:00:42
Translating:   ██████████░░░░░░░░░░  50%  |  245/489 segments
```

### 6. 字幕命名规则

**原则：保留原文件完整文件名（含扩展名），追加 `.srt` 后缀。**

| 源文件 | 转录字幕 | 中文翻译字幕 |
|--------|----------|--------------|
| `test.mp4` | `test.mp4.srt` | `test.mp4.zh.srt` |
| `lecture.mkv` | `lecture.mkv.srt` | `lecture.mkv.zh.srt` |
| `podcast.mp3` | `podcast.mp3.srt` | `podcast.mp3.zh.srt` |
| `recording.m4a` | `recording.m4a.srt` | `recording.m4a.zh.srt` |

> 原文本身是中文时只生成 `*.srt`，不生成 `*.zh.srt`。

### 7. 已存在文件检测

- 检测 `subtitles/<原文件名>.srt` 是否存在
  - 存在且非 `--force` → 跳过转录（tqdm 显示 `[SKIP]`）
  - 存在且非 `--force`，但 `*.zh.srt` 不存在 → 只补翻译步骤
- `--force` 覆盖所有已有输出

---

## CLI 接口

```bash
# 基本用法（处理 media/ 下所有文件）
python main.py

# 指定文件夹
python main.py --input ./media --output ./subtitles

# 强制重新处理已有字幕
python main.py --force

# 只转录不翻译
python main.py --no-translate

# 指定 Ollama 地址（非默认端口时）
python main.py --ollama-url http://localhost:11434

# 指定 Whisper 模型（如用量化版节省内存）
python main.py --whisper-model mlx-community/whisper-large-v3-mlx
```

---

## .gitignore 要求

```gitignore
# 版权保护：媒体源文件和字幕均不入库
media/
subtitles/
*.srt
*.vtt

# Python
__pycache__/
*.pyc
.venv/
```

---

## 依赖（requirements.txt 草案）

```
mlx-whisper>=0.4.0
tqdm>=4.66.0
requests>=2.31.0
ffmpeg-python>=0.2.0
```

> 系统依赖：需预装 `ffmpeg`（`brew install ffmpeg`）

---

## 非目标（Out of Scope）

- GUI 界面
- 云端 API 调用（全程本地离线）
- 说话人分离（Diarization）
- 双语字幕（SRT 只保留中文译文）
- Windows / Linux 支持（本工具专为 Apple Silicon 优化）

---

## 里程碑

| # | 任务 | 说明 |
|---|------|------|
| M1 | 项目初始化 | 目录结构、.gitignore、requirements.txt |
| M2 | 文件扫描模块 | 递归扫描 + 格式过滤 + 跳过逻辑 |
| M3 | MLX Whisper 转录 | 转录 → SRT 生成 + tqdm |
| M4 | 语言判断 | 检测中文跳过翻译 |
| M5 | Ollama 翻译模块 | 批量翻译字幕段 + tqdm |
| M6 | 集成与 CLI | main.py 串联所有模块 |
| M7 | 测试验证 | 用不同格式音视频文件验证端到端流程 |
