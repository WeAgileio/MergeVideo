"""FFmpeg / ffprobe 工具封裝。"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from typing import Callable, Sequence


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


def run_ffmpeg_with_progress(
    args: Sequence[str],
    *,
    total_duration: float,
    on_progress: Callable[[float], None],
) -> None:
    """執行 ffmpeg 並透過 `-progress pipe:1` 回報進度（0.0–1.0）。

    args 為完整 ffmpeg 指令（不含 -progress / -nostats，由本函式插入）。
    stderr 導入暫存檔避免 pipe 阻塞，失敗時取其尾端作為錯誤訊息。
    """
    cmd = [args[0], "-progress", "pipe:1", "-nostats", *args[1:]]

    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as stderr_file:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                text=True,
            )
        except FileNotFoundError as exc:
            raise FFmpegError(f"找不到指令: {cmd[0]}") from exc

        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            # out_time_ms 實際單位為微秒（ffmpeg 歷史行為）
            if line.startswith("out_time_ms=") and total_duration > 0:
                try:
                    elapsed = int(line.split("=", 1)[1]) / 1_000_000
                except ValueError:
                    continue
                on_progress(min(elapsed / total_duration, 1.0))

        proc.wait()
        if proc.returncode != 0:
            stderr_file.seek(0)
            tail = stderr_file.read()[-2000:]
            raise FFmpegError(f"指令失敗: {' '.join(cmd)}\n{tail.strip()}")


def die(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)
