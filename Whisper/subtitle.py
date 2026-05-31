from pathlib import Path


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def save_srt(segments: list, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = format_timestamp(seg["start"])
            end = format_timestamp(seg["end"])
            text = seg["text"].strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")


def parse_srt(srt_path: Path) -> list[dict]:
    entries = []
    blocks = srt_path.read_text(encoding="utf-8").strip().split("\n\n")
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0].strip())
            times = lines[1].strip()
            content = "\n".join(lines[2:]).strip()
            entries.append({"index": index, "times": times, "text": content})
        except (ValueError, IndexError):
            continue
    return entries


def save_translated_srt(entries: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(f"{entry['index']}\n{entry['times']}\n{entry['text']}\n\n")


def cjk_ratio(text: str) -> float:
    chars = [c for c in text if c.strip() and c not in "0123456789:,.->\n "]
    if not chars:
        return 0.0
    cjk = sum(1 for c in chars if "一" <= c <= "鿿")
    return cjk / len(chars)
