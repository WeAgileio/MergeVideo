#!/usr/bin/env python3
"""合併資料夾內數字序影片為單一 MP4。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from compat import check_copy_compat  # noqa: E402
from ffmpeg_utils import FFmpegError, die, require_tools  # noqa: E402
from merger import merge_copy, merge_encode, resolve_output_path  # noqa: E402
from probe import pick_output_size, probe_all  # noqa: E402
from report import print_report  # noqa: E402
from scanner import ScanError, scan_folder  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mergevideo",
        description="合併資料夾內數字序影片（1.mp4, 2.mp4...）為單一 MP4",
    )
    parser.add_argument("input_folder", help="包含數字序影片的資料夾")
    parser.add_argument("-o", "--output", type=Path, help="自訂輸出檔案路徑")
    parser.add_argument(
        "--mode",
        choices=("auto", "copy", "encode"),
        help="合併模式：auto=自動判斷, copy=串接不編碼, encode=重新編碼",
    )
    parser.add_argument("--crf", type=int, default=18, help="Encode 模式影片品質（預設 18）")
    parser.add_argument("--dry-run", action="store_true", help="只分析報告，不合併")
    return parser


def prompt_mode(copy_ok: bool) -> str:
    if copy_ok:
        prompt = "\n請選擇 [C]opy (推薦) / [E]ncode / [Q]uit: "
    else:
        prompt = "\n請選擇 [E]ncode / [Q]uit: "

    while True:
        choice = input(prompt).strip().lower()
        if choice in {"q", "quit"}:
            print("已取消。")
            raise SystemExit(0)
        if choice in {"e", "encode"}:
            return "encode"
        if choice in {"c", "copy"}:
            if copy_ok:
                return "copy"
            print("Copy 模式不可用，請選擇 Encode 或 Quit。")
            continue
        print("無效選項，請重新輸入。")


def resolve_mode(args: argparse.Namespace, copy_ok: bool) -> str:
    if args.mode == "auto":
        return "copy" if copy_ok else "encode"
    if args.mode == "copy":
        if not copy_ok:
            die("Copy 模式不可用，片段格式不一致。請改用 --mode encode。")
        return "copy"
    if args.mode == "encode":
        return "encode"
    return prompt_mode(copy_ok)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_folder = Path(args.input_folder).expanduser().resolve()

    try:
        require_tools()
        paths = scan_folder(input_folder)
        videos = probe_all(paths)
        output_width, output_height, reference = pick_output_size(videos)
        compat = check_copy_compat(videos)

        print_report(
            input_folder=str(input_folder),
            videos=videos,
            output_width=output_width,
            output_height=output_height,
            reference=reference,
            compat=compat,
        )

        if args.dry_run:
            print("\n（dry-run 模式，未執行合併）")
            return 0

        sys.stdout.flush()
        mode = resolve_mode(args, compat.copy_ok)
        output_path = resolve_output_path(input_folder, args.output)

        print(f"\n使用 {mode.upper()} 模式合併中...")
        if mode == "copy":
            merge_copy(videos, output_path)
        else:
            merge_encode(
                videos,
                output_path,
                width=output_width,
                height=output_height,
                fps=reference.fps_float,
                crf=args.crf,
            )

        print(f"\n完成！輸出: {output_path}")
        return 0

    except ScanError as exc:
        die(str(exc))
    except FFmpegError as exc:
        die(str(exc))
    except KeyboardInterrupt:
        print("\n已取消。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
