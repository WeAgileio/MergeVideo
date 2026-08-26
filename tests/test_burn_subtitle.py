"""燒字幕：margin 計算、SRT 解析。"""

from api.services.burn_subtitle import compute_margin_v, parse_srt_cues, srt_has_cues


def test_compute_margin_v_percent_vertical():
    assert compute_margin_v(1920, 6, "percent") == 115


def test_compute_margin_v_percent_horizontal():
    assert compute_margin_v(1080, 6, "percent") == 65


def test_compute_margin_v_px():
    assert compute_margin_v(1080, 80, "px") == 80


def test_srt_has_cues():
    text = "1\n00:00:00,000 --> 00:00:01,000\n你好\n"
    assert srt_has_cues(text) is True
    assert srt_has_cues("not a subtitle") is False
    assert srt_has_cues("") is False


def test_parse_srt_cues():
    cues = parse_srt_cues("1\n00:00:00,000 --> 00:00:00,800\n你好\n")
    assert len(cues) == 1
    assert cues[0][0] == 0.0
    assert cues[0][1] == 0.8
    assert cues[0][2] == "你好"
