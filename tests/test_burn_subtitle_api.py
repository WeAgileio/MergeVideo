"""burn-subtitle API 與 Worker。"""

from __future__ import annotations

import json

from api.config import reset_settings_cache
from api.db import session_scope
from api.models import JobRecord
from conftest import make_video, requires_ffmpeg, run_worker, upload_video

MINIMAL_SRT = "1\n00:00:00,000 --> 00:00:00,800\n你好\n"


def _upload_srt(client, headers: dict, filename: str, content: str) -> dict:
    response = client.post(
        "/v1/files",
        headers=headers,
        files={"file": (filename, content.encode("utf-8"), "application/x-subrip")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_srt_success(client, auth_a):
    uploaded = _upload_srt(client, auth_a, "talk.srt", MINIMAL_SRT)
    assert uploaded["content_type"] == "application/x-subrip"
    assert uploaded["filename"] == "talk.srt"


def test_upload_txt_still_rejected(client, auth_a):
    response = client.post(
        "/v1/files",
        headers=auth_a,
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_burn_subtitle_unauthorized(client):
    response = client.post(
        "/v1/jobs/burn-subtitle",
        json={"file_id": "f_any", "srt_file_id": "f_srt"},
    )
    assert response.status_code == 401


def test_burn_subtitle_invalid_font_size(client, auth_a):
    response = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_a,
        json={"file_id": "f_any", "srt_file_id": "f_srt", "font_size": 0},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FONT_SIZE"


def test_burn_subtitle_invalid_margin_unit(client, auth_a):
    response = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_a,
        json={
            "file_id": "f_any",
            "srt_file_id": "f_srt",
            "margin_unit": "em",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MARGIN"


def test_burn_subtitle_invalid_percent(client, auth_a):
    response = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_a,
        json={
            "file_id": "f_any",
            "srt_file_id": "f_srt",
            "margin_bottom": 120,
            "margin_unit": "percent",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_MARGIN"


@requires_ffmpeg
def test_burn_subtitle_wrong_file_type(client, auth_a, video_dir):
    clip = make_video(video_dir / "burn_wrong.mp4")
    video = upload_video(client, auth_a, clip)
    srt = _upload_srt(client, auth_a, "ok.srt", MINIMAL_SRT)

    swapped = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_a,
        json={"file_id": srt["file_id"], "srt_file_id": video["file_id"]},
    )
    assert swapped.status_code == 400
    assert swapped.json()["error"]["code"] == "WRONG_FILE_TYPE"


@requires_ffmpeg
def test_burn_subtitle_other_owners_file(client, auth_a, auth_b, video_dir):
    clip = make_video(video_dir / "burn_owner.mp4")
    video = upload_video(client, auth_a, clip)
    srt = _upload_srt(client, auth_a, "owner.srt", MINIMAL_SRT)
    response = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_b,
        json={"file_id": video["file_id"], "srt_file_id": srt["file_id"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED_FILE"


@requires_ffmpeg
def test_burn_subtitle_defaults_and_success(client, auth_a, video_dir):
    clip = make_video(video_dir / "talk.mp4", duration=1.0)
    video = upload_video(client, auth_a, clip)
    srt = _upload_srt(client, auth_a, "talk.srt", MINIMAL_SRT)

    response = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_a,
        json={"file_id": video["file_id"], "srt_file_id": srt["file_id"]},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["type"] == "burn_subtitle"

    with session_scope() as session:
        record = session.get(JobRecord, job["job_id"])
        payload = json.loads(record.input_json)
        assert payload["font_size"] == 48
        assert payload["margin_bottom"] == 6
        assert payload["margin_unit"] == "percent"

    assert run_worker() >= 1
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "done", body
    assert body["progress"] == 100
    result = body["result"]
    assert result["filename"] == "talk_burned.mp4"
    assert result["content_type"] == "video/mp4"
    assert "file_id" not in result
    download = client.get(result["download_url"])
    assert download.status_code == 200
    assert len(download.content) > 100


@requires_ffmpeg
def test_burn_subtitle_invalid_srt(client, auth_a, video_dir):
    clip = make_video(video_dir / "burn_badsrt.mp4")
    video = upload_video(client, auth_a, clip)
    srt = _upload_srt(client, auth_a, "bad.srt", "this is not cues\n")
    job = client.post(
        "/v1/jobs/burn-subtitle",
        headers=auth_a,
        json={"file_id": video["file_id"], "srt_file_id": srt["file_id"]},
    ).json()
    run_worker()
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "INVALID_SRT"


@requires_ffmpeg
def test_burn_subtitle_font_unavailable(client, auth_a, video_dir, monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTITLE_FONT_PATH", str(tmp_path / "no-such.ttf"))
    reset_settings_cache()
    try:
        clip = make_video(video_dir / "burn_nofont.mp4")
        video = upload_video(client, auth_a, clip)
        srt = _upload_srt(client, auth_a, "font.srt", MINIMAL_SRT)
        job = client.post(
            "/v1/jobs/burn-subtitle",
            headers=auth_a,
            json={"file_id": video["file_id"], "srt_file_id": srt["file_id"]},
        ).json()
        run_worker()
        body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
        assert body["status"] == "failed"
        assert body["error"]["code"] == "FONT_UNAVAILABLE"
    finally:
        monkeypatch.delenv("SUBTITLE_FONT_PATH", raising=False)
        reset_settings_cache()


def test_openapi_has_burn_subtitle(client):
    spec = client.app.openapi()
    assert "/v1/jobs/burn-subtitle" in spec["paths"]
