"""影片合併引擎（Copy / Encode）。"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from ffmpeg_utils import run_command
from probe import VideoInfo


def default_output_path(input_folder: Path) -> Path:
    output_dir = input_folder / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return output_dir / f"merged{timestamp}.mp4"


def resolve_output_path(input_folder: Path, custom_output: Path | None) -> Path:
    if custom_output is not None:
        custom_output.parent.mkdir(parents=True, exist_ok=True)
        return custom_output
    return default_output_path(input_folder)


def _escape_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")


def merge_copy(videos: list[VideoInfo], output_path: Path) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        list_path = Path(handle.name)
        for video in videos:
            handle.write(f"file '{_escape_concat_path(video.path)}'\n")

    try:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c",
                "copy",
                str(output_path),
            ]
        )
    finally:
        list_path.unlink(missing_ok=True)


def merge_encode(
    videos: list[VideoInfo],
    output_path: Path,
    *,
    width: int,
    height: int,
    fps: float,
    crf: int,
) -> None:
    inputs: list[str] = []
    for video in videos:
        inputs.extend(["-i", str(video.path)])

    video_filters: list[str] = []
    audio_filters: list[str] = []
    concat_inputs: list[str] = []

    fps_text = f"{fps:g}"

    for index, video in enumerate(videos):
        video_filters.append(
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps_text}[v{index}]"
        )
        if video.has_audio:
            audio_filters.append(
                f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo,aresample=48000[a{index}]"
            )
        else:
            duration = max(video.duration, 0.001)
            audio_filters.append(
                f"anullsrc=channel_layout=stereo:sample_rate=48000,atrim=duration={duration:.3f}[a{index}]"
            )
        concat_inputs.append(f"[v{index}][a{index}]")

    count = len(videos)
    filter_complex = (
        ";".join(video_filters + audio_filters)
        + ";"
        + "".join(concat_inputs)
        + f"concat=n={count}:v=1:a=1[outv][outa]"
    )

    run_command(
        [
            "ffmpeg",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ]
    )
