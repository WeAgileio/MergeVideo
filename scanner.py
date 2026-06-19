"""掃描資料夾並驗證數字序影片檔名。"""

from __future__ import annotations

import re
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
NUMERIC_STEM = re.compile(r"^\d+$")


class ScanError(Exception):
    pass


def scan_folder(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise ScanError(f"輸入資料夾不存在: {folder}")

    videos: list[Path] = []
    invalid: list[str] = []

    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if NUMERIC_STEM.match(entry.stem):
            videos.append(entry)
        else:
            invalid.append(entry.name)

    if invalid:
        names = "\n  ".join(sorted(invalid))
        raise ScanError(f"發現非數字檔名的影片:\n  {names}")

    if not videos:
        raise ScanError("資料夾內找不到任何影片檔")

    if len(videos) < 2:
        raise ScanError("至少需要 2 段影片才能合併（目前只有 1 段）")

    videos.sort(key=lambda path: int(path.stem))
    return videos
