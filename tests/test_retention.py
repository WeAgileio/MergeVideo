"""保留策略與背景清理測試。"""

from __future__ import annotations

import datetime

import pytest

from api.config import reset_settings_cache
from api.db import session_scope
from api.models import FileRecord, JobRecord, JobStatus
from api.services.cleanup import cleanup_expired
from api.services.storage import get_storage
from conftest import make_video, requires_ffmpeg, run_worker, upload_video


@requires_ffmpeg
def test_upload_no_expiry_by_default(client, auth_a, video_dir):
    clip = make_video(video_dir / "keep.mp4")
    uploaded = upload_video(client, auth_a, clip)
    assert uploaded["expires_at"] is None

    response = client.get(f"/v1/files/{uploaded['file_id']}", headers=auth_a)
    assert response.status_code == 200
    assert response.json()["expires_at"] is None


@requires_ffmpeg
def test_past_expires_at_still_rejected(client, auth_a, video_dir):
    clip = make_video(video_dir / "past.mp4")
    uploaded = upload_video(client, auth_a, clip)

    with session_scope() as session:
        record = session.get(FileRecord, uploaded["file_id"])
        record.expires_at = datetime.datetime(2020, 1, 1)
        session.commit()

    response = client.post(
        "/v1/jobs/extract-first-frame",
        headers=auth_a,
        json={"file_id": uploaded["file_id"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FILE_NOT_FOUND"


@requires_ffmpeg
def test_cleanup_disabled_keeps_expired_file(client, auth_a, video_dir, monkeypatch):
    monkeypatch.setenv("FILE_TTL_HOURS", "24")
    monkeypatch.setenv("AUTO_CLEANUP_ENABLED", "false")
    reset_settings_cache()

    clip = make_video(video_dir / "noclean.mp4")
    uploaded = upload_video(client, auth_a, clip)

    with session_scope() as session:
        record = session.get(FileRecord, uploaded["file_id"])
        record.expires_at = datetime.datetime(2020, 1, 1)
        session.commit()

    with session_scope() as session:
        removed = cleanup_expired(session, get_storage())
        assert removed == 0
        assert session.get(FileRecord, uploaded["file_id"]) is not None


@requires_ffmpeg
def test_cleanup_removes_expired_upload_when_enabled(
    client, auth_a, video_dir, monkeypatch
):
    monkeypatch.setenv("FILE_TTL_HOURS", "24")
    monkeypatch.setenv("AUTO_CLEANUP_ENABLED", "true")
    reset_settings_cache()

    clip = make_video(video_dir / "cleanme.mp4")
    uploaded = upload_video(client, auth_a, clip)

    with session_scope() as session:
        record = session.get(FileRecord, uploaded["file_id"])
        record.expires_at = datetime.datetime(2020, 1, 1)
        session.commit()

    with session_scope() as session:
        removed = cleanup_expired(session, get_storage())
        assert removed >= 1
        assert session.get(FileRecord, uploaded["file_id"]) is None


@requires_ffmpeg
def test_merge_result_retained_by_default(client, auth_a, video_dir):
    clip1 = make_video(video_dir / "r1.mp4", color="red")
    clip2 = make_video(video_dir / "r2.mp4", color="blue")
    file1 = upload_video(client, auth_a, clip1)
    file2 = upload_video(client, auth_a, clip2)

    job = client.post(
        "/v1/jobs/merge",
        headers=auth_a,
        json={"file_ids": [file1["file_id"], file2["file_id"]]},
    ).json()
    run_worker()

    with session_scope() as session:
        record = session.get(JobRecord, job["job_id"])
        record.completed_at = datetime.datetime(2020, 1, 1)
        session.commit()

    with session_scope() as session:
        removed = cleanup_expired(session, get_storage())
        assert removed == 0

    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "done"
    assert body["result"]["download_url"]


@requires_ffmpeg
def test_merge_result_cleaned_when_enabled(client, auth_a, video_dir, monkeypatch):
    monkeypatch.setenv("RESULT_TTL_HOURS", "72")
    monkeypatch.setenv("AUTO_CLEANUP_ENABLED", "true")
    reset_settings_cache()

    clip1 = make_video(video_dir / "c1.mp4", color="red")
    clip2 = make_video(video_dir / "c2.mp4", color="blue")
    file1 = upload_video(client, auth_a, clip1)
    file2 = upload_video(client, auth_a, clip2)

    job = client.post(
        "/v1/jobs/merge",
        headers=auth_a,
        json={"file_ids": [file1["file_id"], file2["file_id"]]},
    ).json()
    run_worker()

    with session_scope() as session:
        record = session.get(JobRecord, job["job_id"])
        record.completed_at = datetime.datetime(2020, 1, 1)
        session.commit()

    with session_scope() as session:
        removed = cleanup_expired(session, get_storage())
        assert removed >= 1
        record = session.get(JobRecord, job["job_id"])
        assert record is not None
        assert record.result_json is None

    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "done"
    assert body.get("result") is None
