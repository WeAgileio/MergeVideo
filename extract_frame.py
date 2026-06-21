"""擷取影片第一幀或最後一幀為 PNG。"""

from __future__ import annotations

from pathlib import Path

from ffmpeg_utils import FFmpegError, run_command
from probe import probe_video


class ExtractError(Exception):
    pass


def resolve_output_path(video_path: Path, frame_suffix: str) -> Path:
    output_dir = video_path.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{video_path.stem}_{frame_suffix}.png"


def validate_video_path(path: Path) -> Path:
    if not path.exists():
        raise ExtractError(f"找不到檔案: {path}")
    if path.is_dir():
        raise ExtractError("請提供單一影片檔路徑，不支援資料夾輸入")
    if not path.is_file():
        raise ExtractError(f"不是有效的檔案: {path}")
    return path


def _extract_with_sseof(video_path: Path, output_path: Path, seek_seconds: float) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-sseof",
            f"{seek_seconds:g}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ]
    )


def _extract_with_duration(video_path: Path, output_path: Path, duration: float) -> None:
    if duration <= 0:
        seek = 0.0
    else:
        seek = max(duration - 0.04, 0.0)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{seek:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ]
    )


def _extract_at_start(video_path: Path, output_path: Path) -> None:
    run_command(
        [
            "ffmpeg",
            "-y",
            "-ss",
            "0",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(output_path),
        ]
    )


def _ensure_valid_output(output_path: Path, error_message: str) -> Path:
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise ExtractError(error_message)
    return output_path


def extract_first_frame(video_path: Path) -> Path:
    video_path = validate_video_path(video_path.resolve())
    probe_video(video_path)
    output_path = resolve_output_path(video_path, "FirstFrame")
    _extract_at_start(video_path, output_path)
    return _ensure_valid_output(output_path, "擷取第一幀失敗，未產生有效輸出檔")


def extract_last_frame(video_path: Path) -> Path:
    video_path = validate_video_path(video_path.resolve())
    info = probe_video(video_path)
    output_path = resolve_output_path(video_path, "LastFrame")

    try:
        _extract_with_sseof(video_path, output_path, -0.1)
    except FFmpegError:
        _extract_with_duration(video_path, output_path, info.duration)

    return _ensure_valid_output(output_path, "擷取最後一幀失敗，未產生有效輸出檔")
