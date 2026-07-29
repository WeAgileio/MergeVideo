"""整合測試：upload → job → worker → poll → download URL。"""

from __future__ import annotations

from conftest import make_video, requires_ffmpeg, run_worker, upload_video


@requires_ffmpeg
def test_upload_merge_poll_download(client, auth_a, video_dir):
    clip1 = make_video(video_dir / "m1.mp4", color="red")
    clip2 = make_video(video_dir / "m2.mp4", color="blue")

    file1 = upload_video(client, auth_a, clip1)
    file2 = upload_video(client, auth_a, clip2)
    assert file1["file_id"] != file2["file_id"]
    assert file1["metadata"]["width"] == 320

    response = client.post(
        "/v1/jobs/merge",
        headers=auth_a,
        json={"file_ids": [file1["file_id"], file2["file_id"]]},
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "queued"

    assert run_worker() >= 1

    response = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done", body
    assert body["progress"] == 100
    result = body["result"]
    assert result["filename"] == "merged.mp4"
    assert result["content_type"] == "video/mp4"
    assert result["size_bytes"] > 0

    download = client.get(result["download_url"])
    assert download.status_code == 200
    assert len(download.content) == result["size_bytes"]


@requires_ffmpeg
def test_merge_incompatible_uses_encode(client, auth_a, video_dir):
    small = make_video(video_dir / "e1.mp4", width=160, height=120, color="green")
    large = make_video(video_dir / "e2.mp4", width=320, height=240, color="yellow")

    file1 = upload_video(client, auth_a, small)
    file2 = upload_video(client, auth_a, large)

    response = client.post(
        "/v1/jobs/merge",
        headers=auth_a,
        json={"file_ids": [file1["file_id"], file2["file_id"]]},
    )
    job_id = response.json()["job_id"]
    run_worker()

    body = client.get(f"/v1/jobs/{job_id}", headers=auth_a).json()
    assert body["status"] == "done", body


@requires_ffmpeg
def test_extract_first_and_last_frame(client, auth_a, video_dir):
    clip = make_video(video_dir / "x1.mp4", color="purple")
    uploaded = upload_video(client, auth_a, clip)

    first = client.post(
        "/v1/jobs/extract-first-frame",
        headers=auth_a,
        json={"file_id": uploaded["file_id"]},
    ).json()
    last = client.post(
        "/v1/jobs/extract-last-frame",
        headers=auth_a,
        json={"file_id": uploaded["file_id"]},
    ).json()

    run_worker()

    first_body = client.get(f"/v1/jobs/{first['job_id']}", headers=auth_a).json()
    last_body = client.get(f"/v1/jobs/{last['job_id']}", headers=auth_a).json()

    assert first_body["status"] == "done", first_body
    assert first_body["result"]["filename"].endswith("_FirstFrame.png")
    assert first_body["result"]["content_type"] == "image/png"

    assert last_body["status"] == "done", last_body
    assert last_body["result"]["filename"].endswith("_LastFrame.png")

    download = client.get(first_body["result"]["download_url"])
    assert download.status_code == 200
    assert download.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "ffmpeg" in body and "ffprobe" in body
