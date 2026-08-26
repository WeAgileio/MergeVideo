"""replace-images 上傳、API 與 Worker。"""

from __future__ import annotations

import json
from pathlib import Path

from api.db import session_scope
from api.models import JobRecord
from conftest import make_video, requires_ffmpeg, run_worker, upload_video


def _make_image(path: Path, *, size=(100, 50), fmt: str = "PNG") -> Path:
    from PIL import Image

    Image.new("RGB", size, (0, 128, 255)).save(path, fmt)
    return path


def _upload_image(client, headers: dict, path: Path, content_type: str) -> dict:
    with path.open("rb") as handle:
        response = client.post(
            "/v1/files",
            headers=headers,
            files={"file": (path.name, handle, content_type)},
        )
    assert response.status_code == 201, response.text
    return response.json()


def _upload_raw(client, headers: dict, filename: str, data: bytes, content_type: str) -> dict:
    response = client.post(
        "/v1/files",
        headers=headers,
        files={"file": (filename, data, content_type)},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_upload_png_success(client, auth_a, video_dir):
    uploaded = _upload_image(
        client, auth_a, _make_image(video_dir / "slide.png"), "image/png"
    )
    assert uploaded["content_type"] == "image/png"
    assert uploaded["filename"] == "slide.png"
    assert "metadata" not in uploaded


def test_upload_jpeg_success(client, auth_a, video_dir):
    uploaded = _upload_image(
        client, auth_a, _make_image(video_dir / "slide.jpg", fmt="JPEG"), "image/jpeg"
    )
    assert uploaded["content_type"] == "image/jpeg"


def test_upload_txt_rejected_after_image_support(client, auth_a):
    response = client.post(
        "/v1/files",
        headers=auth_a,
        files={"file": ("note.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_replace_images_unauthorized(client):
    response = client.post(
        "/v1/jobs/replace-images",
        json={
            "file_id": "f_any",
            "replacements": [{"image_file_id": "f_img", "start": 0, "end": 1}],
        },
    )
    assert response.status_code == 401


def test_replace_images_empty_replacements(client, auth_a):
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={"file_id": "f_any"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_REPLACEMENTS"


def test_replace_images_too_many_replacements(client, auth_a):
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": "f_any",
            "replacements": [
                {"image_file_id": "f_img", "start": index, "end": index + 0.5}
                for index in range(11)
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "TOO_MANY_REPLACEMENTS"


def test_replace_images_invalid_range(client, auth_a):
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": "f_any",
            "replacements": [{"image_file_id": "f_img", "start": 2, "end": 2}],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RANGE"


def test_replace_images_negative_start(client, auth_a):
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": "f_any",
            "replacements": [{"image_file_id": "f_img", "start": -1, "end": 2}],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RANGE"


def test_replace_images_overlapping_ranges(client, auth_a):
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": "f_any",
            "replacements": [
                {"image_file_id": "f_img", "start": 1, "end": 3},
                {"image_file_id": "f_img", "start": 2, "end": 4},
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "OVERLAPPING_RANGES"


@requires_ffmpeg
def test_replace_images_wrong_file_type(client, auth_a, video_dir):
    clip = make_video(video_dir / "replace_wrong.mp4")
    video = upload_video(client, auth_a, clip)
    image = _upload_image(
        client, auth_a, _make_image(video_dir / "wrong.png"), "image/png"
    )

    swapped = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": image["file_id"],
            "replacements": [
                {"image_file_id": video["file_id"], "start": 0, "end": 0.5}
            ],
        },
    )
    assert swapped.status_code == 400
    assert swapped.json()["error"]["code"] == "WRONG_FILE_TYPE"


@requires_ffmpeg
def test_replace_images_end_after_duration_rejected(client, auth_a, video_dir):
    clip = make_video(video_dir / "replace_toolong.mp4", duration=1.0)
    video = upload_video(client, auth_a, clip)
    image = _upload_image(
        client, auth_a, _make_image(video_dir / "toolong.png"), "image/png"
    )
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": video["file_id"],
            "replacements": [
                {"image_file_id": image["file_id"], "start": 0, "end": 30}
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_RANGE"


@requires_ffmpeg
def test_replace_images_other_owners_file(client, auth_a, auth_b, video_dir):
    clip = make_video(video_dir / "replace_owner.mp4")
    video = upload_video(client, auth_a, clip)
    image = _upload_image(
        client, auth_a, _make_image(video_dir / "owner.png"), "image/png"
    )
    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_b,
        json={
            "file_id": video["file_id"],
            "replacements": [
                {"image_file_id": image["file_id"], "start": 0, "end": 0.5}
            ],
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED_FILE"


@requires_ffmpeg
def test_replace_images_success(client, auth_a, video_dir):
    from probe import probe_video

    clip = make_video(video_dir / "talk_replace.mp4", duration=1.0)
    video = upload_video(client, auth_a, clip)
    image = _upload_image(
        client, auth_a, _make_image(video_dir / "cover.png"), "image/png"
    )

    response = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": video["file_id"],
            "replacements": [
                {"image_file_id": image["file_id"], "start": 0.2, "end": 0.5},
                {"image_file_id": image["file_id"], "start": 0.5, "end": 0.8},
            ],
        },
    )
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["type"] == "replace_images"

    with session_scope() as session:
        record = session.get(JobRecord, job["job_id"])
        payload = json.loads(record.input_json)
        # 同一張圖用在兩段，只 pin 一次
        assert payload["file_ids"] == [video["file_id"], image["file_id"]]
        assert len(payload["replacements"]) == 2

    assert run_worker() >= 1
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "done", body
    assert body["progress"] == 100

    result = body["result"]
    assert result["filename"] == "talk_replace_replaced.mp4"
    assert result["content_type"] == "video/mp4"
    assert result["file_id"]

    registered = client.get(f"/v1/files/{result['file_id']}", headers=auth_a)
    assert registered.status_code == 200
    assert registered.json()["content_type"] == "video/mp4"

    output = video_dir / "downloaded_replaced.mp4"
    download = client.get(result["download_url"])
    assert download.status_code == 200
    output.write_bytes(download.content)
    assert abs(probe_video(output).duration - probe_video(clip).duration) < 0.15


@requires_ffmpeg
def test_replace_images_invalid_image(client, auth_a, video_dir):
    clip = make_video(video_dir / "replace_badimg.mp4")
    video = upload_video(client, auth_a, clip)
    broken = _upload_raw(client, auth_a, "broken.png", b"not an image", "image/png")

    job = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": video["file_id"],
            "replacements": [
                {"image_file_id": broken["file_id"], "start": 0, "end": 0.5}
            ],
        },
    ).json()
    run_worker()
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "INVALID_IMAGE"


@requires_ffmpeg
def test_replace_images_worker_rejects_range_past_duration(client, auth_a, video_dir):
    """API 的片長檢查靠上傳時的 metadata，Worker 仍會自行 probe 再擋一次。"""
    clip = make_video(video_dir / "replace_worker_range.mp4", duration=1.0)
    video = upload_video(client, auth_a, clip)
    image = _upload_image(
        client, auth_a, _make_image(video_dir / "range.png"), "image/png"
    )
    job = client.post(
        "/v1/jobs/replace-images",
        headers=auth_a,
        json={
            "file_id": video["file_id"],
            "replacements": [
                {"image_file_id": image["file_id"], "start": 0, "end": 0.5}
            ],
        },
    ).json()

    with session_scope() as session:
        record = session.get(JobRecord, job["job_id"])
        payload = json.loads(record.input_json)
        payload["replacements"][0]["end"] = 30.0
        record.input_json = json.dumps(payload)
        session.commit()

    run_worker()
    body = client.get(f"/v1/jobs/{job['job_id']}", headers=auth_a).json()
    assert body["status"] == "failed"
    assert body["error"]["code"] == "INVALID_RANGE"


def test_openapi_has_replace_images(client):
    spec = client.app.openapi()
    assert "/v1/jobs/replace-images" in spec["paths"]
