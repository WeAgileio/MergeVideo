"""字幕組裝單元測試（不載入 FunASR）。"""

from __future__ import annotations

import pytest

from api.services.subtitle import (
    SubtitleJobError,
    cues_from_alignment,
    format_srt,
    ms_to_srt_time,
    split_sentences,
)


def test_split_two_sentences():
    assert split_sentences("第一句。第二句。") == ["第一句。", "第二句。"]


def test_split_on_chinese_comma():
    assert split_sentences("甲，乙，丙。") == ["甲，", "乙，", "丙。"]


def test_split_metaplanet_news_copy():
    script = (
        "PANews 8月12日消息，據Lookonchain監測，Metaplanet在過去3小時內共轉出3881枚BTC"
        "（2.473億美元）。Metaplanet累計買入4.3萬枚BTC，均價96191美元，目前浮虧14億美元（-34%）"
    )
    parts = split_sentences(script)
    assert len(parts) == 6
    assert parts[0] == "PANews 8月12日消息，"
    assert parts[-1].endswith("（-34%）")
    assert "2.473" in "".join(parts)


def test_split_no_punctuation_is_one_sentence():
    assert split_sentences("沒有句號的稿") == ["沒有句號的稿"]


def test_ms_to_srt_time():
    assert ms_to_srt_time(100) == "00:00:00,100"
    assert ms_to_srt_time(400) == "00:00:00,400"
    assert ms_to_srt_time(3_661_234) == "01:01:01,234"


def test_two_cues_from_alignment():
    script = "第一句。第二句。"
    timestamps = [[i * 100, i * 100 + 90] for i in range(8)]
    cues = cues_from_alignment(script, timestamps)
    assert len(cues) == 2
    assert cues[0][2] == "第一句。"
    assert cues[1][2] == "第二句。"
    assert cues[0][0] == 0
    assert cues[0][1] == 390
    assert cues[1][0] == 400
    assert cues[1][1] == 790


def test_cue_uses_first_and_last_character_times():
    cues = cues_from_alignment("你好。", [[100, 200], [200, 350], [350, 400]])
    assert cues == [(100, 400, "你好。")]


def test_no_punctuation_single_cue():
    script = "沒有句號的稿"
    timestamps = [[i * 50, i * 50 + 40] for i in range(len(script))]
    cues = cues_from_alignment(script, timestamps)
    assert len(cues) == 1
    assert cues[0][2] == script
    assert cues[0][0] == 0
    assert cues[0][1] == (len(script) - 1) * 50 + 40


def test_fewer_timestamps_than_chars_keeps_later_sentences():
    """fa-zh 常回比字數少的 stamp；舊邏輯會讓第一句吃光、第二句消失。"""
    script = (
        "PANews 8月12日消息，據Lookonchain監測，Metaplanet在過去3小時內共轉出3881枚BTC"
        "（2.473億美元）。Metaplanet累計買入4.3萬枚BTC，均價96191美元，目前浮虧14億美元（-34%）"
    )
    # 少於第一句 69 字，模擬 token 級時間戳
    timestamps = [[5390 + i * 200, 5390 + i * 200 + 180] for i in range(50)]
    cues = cues_from_alignment(script, timestamps)
    texts = [c[2] for c in cues]
    assert len(cues) >= 6
    assert any("轉出3881枚BTC" in t for t in texts)
    assert any("浮虧14億美元" in t for t in texts)
    assert cues[0][0] == 5390
    assert cues[-1][1] == timestamps[-1][1]


def test_empty_timestamps_align_failed():
    with pytest.raises(SubtitleJobError) as exc:
        cues_from_alignment("你好。", [])
    assert exc.value.code == "ALIGN_FAILED"


def test_format_srt_no_speaker_prefix():
    srt = format_srt([(100, 400, "第一句。"), (400, 790, "第二句。")])
    assert srt.startswith("1\n")
    assert "00:00:00,100 --> 00:00:00,400" in srt
    assert "Speaker" not in srt
    assert "[spk]" not in srt
    assert srt.endswith("\n")
    assert "\ufeff" not in srt
    encoded = srt.encode("utf-8")
    assert not encoded.startswith(b"\xef\xbb\xbf")
    assert encoded.count(b"\n2\n") == 1
