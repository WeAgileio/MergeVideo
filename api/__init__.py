"""MergeVideo HTTP API。"""

from __future__ import annotations

import sys
from pathlib import Path

# 核心 FFmpeg 模組（merger、probe 等）位於 repo 根目錄，確保可被 import
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
