from pathlib import Path

import requests
from tqdm import tqdm

from subtitle import parse_srt, save_translated_srt

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gpt-oss:120b"
BATCH_SIZE = 20

_SYSTEM_PROMPT = (
    "你是专业字幕翻译员。将用户提供的字幕文本翻译为简体中文。"
    "输入格式为「序号: 文本」，输出格式完全相同，每行一条，不添加任何解释或额外内容。"
    "译文简洁自然，符合字幕阅读习惯。"
)


def _translate_batch(texts: list[str], ollama_url: str, model: str) -> list[str]:
    numbered = "\n".join(f"{i + 1}: {t}" for i, t in enumerate(texts))
    resp = requests.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": numbered},
            ],
            "stream": False,
        },
        timeout=180,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"].strip()

    results = list(texts)
    for line in content.splitlines():
        line = line.strip()
        if not line or ": " not in line:
            continue
        idx_str, translated = line.split(": ", 1)
        try:
            idx = int(idx_str.strip()) - 1
            if 0 <= idx < len(texts):
                results[idx] = translated.strip()
        except ValueError:
            pass
    return results


def translate_srt(
    srt_path: Path,
    output_path: Path,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    model: str = DEFAULT_MODEL,
) -> bool:
    entries = parse_srt(srt_path)
    if not entries:
        return False

    batches = [entries[i: i + BATCH_SIZE] for i in range(0, len(entries), BATCH_SIZE)]
    translated_entries = []

    for batch in tqdm(batches, desc="  Translating", unit="batch", leave=False):
        texts = [e["text"] for e in batch]
        try:
            translated = _translate_batch(texts, ollama_url, model)
        except Exception as e:
            tqdm.write(f"  [WARN] batch failed ({e}), keeping original")
            translated = texts
        for entry, new_text in zip(batch, translated):
            translated_entries.append({**entry, "text": new_text})

    save_translated_srt(translated_entries, output_path)
    return True
