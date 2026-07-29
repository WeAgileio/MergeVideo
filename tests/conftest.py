"""測試環境：local storage + SQLite + 無 Redis（DB 輪詢）。

環境變數必須在 import api.* 之前設定。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="mergevideo_api_test_"))

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_ROOT}/api.db"
os.environ["REDIS_URL"] = ""
os.environ["STORAGE_BACKEND"] = "local"
os.environ["LOCAL_STORAGE_DIR"] = str(_TEST_ROOT / "storage")
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
os.environ["API_KEYS"] = "test-key-a,test-key-b"
os.environ["MAX_FILE_SIZE_MB"] = "10"
os.environ["MAX_MERGE_FILES"] = "10"

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FFMPEG_AVAILABLE = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

requires_ffmpeg = pytest.mark.skipif(not FFMPEG_AVAILABLE, reason="需要 ffmpeg/ffprobe")


def make_video(
    path: Path,
    *,
    width: int = 320,
    height: int = 240,
    fps: int = 24,
    duration: float = 1.0,
    audio: bool = True,
    color: str = "red",
) -> Path:
    args = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={width}x{height}:r={fps}:d={duration}",
    ]
    if audio:
        args += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-c:a",
            "aac",
            "-shortest",
        ]
    args += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(args, check=True, capture_output=True)
    return path


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from api.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_a() -> dict:
    return {"Authorization": "Bearer test-key-a"}


@pytest.fixture()
def auth_b() -> dict:
    return {"Authorization": "Bearer test-key-b"}


@pytest.fixture(scope="session")
def video_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("videos")


def upload_video(client, headers: dict, path: Path) -> dict:
    with path.open("rb") as handle:
        response = client.post(
            "/v1/files",
            headers=headers,
            files={"file": (path.name, handle, "video/mp4")},
        )
    assert response.status_code == 201, response.text
    return response.json()


def run_worker() -> int:
    from api.worker.runner import process_pending_jobs

    return process_pending_jobs()
