"""錯誤情境測試：過大檔案、非 owner、過期 file、驗證錯誤。"""

from __future__ import annotations

import datetime
import io

from conftest import make_video, requires_ffmpeg, upload_video


def test_missing_api_key(client):
    response = client.get("/v1/files/f_nonexistent")
    assert response.status_code == 401


def test_invalid_api_key(client):
    response = client.get(
        "/v1/files/f_nonexistent", headers={"Authorization": "Bearer wrong-key"}
    )
    assert response.status_code == 401


def test_file_too_large(client, auth_a):
    # 測試環境上限 10MB，上傳 11MB
    blob = io.BytesIO(b"\x00" * (11 * 1024 * 1024))
    response = client.post(
        "/v1/files", headers=auth_a, files={"file": ("big.mp4", blob, "video/mp4")}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_unsupported_format(client, auth_a):
    response = client.post(
        "/v1/files",
        headers=auth_a,
        files={"file": ("note.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_insufficient_files_for_merge(client, auth_a):
    response = client.post(
        "/v1/jobs/merge", headers=auth_a, json={"file_ids": ["f_only_one"]}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INSUFFICIENT_FILES"


def test_merge_with_unknown_file(client, auth_a):
    response = client.post(
        "/v1/jobs/merge", headers=auth_a, json={"file_ids": ["f_ghost1", "f_ghost2"]}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FILE_NOT_FOUND"


def test_job_not_found(client, auth_a):
    response = client.get("/v1/jobs/j_nonexistent", headers=auth_a)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "JOB_NOT_FOUND"


@requires_ffmpeg
def test_non_owner_cannot_use_file(client, auth_a, auth_b, video_dir):
    clip = make_video(video_dir / "owner.mp4")
    uploaded = upload_video(client, auth_a, clip)

    # 非 owner 建 job → 403
    response = client.post(
        "/v1/jobs/extract-first-frame",
        headers=auth_b,
        json={"file_id": uploaded["file_id"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED_FILE"

    # 非 owner 查 metadata → 404（不洩漏存在性）
    response = client.get(f"/v1/files/{uploaded['file_id']}", headers=auth_b)
    assert response.status_code == 404


@requires_ffmpeg
def test_expired_file_rejected(client, auth_a, video_dir):
    clip = make_video(video_dir / "expiring.mp4")
    uploaded = upload_video(client, auth_a, clip)

    # 將 expires_at 改為過去
    from api.db import session_scope
    from api.models import FileRecord

    with session_scope() as session:
        record = session.get(FileRecord, uploaded["file_id"])
        record.expires_at = record.expires_at - datetime.timedelta(days=30)
        session.commit()

    response = client.post(
        "/v1/jobs/extract-first-frame",
        headers=auth_a,
        json={"file_id": uploaded["file_id"]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "FILE_NOT_FOUND"


@requires_ffmpeg
def test_delete_file(client, auth_a, video_dir):
    clip = make_video(video_dir / "deleteme.mp4")
    uploaded = upload_video(client, auth_a, clip)

    response = client.delete(f"/v1/files/{uploaded['file_id']}", headers=auth_a)
    assert response.status_code == 204

    response = client.get(f"/v1/files/{uploaded['file_id']}", headers=auth_a)
    assert response.status_code == 404
