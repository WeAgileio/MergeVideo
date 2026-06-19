"""Copy 模式相容性判定。"""

from __future__ import annotations

from dataclasses import dataclass, field

from probe import VideoInfo


@dataclass
class CompatResult:
    copy_ok: bool
    reasons: list[str] = field(default_factory=list)


def check_copy_compat(videos: list[VideoInfo]) -> CompatResult:
    reasons: list[str] = []
    ref = videos[0]

    for video in videos:
        if video.width != ref.width or video.height != ref.height:
            reasons.append(f"解析度不一致 ({video.path.name} 為 {video.width}×{video.height})")

    for video in videos[1:]:
        if video.vcodec != ref.vcodec:
            reasons.append(f"影片編碼不一致 ({video.path.name} 為 {video.vcodec})")
            break

    for video in videos[1:]:
        if video.pix_fmt != ref.pix_fmt:
            reasons.append(f"像素格式不一致 ({video.path.name} 為 {video.pix_fmt})")
            break

    for video in videos[1:]:
        if video.fps_num != ref.fps_num or video.fps_den != ref.fps_den:
            reasons.append(f"幀率不一致 ({video.path.name} 為 {video.fps_label} fps)")
            break

    has_audio = [video.has_audio for video in videos]
    if any(has_audio) and not all(has_audio):
        reasons.append("音訊不一致（部分片段有聲、部分無聲）")
    elif all(has_audio):
        for video in videos[1:]:
            if video.acodec != ref.acodec:
                reasons.append(f"音訊編碼不一致 ({video.path.name} 為 {video.acodec})")
                break
        for video in videos[1:]:
            if video.sample_rate != ref.sample_rate:
                reasons.append(f"取樣率不一致 ({video.path.name} 為 {video.sample_rate}Hz)")
                break
        for video in videos[1:]:
            if video.channels != ref.channels:
                reasons.append(f"聲道數不一致 ({video.path.name} 為 {video.channels} 聲道)")
                break

    unique_reasons = list(dict.fromkeys(reasons))
    return CompatResult(copy_ok=len(unique_reasons) == 0, reasons=unique_reasons)
