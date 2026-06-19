"""分析報告輸出。"""

from __future__ import annotations

from compat import CompatResult
from probe import VideoInfo


def print_report(
    *,
    input_folder: str,
    videos: list[VideoInfo],
    output_width: int,
    output_height: int,
    reference: VideoInfo,
    compat: CompatResult,
) -> None:
    print(f"\n掃描資料夾: {input_folder}")
    print(f"找到 {len(videos)} 個影片（自然排序）\n")
    print(f" {'#':>2}  {'檔名':<16} {'解析度':<12} {'FPS':>5}  {'編碼':<8} {'音訊'}")
    print("─" * 62)

    for index, video in enumerate(videos, start=1):
        resolution = f"{video.width}×{video.height}"
        print(
            f" {index:>2}  {video.path.name:<16} {resolution:<12} "
            f"{video.fps_label:>5}  {video.vcodec:<8} {video.audio_label}"
        )

    print(f"\n輸出解析度: {output_width}×{output_height}（來自 {reference.path.name}，最大面積）")
    print("\n相容性分析:")
    if compat.copy_ok:
        print("  ✓ 全部一致")
        print("\nCopy 模式: 可用（快速，無重新編碼）")
    else:
        for reason in compat.reasons:
            print(f"  ✗ {reason}")
        print("\nCopy 模式: 不可用")
    print("Encode 模式: 可用（重新編碼，較慢但穩）")
