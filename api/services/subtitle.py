"""有稿字幕：標點分句、字級時間戳 → 標準 SRT。不依賴 FunASR。"""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；;，])")


class SubtitleJobError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def split_sentences(script: str) -> list[str]:
    """以 。！？!?；;， 分句，標點留在該句末；不斷英文逗號（避免 1,000）。"""
    text = script.strip()
    if not text:
        return []
    return [part for part in _SENTENCE_SPLIT.split(text) if part]
    text = script.strip()
    if not text:
        return []
    return [part for part in _SENTENCE_SPLIT.split(text) if part]


def ms_to_srt_time(ms: int) -> str:
    if ms < 0:
        ms = 0
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _char_count(text: str) -> int:
    return sum(1 for ch in text if ch not in "\n\r")


def _allocate_counts(weights: list[int], total: int) -> list[int]:
    """依權重把 total 個時間戳分給各句。句數 ≤ 時間戳數時每句至少 1 個。"""
    n = len(weights)
    if n == 0 or total <= 0:
        return [0] * n
    positive = [max(w, 1) for w in weights]
    if total >= n:
        rest = total - n
        base = [1] * n
        if rest == 0:
            return base
        extra = _largest_remainder(positive, rest)
        return [b + e for b, e in zip(base, extra)]
    return _largest_remainder(positive, total)


def _largest_remainder(weights: list[int], total: int) -> list[int]:
    weight_sum = sum(weights)
    if weight_sum <= 0 or total <= 0:
        return [0] * len(weights)
    raw = [total * w / weight_sum for w in weights]
    floors = [int(x) for x in raw]
    leftover = total - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda i: (raw[i] - floors[i], -i),
        reverse=True,
    )
    for i in order[:leftover]:
        floors[i] += 1
    return floors


def cues_from_alignment(
    script: str, timestamps: list[list[int]]
) -> list[tuple[int, int, str]]:
    """依各句字數比例分配 timestamp，回 (start_ms, end_ms, text)。

    fa-zh 時間戳數量常少於 Unicode 字數（英文、數字常被收成一個 token）。
    不可用「一句吃掉 len(sentence) 個 stamp」否則後面的句子會被丟掉。
    """
    if not timestamps:
        raise SubtitleJobError("ALIGN_FAILED", "對齊未產生時間戳")

    sentences = split_sentences(script)
    if not sentences:
        raise SubtitleJobError("ALIGN_FAILED", "對齊未產生時間戳")

    counts = _allocate_counts([_char_count(s) for s in sentences], len(timestamps))
    index = 0
    cues: list[tuple[int, int, str]] = []
    for sentence, n in zip(sentences, counts):
        text = sentence.strip()
        if not text:
            index += n
            continue
        slice_ts = timestamps[index : index + n]
        index += n
        if not slice_ts:
            if cues:
                start, end, prev = cues[-1]
                cues[-1] = (start, end, f"{prev}{text}")
            continue
        start = int(slice_ts[0][0])
        end = int(slice_ts[-1][1])
        if end < start:
            end = start
        cues.append((start, end, text))

    if not cues:
        raise SubtitleJobError("ALIGN_FAILED", "對齊未產生時間戳")
    return cues


def format_srt(cues: list[tuple[int, int, str]]) -> str:
    """UTF-8 標準 SRT（無 BOM、無 Speaker 前綴）。"""
    blocks: list[str] = []
    for index, (start, end, text) in enumerate(cues, start=1):
        blocks.append(
            f"{index}\n{ms_to_srt_time(start)} --> {ms_to_srt_time(end)}\n{text}"
        )
    return "\n\n".join(blocks) + "\n"


def parse_timestamps(result: object) -> list[list[int]]:
    """從 FunASR generate() 回傳值取出 [[start_ms, end_ms], ...]。"""
    if not result:
        return []
    first = result[0] if isinstance(result, list) else result
    if not isinstance(first, dict):
        return []
    raw = first.get("timestamp") or first.get("timestamps") or []
    out: list[list[int]] = []
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append([int(item[0]), int(item[1])])
    return out
