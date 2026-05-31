#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from transcribe import DEFAULT_MODEL as DEFAULT_WHISPER_MODEL
from transcribe import find_media_files, transcribe_file
from translate import DEFAULT_MODEL as DEFAULT_OLLAMA_MODEL
from translate import DEFAULT_OLLAMA_URL, translate_srt
from subtitle import cjk_ratio, parse_srt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MLX Whisper 字幕生成 + Ollama 中文翻译")
    p.add_argument("--input", type=Path, default=Path("media"), metavar="DIR")
    p.add_argument("--output", type=Path, default=Path("subtitles"), metavar="DIR")
    p.add_argument("--force", action="store_true", help="强制重新处理已有字幕")
    p.add_argument("--no-translate", action="store_true", help="只转录，不翻译")
    p.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL, metavar="MODEL")
    p.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL, metavar="URL")
    p.add_argument("--ollama-model", default=DEFAULT_OLLAMA_MODEL, metavar="MODEL")
    return p


def _is_chinese(language: str | None, srt_path: Path) -> bool:
    if language and language.startswith("zh"):
        return True
    if language is None and srt_path.exists():
        entries = parse_srt(srt_path)
        sample = " ".join(e["text"] for e in entries[:30])
        return cjk_ratio(sample) > 0.3
    return False


def main() -> None:
    args = build_parser().parse_args()

    if not args.input.exists():
        print(f"[ERROR] 媒体文件夹不存在: {args.input}")
        sys.exit(1)

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"扫描媒体文件: {args.input}")
    media_files = find_media_files(args.input)

    if not media_files:
        print("未找到任何媒体文件")
        sys.exit(0)

    print(f"找到 {len(media_files)} 个媒体文件\n")
    print(f"Whisper 模型 : {args.whisper_model}")
    if not args.no_translate:
        print(f"翻译模型     : {args.ollama_model} @ {args.ollama_url}")
    print()

    stats = {"ok": 0, "skip": 0, "fail": 0, "translated": 0}

    for i, file_path in enumerate(tqdm(media_files, desc="Total", unit="file"), 1):
        tqdm.write(f"\n[{i}/{len(media_files)}] {file_path.name}")

        result = transcribe_file(
            file_path,
            output_dir=args.output,
            model_name=args.whisper_model,
            force=args.force,
        )

        if result is None:
            stats["fail"] += 1
            continue

        srt_path = result["srt_path"]
        language = result.get("language")

        if result["skipped"]:
            tqdm.write(f"  [SKIP] 字幕已存在: {srt_path.name}")
            stats["skip"] += 1
        else:
            tqdm.write(f"  [OK]   转录完成 → {srt_path.name}  (lang={language})")
            stats["ok"] += 1

        if args.no_translate:
            continue

        zh_srt_path = args.output / (file_path.name + ".zh.srt")

        if _is_chinese(language, srt_path):
            tqdm.write("  [SKIP] 原始语言为中文，跳过翻译")
            continue

        if zh_srt_path.exists() and not args.force:
            tqdm.write(f"  [SKIP] 中文字幕已存在: {zh_srt_path.name}")
            continue

        ok = translate_srt(srt_path, zh_srt_path, args.ollama_url, args.ollama_model)
        if ok:
            tqdm.write(f"  [OK]   翻译完成 → {zh_srt_path.name}")
            stats["translated"] += 1
        else:
            tqdm.write("  [WARN] 翻译失败")

    print(f"\n{'='*50}")
    print(
        f"完成！  转录 {stats['ok']}  翻译 {stats['translated']}"
        f"  跳过 {stats['skip']}  失败 {stats['fail']}"
    )


if __name__ == "__main__":
    main()
