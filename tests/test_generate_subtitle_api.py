"""generate-subtitle API 與 Worker（mock fa-zh）。"""

from __future__ import annotations

from api.config import reset_settings_cache
from api.services.funasr_align import FunasrUnavailable
from conftest import make_video, requires_ffmpeg, run_worker, upload_video


class _FakeAlignModel:
    def __init__(self, timestamps: list[list[int]] | None = None, error: Exception | None = None):
        self.timestamps = timestamps or []
        self.error = error

    def generate(self, **kwargs):
        if self.error is not None:
            raise self.error
        return [{"timestamp": self.timestamps}]


def test_generate_subtitle_missing_script(client, auth_a):
    response = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_a,
        json={"file_id": "f_any"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SCRIPT_REQUIRED"


def test_generate_subtitle_blank_script(client, auth_a):
    response = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_a,
        json={"file_id": "f_any", "script": "   "},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "SCRIPT_EMPTY"


def test_generate_subtitle_too_long(client, auth_a, monkeypatch):
    monkeypatch.setenv("FUNASR_MAX_SCRIPT_CHARS", "8")
    reset_settings_cache()
    try:
        response = client.post(
            "/v1/jobs/generate-subtitle",
            headers=auth_a,
            json={"file_id": "f_any", "script": "123456789"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "SCRIPT_TOO_LONG"
    finally:
        monkeypatch.delenv("FUNASR_MAX_SCRIPT_CHARS", raising=False)
        reset_settings_cache()


def test_generate_subtitle_unauthorized(client):
    response = client.post(
        "/v1/jobs/generate-subtitle",
        json={"file_id": "f_any", "script": "你好。"},
    )
    assert response.status_code == 401


@requires_ffmpeg
def test_generate_subtitle_other_owners_file(client, auth_a, auth_b, video_dir):
    clip = make_video(video_dir / "sub_owner.mp4")
    uploaded = upload_video(client, auth_a, clip)
    response = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_b,
        json={"file_id": uploaded["file_id"], "script": "你好。"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED_FILE"


@requires_ffmpeg
def test_generate_subtitle_success(client, auth_a, video_dir, monkeypatch):
    script = "你好。世界。"
    timestamps = [[i * 100, i * 100 + 90] for i in range(6)]
    monkeypatch.setattr(
        "api.worker.runner.get_align_model",
        lambda: _FakeAlignModel(timestamps),
    )

    clip = make_video(video_dir / "talk.mp4")
    uploaded = upload_video(client, auth_a, clip)
    response = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_a,
        json={"file_id": uploaded["file_id"], "script": script},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["type"] == "generate_subtitle"
    assert job["status"] == "queued"

    assert run_worker() >= 1

    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "done", body
    assert body["progress"] == 100
    result = body["result"]
    assert result["filename"] == "talk.srt"
    assert result["content_type"] == "application/x-subrip"
    assert result["size_bytes"] > 0
    assert result["file_id"]

    file_meta = client.get(f"/v1/files/{result['file_id']}", headers=auth_a)
    assert file_meta.status_code == 200, file_meta.text
    assert file_meta.json()["content_type"] == "application/x-subrip"
    assert file_meta.json()["filename"] == "talk.srt"

    download = client.get(result["download_url"])
    assert download.status_code == 200
    text = download.content.decode("utf-8")
    assert text.startswith("1\n")
    assert "你好。" in text
    assert "世界。" in text
    assert "Speaker" not in text


@requires_ffmpeg
def test_generate_subtitle_no_audio(client, auth_a, video_dir, monkeypatch):
    monkeypatch.setattr(
        "api.worker.runner.get_align_model",
        lambda: _FakeAlignModel([[0, 100]]),
    )
    clip = make_video(video_dir / "silent.mp4", audio=False)
    uploaded = upload_video(client, auth_a, clip)
    job = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_a,
        json={"file_id": uploaded["file_id"], "script": "你好。"},
    ).json()
    run_worker()
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "NO_AUDIO_STREAM"


@requires_ffmpeg
def test_generate_subtitle_empty_timestamps(client, auth_a, video_dir, monkeypatch):
    monkeypatch.setattr(
        "api.worker.runner.get_align_model",
        lambda: _FakeAlignModel([]),
    )
    clip = make_video(video_dir / "empty_ts.mp4")
    uploaded = upload_video(client, auth_a, clip)
    job = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_a,
        json={"file_id": uploaded["file_id"], "script": "你好。"},
    ).json()
    run_worker()
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "ALIGN_FAILED"


@requires_ffmpeg
def test_generate_subtitle_funasr_unavailable(client, auth_a, video_dir, monkeypatch):
    def boom():
        raise FunasrUnavailable("FunASR 未安裝")

    monkeypatch.setattr("api.worker.runner.get_align_model", boom)
    clip = make_video(video_dir / "no_model.mp4")
    uploaded = upload_video(client, auth_a, clip)
    job = client.post(
        "/v1/jobs/generate-subtitle",
        headers=auth_a,
        json={"file_id": uploaded["file_id"], "script": "你好。"},
    ).json()
    run_worker()
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "FUNASR_UNAVAILABLE"


def test_openapi_has_generate_subtitle(client):
    spec = client.app.openapi()
    assert "/v1/jobs/generate-subtitle" in spec["paths"]
