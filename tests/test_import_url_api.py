"""整合測試：import-url job。"""

from __future__ import annotations

import shutil

from api.services.url_import import UrlImportError
from conftest import make_video, requires_ffmpeg, run_worker, upload_video


@requires_ffmpeg
def test_import_url_then_merge(client, auth_a, video_dir, monkeypatch):
    remote = make_video(video_dir / "remote.mp4", color="orange")
    local = make_video(video_dir / "local.mp4", color="cyan")

    def fake_download(url, dest, **kwargs):
        shutil.copy(remote, dest)

    monkeypatch.setattr("api.worker.runner.download_url_to_file", fake_download)

    response = client.post(
        "/v1/jobs/import-url",
        headers=auth_a,
        json={"url": "https://cdn.example.com/remote.mp4", "filename": "remote.mp4"},
    )
    assert response.status_code == 202, response.text
    import_job = response.json()
    assert import_job["type"] == "import_url"

    uploaded = upload_video(client, auth_a, local)

    assert run_worker() >= 1

    body = client.get(f"/v1/jobs/{import_job['job_id']}", headers=auth_a).json()
    assert body["status"] == "done", body
    imported_file_id = body["result"]["file_id"]

    merge_resp = client.post(
        "/v1/jobs/merge",
        headers=auth_a,
        json={"file_ids": [imported_file_id, uploaded["file_id"]]},
    )
    assert merge_resp.status_code == 202
    merge_job_id = merge_resp.json()["job_id"]
    run_worker()

    merge_body = client.get(f"/v1/jobs/{merge_job_id}", headers=auth_a).json()
    assert merge_body["status"] == "done", merge_body


def test_import_url_rejects_http_by_default(client, auth_a):
    response = client.post(
        "/v1/jobs/import-url",
        headers=auth_a,
        json={"url": "http://example.com/video.mp4"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_URL"


@requires_ffmpeg
def test_import_url_unsupported_format(client, auth_a, video_dir, monkeypatch):
    text_file = video_dir / "bad.txt"
    text_file.write_text("not a video", encoding="utf-8")

    def fake_download(url, dest, **kwargs):
        shutil.copy(text_file, dest)

    monkeypatch.setattr("api.worker.runner.download_url_to_file", fake_download)

    job = client.post(
        "/v1/jobs/import-url",
        headers=auth_a,
        json={"url": "https://cdn.example.com/bad.txt", "filename": "bad.txt"},
    ).json()
    run_worker()

    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "UNSUPPORTED_FORMAT"


@requires_ffmpeg
def test_import_url_file_too_large(client, auth_a, monkeypatch):
    def fake_download(url, dest, **kwargs):
        raise UrlImportError("FILE_TOO_LARGE", "檔案超過大小上限 10 MB")

    monkeypatch.setattr("api.worker.runner.download_url_to_file", fake_download)

    job = client.post(
        "/v1/jobs/import-url",
        headers=auth_a,
        json={"url": "https://cdn.example.com/huge.mp4"},
    ).json()
    run_worker()

    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "FILE_TOO_LARGE"
