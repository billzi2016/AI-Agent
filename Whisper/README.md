# Whisper 字幕生成工具

本地音视频字幕生成 + 中文翻译。基于 [mlx-whisper](https://github.com/ml-explore/mlx-examples) 在 Apple Silicon 上做 MLX 加速转录，通过本地 [Ollama](https://ollama.com) 运行 `gpt-oss:120b` 完成翻译，全程离线。

## 环境要求

- Apple Silicon Mac（M1 / M2 / M3 / M4）
- Python 3.11+
- [ffmpeg](https://ffmpeg.org)（媒体解码）
- [Ollama](https://ollama.com)（翻译，可选）

## 安装

```bash
# 安装 ffmpeg
brew install ffmpeg

# 安装 Python 依赖
pip install -r requirements.txt
# 或使用 pyproject.toml
pip install -e .

# 拉取翻译模型（首次使用）
ollama pull gpt-oss:120b
```

## 使用

将音视频文件放入 `media/` 文件夹，然后运行：

```bash
python main.py
```

字幕输出到 `subtitles/` 文件夹，命名规则保留原扩展名：

```
media/lecture.mp4   →   subtitles/lecture.mp4.srt
                    →   subtitles/lecture.mp4.zh.srt  （非中文时）
```

### 常用选项

```bash
python main.py --force               # 强制重新处理已有字幕
python main.py --no-translate        # 只转录，不翻译
python main.py --input ./my_videos   # 指定媒体文件夹
python main.py --output ./subs       # 指定输出文件夹
python main.py --whisper-model mlx-community/whisper-large-v3-mlx
python main.py --ollama-model gpt-oss:120b
python main.py --ollama-url http://localhost:11434
```

### 全部参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | `media/` | 媒体文件夹 |
| `--output` | `subtitles/` | 字幕输出文件夹 |
| `--force` | false | 强制覆盖已有字幕 |
| `--no-translate` | false | 只转录，跳过翻译 |
| `--whisper-model` | `mlx-community/whisper-large-v3-mlx` | MLX Whisper 模型 |
| `--ollama-model` | `gpt-oss:120b` | Ollama 翻译模型 |
| `--ollama-url` | `http://localhost:11434` | Ollama 服务地址 |

## 支持格式

通过 `ffprobe` 探测音频流，支持任何 ffmpeg 可解码的格式，包括但不限于：

`.mp4` `.mov` `.mkv` `.avi` `.webm` `.m4v` `.mp3` `.wav` `.m4a` `.flac` `.aac` `.ogg` `.ts` 等

## Whisper 模型对比

| 模型 | 速度 | 精度 |
|------|------|------|
| `mlx-community/whisper-large-v3-mlx` | 较慢 | 最高（默认） |
| `mlx-community/whisper-large-v3-turbo` | 快 | 高 |
| `mlx-community/whisper-medium-mlx` | 更快 | 中 |

首次运行时模型会自动从 Hugging Face 下载并缓存到本地。

## 注意

- `media/` 和 `subtitles/` 已加入 `.gitignore`，不会进入版本控制（版权保护）
- Docker 镜像不支持 MLX 加速，仅用于 Ollama 服务部署，详见 [Dockerfile](Dockerfile)
