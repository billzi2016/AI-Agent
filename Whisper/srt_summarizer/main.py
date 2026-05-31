#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import requests

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gpt-oss:120b"
CHUNK_SIZE = 80_000  # characters, safe under 256k token limit

_SUMMARIZE_PROMPT = (
    "你是专业内容摘要助手。请对以下字幕文本进行摘要，"
    "提炼核心内容、关键信息和重要观点，输出简洁清晰的中文摘要。"
    "专有名词（人名、地名、产品名、技术术语、品牌名等）和重要名词必须原样保留，不得省略或替换。"
    "直接输出摘要内容，不需要任何前缀或解释。"
)

_MERGE_PROMPT = (
    "你是专业内容摘要助手。以下是同一内容多个片段的分段摘要，"
    "请将它们整合为一篇连贯、完整的最终摘要。"
    "专有名词（人名、地名、产品名、技术术语、品牌名等）和重要名词必须原样保留，不得省略或替换。"
    "直接输出最终摘要，不需要任何前缀或解释。"
)


def strip_srt(srt_path: Path) -> str:
    blocks = srt_path.read_text(encoding="utf-8").strip().split("\n\n")
    lines = []
    for block in blocks:
        parts = block.strip().splitlines()
        if len(parts) < 3:
            continue
        # parts[0] = index, parts[1] = timestamp, parts[2:] = text
        text = "\n".join(parts[2:]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)


def _call_ollama(system: str, content: str, ollama_url: str, model: str) -> str:
    resp = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "stream": False,
        },
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def summarize(text: str, ollama_url: str, model: str, chunk_size: int, out_path: Path) -> str:
    chunks = [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    if len(chunks) == 1:
        return _call_ollama(_SUMMARIZE_PROMPT, chunks[0], ollama_url, model)

    chunks_dir = out_path.parent / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    print(f"  分 {len(chunks)} 块处理...")
    chunk_summaries = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  块 {i}/{len(chunks)}...", end=" ", flush=True)
        summary = _call_ollama(_SUMMARIZE_PROMPT, chunk, ollama_url, model)
        chunk_summaries.append(summary)
        part_path = chunks_dir / f"{out_path.stem}.part{i}.txt"
        part_path.write_text(summary, encoding="utf-8")
        print(f"完成 → chunks/{part_path.name}")

    print("  合并摘要...", end=" ", flush=True)
    merged = "\n\n".join(f"【片段{i}】\n{s}" for i, s in enumerate(chunk_summaries, 1))
    final = _call_ollama(_MERGE_PROMPT, merged, ollama_url, model)
    print("完成")
    return final


def main() -> None:
    p = argparse.ArgumentParser(description="SRT 中文字幕摘要生成器")
    p.add_argument("--input", type=Path, default=Path("../subtitles"), metavar="DIR")
    p.add_argument("--output", type=Path, default=None, metavar="DIR",
                   help="输出目录，默认与 --input 相同")
    p.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, metavar="URL")
    p.add_argument("--model", default=DEFAULT_MODEL, metavar="MODEL")
    p.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, metavar="CHARS",
                   help="每块最大字符数（默认 80000，对应约 80k-160k token）")
    args = p.parse_args()

    if args.output is None:
        args.output = args.input

    if not args.input.exists():
        print(f"[ERROR] 字幕目录不存在: {args.input}")
        sys.exit(1)

    # 优先 .zh.srt（翻译结果），没有则回退到 .srt（原始中文）
    zh_srt = {p.name.replace(".zh.srt", ""): p for p in args.input.glob("*.zh.srt")}
    raw_srt = {p.name.replace(".srt", ""): p for p in args.input.glob("*.srt")
               if not p.name.endswith(".zh.srt")}
    candidates = {**raw_srt, **zh_srt}  # zh.srt 覆盖同名 .srt

    if not candidates:
        print(f"未找到任何 .srt 或 .zh.srt 文件于: {args.input}")
        sys.exit(0)

    args.output.mkdir(parents=True, exist_ok=True)
    print(f"找到 {len(candidates)} 个字幕文件\n")

    for stem, srt_path in sorted(candidates.items()):
        out_path = args.output / f"{stem}.summary.txt"

        print(f"处理: {srt_path.name}")
        text = strip_srt(srt_path)
        if not text.strip():
            print("  [SKIP] 空文件\n")
            continue

        print(f"  文本长度: {len(text):,} 字符")
        summary = summarize(text, args.ollama_url, args.model, args.chunk_size, out_path)
        out_path.write_text(summary, encoding="utf-8")
        print(f"  [OK] → {out_path}\n")

    print("全部完成！")


if __name__ == "__main__":
    main()
