"""FFmpeg / ffprobe 工具封裝。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from typing import Sequence


class FFmpegError(Exception):
    pass


def require_tools() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if missing:
        raise FFmpegError(f"找不到必要工具: {', '.join(missing)}，請確認已安裝並在 PATH 中")


def run_command(args: Sequence[str], *, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise FFmpegError(f"指令失敗: {' '.join(args)}\n{stderr}") from exc
    except FileNotFoundError as exc:
        raise FFmpegError(f"找不到指令: {args[0]}") from exc


def die(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)
