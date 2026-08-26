"""FunASR fa-zh lazy singleton。僅 Worker 呼叫；模組頂層不 import funasr。"""

from __future__ import annotations

import os

from api.config import get_settings
from api.services.subtitle import SubtitleJobError

_model = None


class FunasrUnavailable(SubtitleJobError):
    def __init__(self, message: str) -> None:
        super().__init__("FUNASR_UNAVAILABLE", message)


def get_align_model():
    """載入並快取 AutoModel('fa-zh')；失敗拋 FunasrUnavailable。"""
    global _model
    if _model is not None:
        return _model

    settings = get_settings()
    if settings.funasr_cache_dir is not None:
        cache = str(settings.funasr_cache_dir)
        os.environ.setdefault("MODELSCOPE_CACHE", cache)
        os.environ.setdefault("HF_HOME", cache)

    try:
        from funasr import AutoModel
    except ImportError as exc:
        raise FunasrUnavailable("FunASR 未安裝（Worker 需 pip install -r requirements-worker.txt）") from exc

    try:
        _model = AutoModel(model="fa-zh", device=settings.funasr_device)
    except Exception as exc:
        raise FunasrUnavailable(f"無法載入 fa-zh: {exc}") from exc
    return _model


def reset_align_model() -> None:
    """測試用。"""
    global _model
    _model = None
