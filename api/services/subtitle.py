"""有稿字幕：標點分句、對齊時間戳 → 標準 SRT。不依賴 FunASR。"""

from __future__ import annotations

import re
from pathlib import Path

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


def _visible_char_count(text: str) -> int:
    return sum(1 for ch in text if not ch.isspace())


def _alignment_units(text: str) -> list[str]:
    """fa-zh 常見切法：空白不佔 stamp；連續 ASCII 整串一個 token；其餘一字一個。"""
    units: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            units.append("".join(buf))
            buf.clear()

    for ch in text:
        if ch.isspace():
            flush()
            continue
        if ch.isascii():
            buf.append(ch)
        else:
            flush()
            units.append(ch)
    flush()
    return units


def _slice_weights(sentences: list[str], n_timestamps: int) -> list[int]:
    char_counts = [_char_count(s) for s in sentences]
    visible_counts = [_visible_char_count(s) for s in sentences]
    unit_counts = [len(_alignment_units(s)) for s in sentences]
    if n_timestamps == sum(char_counts):
        return char_counts
    if n_timestamps == sum(visible_counts):
        return visible_counts
    return unit_counts


def _allocate_counts(weights: list[int], total: int) -> list[int]:
    """依權重把 total 個時間戳分給各句。句數 ≤ 時間戳數時每句至少 1 個。"""
    n = len(weights)
    if n == 0 or total <= 0:
        return [0] * n
    if sum(weights) == total:
        return list(weights)
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
    """依各句對齊單位分配 timestamp，回 (start_ms, end_ms, text)。

    stamp 數等於字數時仍按字切（純中文 1:1）。否則按對齊單位：
    連續 ASCII（專名、數字）算一個 token，避免英文把後面的句子時間吃掉。
    """
    if not timestamps:
        raise SubtitleJobError("ALIGN_FAILED", "對齊未產生時間戳")

    sentences = split_sentences(script)
    if not sentences:
        raise SubtitleJobError("ALIGN_FAILED", "對齊未產生時間戳")

    counts = _allocate_counts(_slice_weights(sentences, len(timestamps)), len(timestamps))
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


_NOISE_DB = -35.0
_FRAME_MS = 50
_MIN_VOICED_MS = 200
_MAX_TRAILING_GAP_MS = 2000


def _voiced_frames(
    wav_path: Path,
    *,
    noise_db: float = _NOISE_DB,
    frame_ms: int = _FRAME_MS,
) -> tuple[int, list[bool]]:
    """回傳 (frame_ms, 每幀是否有語音)。"""
    import struct
    import wave

    with wave.open(str(wav_path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        n_frames = wav.getnframes()
        raw = wav.readframes(n_frames)
    if sample_width != 2 or channels < 1 or sample_rate <= 0 or n_frames <= 0:
        return frame_ms, []

    n_samples = n_frames * channels
    samples = struct.unpack("<" + "h" * n_samples, raw)
    if channels > 1:
        samples = [
            sum(samples[i : i + channels]) // channels
            for i in range(0, n_samples, channels)
        ]

    hop = max(int(sample_rate * frame_ms / 1000), 1)
    threshold = (10 ** (noise_db / 20.0)) * 32768.0
    voiced: list[bool] = []
    for i in range(0, len(samples), hop):
        chunk = samples[i : i + hop]
        rms = (sum(x * x for x in chunk) / len(chunk)) ** 0.5
        voiced.append(rms >= threshold)
    return frame_ms, voiced


def voiced_intervals_ms(
    wav_path: Path,
    *,
    noise_db: float = _NOISE_DB,
    frame_ms: int = _FRAME_MS,
    min_run_ms: int = _MIN_VOICED_MS,
) -> list[tuple[int, int]]:
    """從 16-bit PCM wav 找出語音區間（毫秒）。"""
    used_frame_ms, voiced = _voiced_frames(
        wav_path, noise_db=noise_db, frame_ms=frame_ms
    )
    intervals: list[tuple[int, int]] = []
    run_start: int | None = None
    for index, is_voiced in enumerate(voiced):
        if is_voiced and run_start is None:
            run_start = index
        elif not is_voiced and run_start is not None:
            start_ms = run_start * used_frame_ms
            end_ms = index * used_frame_ms
            if end_ms - start_ms >= min_run_ms:
                intervals.append((start_ms, end_ms))
            run_start = None
    if run_start is not None:
        start_ms = run_start * used_frame_ms
        end_ms = len(voiced) * used_frame_ms
        if end_ms - start_ms >= min_run_ms:
            intervals.append((start_ms, end_ms))
    return intervals


def extend_last_cue_to_speech(
    cues: list[tuple[int, int, str]],
    wav_path: Path,
    *,
    max_gap_ms: int = _MAX_TRAILING_GAP_MS,
) -> list[tuple[int, int, str]]:
    """若最後一句後面仍緊接著口播，把 end 延到該段語音結束。

    以幀為單位往後掃，允許中間最多 max_gap_ms 靜音（含句中換氣），
    避免 FunASR 最後一個 stamp 提早結束。
    """
    if not cues:
        return cues
    try:
        frame_ms, voiced = _voiced_frames(wav_path)
    except Exception:
        return cues
    if not voiced:
        return cues

    start, end, text = cues[-1]
    index = max(end // frame_ms, 0)
    last_voiced_ms = end
    silence_ms = 0
    for i in range(index, len(voiced)):
        if voiced[i]:
            last_voiced_ms = (i + 1) * frame_ms
            silence_ms = 0
        else:
            silence_ms += frame_ms
            if silence_ms > max_gap_ms:
                break
    if last_voiced_ms <= end:
        return cues
    return [*cues[:-1], (start, last_voiced_ms, text)]


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
