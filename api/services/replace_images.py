"""指定時段把畫面整框換成靜態圖（Pillow contain + ffmpeg overlay）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ffmpeg_utils import run_ffmpeg_with_progress
from probe import probe_video

REPLACE_CRF = 18


class ReplaceImagesError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Replacement:
    image_path: Path
    start: float
    end: float


def render_contained_png(
    image_path: Path, dest: Path, *, width: int, height: int
) -> None:
    """把圖等比縮到不超出 width×height，置中貼上黑底畫布；透明處由黑底補齊。"""
    try:
        with Image.open(image_path) as source:
            source.load()
            image = source.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ReplaceImagesError(
            "INVALID_IMAGE", f"無法解讀圖片: {image_path.name}"
        ) from exc

    scale = min(width / image.width, height / image.height)
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    offset = ((width - new_size[0]) // 2, (height - new_size[1]) // 2)
    canvas.paste(resized, offset, resized)
    canvas.save(dest, "PNG")


def _overlay_filter(ranges: list[tuple[float, float]]) -> str:
    parts: list[str] = []
    last = "0:v"
    for index, (start, end) in enumerate(ranges, start=1):
        out = "vout" if index == len(ranges) else f"v{index}"
        parts.append(
            f"[{last}][{index}:v]overlay=0:0:enable='between(t\\,{start}\\,{end})'[{out}]"
        )
        last = out
    return ";".join(parts)


def replace_images(
    video_path: Path,
    replacements: list[Replacement],
    output_path: Path,
    *,
    work_dir: Path,
    progress_callback=None,
) -> None:
    info = probe_video(video_path)

    longest_end = max(item.end for item in replacements)
    if info.duration > 0 and longest_end > info.duration:
        raise ReplaceImagesError(
            "INVALID_RANGE", f"end 超過影片長度 {round(info.duration, 3)} 秒: {longest_end}"
        )

    png_paths: list[Path] = []
    for index, item in enumerate(replacements):
        png = work_dir / f"replace_{index:03d}.png"
        render_contained_png(item.image_path, png, width=info.width, height=info.height)
        png_paths.append(png)

    inputs: list[str] = ["-i", str(video_path)]
    for png in png_paths:
        inputs.extend(["-i", str(png)])

    filter_complex = _overlay_filter([(item.start, item.end) for item in replacements])
    args = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-c:v",
        "libx264",
        "-crf",
        str(REPLACE_CRF),
        "-pix_fmt",
        "yuv420p",
    ]
    if info.has_audio:
        args.extend(["-map", "0:a", "-c:a", "copy"])
    else:
        args.append("-an")
    args.append(str(output_path))

    if progress_callback is not None and info.duration > 0:
        run_ffmpeg_with_progress(
            args, total_duration=info.duration, on_progress=progress_callback
        )
    else:
        from ffmpeg_utils import run_command

        run_command(args)
