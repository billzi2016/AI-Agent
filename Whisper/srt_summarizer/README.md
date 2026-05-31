# srt_summarizer

读取上层流水线生成的中文字幕（`.zh.srt`），剥掉所有 SRT 格式，把纯文本发给本地 Ollama 做摘要，结果保存为 `.summary.txt`，和字幕文件放在同一目录。

## 依赖

```
pip install requests
```

需要本地运行 Ollama，且已拉取 `gpt-oss:120b` 模型。

## 用法

从项目根目录运行：

```bash
python srt_summarizer/main.py
```

默认读取 `subtitles/*.zh.srt`，摘要写回同目录。

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--input` | `subtitles/` | `.zh.srt` 所在目录 |
| `--output` | 同 `--input` | 摘要输出目录 |
| `--ollama-url` | `http://localhost:11434` | Ollama 地址 |
| `--model` | `gpt-oss:120b` | 使用的模型 |
| `--chunk-size` | `80000` | 每块最大字符数 |

## 分块策略

模型上下文窗口 256k token，单个中文字符约 1-2 token。  
默认每块 **8 万字符**（约 8-16 万 token），留足 prompt 和回复空间。

超过一块时：先逐块摘要，再合并成最终摘要。

## 输出

```
subtitles/
  video.mp4.zh.srt       ← 输入
  video.mp4.summary.txt  ← 输出
```

`.summary.txt` 已加入 `.gitignore`，不会提交。
