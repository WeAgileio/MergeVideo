"""將 SRT 燒進影片畫面（Pillow 繪字 + ffmpeg overlay）。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from api.services.subtitle import SubtitleJobError
from ffmpeg_utils import run_ffmpeg_with_progress
from probe import probe_video

DEFAULT_FONT_SIZE = 48
DEFAULT_MARGIN_BOTTOM = 6
DEFAULT_MARGIN_UNIT = "percent"
FONT_SIZE_MIN = 1
FONT_SIZE_MAX = 512
BURN_CRF = 18

_CUE_TIME = re.compile(
    r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)


def srt_has_cues(text: str) -> bool:
    return bool(_CUE_TIME.search(text))


def srt_time_to_seconds(stamp: str) -> float:
    stamp = stamp.strip().replace(",", ".")
    hours, minutes, seconds = stamp.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def parse_srt_cues(text: str) -> list[tuple[float, float, str]]:
    """回傳 (start_sec, end_sec, text) 列表。"""
    cues: list[tuple[float, float, str]] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [line.rstrip("\r") for line in block.split("\n") if line.strip() != ""]
        if not lines:
            continue
        time_at = next((i for i, line in enumerate(lines) if _CUE_TIME.search(line)), None)
        if time_at is None:
            continue
        match = _CUE_TIME.search(lines[time_at])
        if match is None:
            continue
        start = srt_time_to_seconds(match.group(1))
        end = srt_time_to_seconds(match.group(2))
        body = "\n".join(lines[time_at + 1 :]).strip()
        if not body:
            continue
        cues.append((start, end, body))
    return cues


def compute_margin_v(
    frame_height: int, margin_bottom: float, margin_unit: str
) -> int:
    if margin_unit == "percent":
        return int(round(frame_height * margin_bottom / 100))
    return int(round(margin_bottom))


def render_cue_png(
    dest: Path,
    *,
    width: int,
    height: int,
    text: str,
    font_path: Path,
    font_size: int,
    margin_v: int,
) -> None:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), font_size)
    bbox = draw.multiline_textbbox(
        (0, 0), text, font=font, stroke_width=2, align="center"
    )
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) / 2 - bbox[0]
    y = height - margin_v - text_h - bbox[1]
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=2,
        stroke_fill=(0, 0, 0, 255),
        align="center",
    )
    image.save(dest, "PNG")


def _overlay_filter(cue_count: int, cues: list[tuple[float, float, str]]) -> str:
    if cue_count == 1:
        start, end, _ = cues[0]
        return (
            f"[0:v][1:v]overlay=0:0:enable='between(t\\,{start}\\,{end})'[vout]"
        )
    parts: list[str] = []
    last = "0:v"
    for index, (start, end, _) in enumerate(cues, start=1):
        out = "vout" if index == cue_count else f"v{index}"
        parts.append(
            f"[{last}][{index}:v]overlay=0:0:enable='between(t\\,{start}\\,{end})'[{out}]"
        )
        last = out
    return ";".join(parts)


def burn_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    *,
    font_path: Path,
    font_size: int,
    margin_bottom: float,
    margin_unit: str,
    progress_callback=None,
) -> None:
    if not font_path.is_file():
        raise SubtitleJobError("FONT_UNAVAILABLE", f"找不到字幕字型: {font_path}")

    srt_text = srt_path.read_text(encoding="utf-8")
    cues = parse_srt_cues(srt_text)
    if not cues:
        raise SubtitleJobError("INVALID_SRT", "SRT 沒有可用的字幕 cue")

    work_font = srt_path.parent / font_path.name
    if font_path.resolve() != work_font.resolve():
        shutil.copy2(font_path, work_font)

    info = probe_video(video_path)
    margin_v = compute_margin_v(info.height, margin_bottom, margin_unit)

    png_paths: list[Path] = []
    for index, (_start, _end, body) in enumerate(cues):
        png = srt_path.parent / f"cue_{index:03d}.png"
        render_cue_png(
            png,
            width=info.width,
            height=info.height,
            text=body,
            font_path=work_font,
            font_size=font_size,
            margin_v=margin_v,
        )
        png_paths.append(png)

    inputs: list[str] = ["-i", str(video_path)]
    for png in png_paths:
        inputs.extend(["-i", str(png)])

    filter_complex = _overlay_filter(len(cues), cues)
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
        str(BURN_CRF),
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
