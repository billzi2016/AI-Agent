# ──────────────────────────────────────────────────────────────────────────────
# 注意：MLX 仅在 Apple Silicon 原生环境运行，Docker 容器内无法使用 MLX 加速。
# 此 Dockerfile 用于部署 Ollama 翻译服务（Linux / 云端），
# 或在非 Mac 环境下以 CPU 模式运行转录（需将 mlx-whisper 替换为 faster-whisper）。
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依赖安装（先复制 requirements 利用 Docker 层缓存）
COPY requirements.txt pyproject.toml ./

# 容器内用 faster-whisper 替代 mlx-whisper（CPU/CUDA 兼容）
RUN pip install --no-cache-dir \
        faster-whisper>=1.0.0 \
        tqdm>=4.66.0 \
        requests>=2.31.0

# 复制源码
COPY main.py transcribe.py translate.py subtitle.py ./

# 媒体和字幕通过 volume 挂载，不打包进镜像
VOLUME ["/app/media", "/app/subtitles"]

# Ollama 默认端口（若容器内同时跑 Ollama）
EXPOSE 11434

ENV OLLAMA_URL=http://host.docker.internal:11434
ENV WHISPER_MODEL=large-v3

ENTRYPOINT ["python", "main.py"]
CMD ["--input", "/app/media", "--output", "/app/subtitles"]
