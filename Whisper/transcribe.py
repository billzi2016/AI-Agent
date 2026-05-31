import subprocess
from pathlib import Path

from tqdm import tqdm

from subtitle import save_srt

DEFAULT_MODEL = "mlx-community/whisper-large-v3-mlx"

_SKIP_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".sh", ".srt", ".vtt", ".ass", ".sub", ".jpg", ".jpeg", ".png", ".gif",
    ".bmp", ".svg", ".ico", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
    ".pptx", ".zip", ".tar", ".gz", ".rar", ".7z", ".exe", ".dmg", ".gitignore",
}


def _has_audio(file_path: Path) -> bool:
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "audio" in r.stdout
    except Exception:
        return False


def find_media_files(media_dir: Path) -> list[Path]:
    candidates = [
        p for p in media_dir.rglob("*")
        if p.is_file() and p.suffix.lower() not in _SKIP_SUFFIXES
    ]
    files = []
    for p in tqdm(candidates, desc="Scanning", unit="file", leave=False):
        if _has_audio(p):
            files.append(p)
    return sorted(files)


def transcribe_file(
    file_path: Path,
    output_dir: Path,
    model_name: str = DEFAULT_MODEL,
    force: bool = False,
) -> dict | None:
    import mlx_whisper

    srt_path = output_dir / (file_path.name + ".srt")

    if srt_path.exists() and not force:
        return {"srt_path": srt_path, "language": None, "skipped": True}

    try:
        result = mlx_whisper.transcribe(
            str(file_path),
            path_or_hf_repo=model_name,
            verbose=False,
        )
    except Exception as e:
        tqdm.write(f"  [ERROR] {e}")
        return None

    segments = result.get("segments", [])
    language = result.get("language", "")

    if not segments:
        tqdm.write("  [WARN] No speech detected")
        return None

    save_srt(segments, srt_path)
    return {"srt_path": srt_path, "language": language, "skipped": False}
