"""ffprobe 解析影片 metadata。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from ffmpeg_utils import run_command


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    fps_num: int
    fps_den: int
    vcodec: str
    pix_fmt: str
    has_audio: bool
    acodec: str | None
    sample_rate: int | None
    channels: int | None
    duration: float

    @property
    def pixel_area(self) -> int:
        return self.width * self.height

    @property
    def fps_label(self) -> str:
        if self.fps_den == 0:
            return "?"
        value = Fraction(self.fps_num, self.fps_den)
        return f"{float(value):g}"

    @property
    def fps_float(self) -> float:
        if self.fps_den == 0:
            return 30.0
        return float(Fraction(self.fps_num, self.fps_den))

    @property
    def audio_label(self) -> str:
        if not self.has_audio:
            return "無"
        return f"{self.acodec} {self.sample_rate}Hz"


def _parse_fps(rate: str) -> tuple[int, int]:
    if "/" in rate:
        num, den = rate.split("/", 1)
        return int(num), int(den)
    value = float(rate)
    frac = Fraction(value).limit_denominator(1001)
    return frac.numerator, frac.denominator


def probe_video(path: Path) -> VideoInfo:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ]
    )
    data = json.loads(result.stdout)

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError(f"找不到影片串流: {path.name}")

    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or video_stream.get("duration") or 0)

    fps_num, fps_den = _parse_fps(video_stream.get("r_frame_rate", "30/1"))

    return VideoInfo(
        path=path,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        fps_num=fps_num,
        fps_den=fps_den,
        vcodec=video_stream.get("codec_name", "unknown"),
        pix_fmt=video_stream.get("pix_fmt", "unknown"),
        has_audio=audio_stream is not None,
        acodec=audio_stream.get("codec_name") if audio_stream else None,
        sample_rate=int(audio_stream["sample_rate"]) if audio_stream and audio_stream.get("sample_rate") else None,
        channels=int(audio_stream.get("channels", 0)) if audio_stream else None,
        duration=duration,
    )


def probe_all(paths: list[Path]) -> list[VideoInfo]:
    return [probe_video(path) for path in paths]


def pick_output_size(videos: list[VideoInfo]) -> tuple[int, int, VideoInfo]:
    best = videos[0]
    for video in videos[1:]:
        if video.pixel_area > best.pixel_area:
            best = video
    return best.width, best.height, best
