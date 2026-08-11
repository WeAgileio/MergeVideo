"""Worker：claim job → 下載輸入 → FFmpeg 處理 → 上傳結果 → 更新狀態。

單一 worker process 設計（claim 為 DB 讀寫非跨程序原子鎖）；
如需多 worker 水平擴展，claim 需改為 SELECT ... FOR UPDATE SKIP LOCKED。
"""

from __future__ import annotations

import json
import tempfile
import time
import traceback
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

import api  # noqa: F401  # 確保 repo 根目錄在 sys.path，才能 import 核心模組
from api.config import compute_file_expires_at, expires_at_to_api, get_settings
from api.db import init_db, session_scope
from api.models import FileRecord, JobRecord, JobStatus, utcnow
from api.routes.files import _probe_metadata
from api.services.cleanup import cleanup_expired
from api.services.queue import get_queue
from api.services.storage import Storage, get_storage
from api.services.url_import import (
    UrlImportError,
    download_url_to_file,
    infer_filename,
    validate_video_file,
)
from extract_frame import extract_first_frame, extract_last_frame
from merger import merge_auto

_CLEANUP_INTERVAL_SECONDS = 60.0  # fallback；正式值由 config 提供


def claim_next_job(session: Session) -> JobRecord | None:
    job = session.scalars(
        select(JobRecord)
        .where(JobRecord.status == JobStatus.QUEUED)
        .order_by(JobRecord.created_at)
        .limit(1)
    ).first()
    if job is None:
        return None
    job.status = JobStatus.PROCESSING
    job.started_at = utcnow()
    job.progress = 0
    session.commit()
    return job


def _make_progress_updater(job: JobRecord, session: Session):
    """回傳節流的進度 callback：>= 1% 變化且間隔 1 秒才寫 DB，上限 99%。"""
    state = {"percent": -1, "at": 0.0}

    def on_progress(fraction: float) -> None:
        percent = min(int(fraction * 100), 99)
        now = time.monotonic()
        if percent > state["percent"] and now - state["at"] >= 1.0:
            job.progress = percent
            session.commit()
            state["percent"] = percent
            state["at"] = now

    return on_progress


def _fetch_input(
    session: Session, storage: Storage, file_id: str, dest: Path
) -> FileRecord:
    record = session.get(FileRecord, file_id)
    if record is None:
        raise RuntimeError(f"輸入檔已不存在: {file_id}")
    storage.fetch(record.storage_key, dest)
    return record


def _run_merge(job: JobRecord, session: Session, storage: Storage, tmp: Path) -> dict:
    payload = json.loads(job.input_json)
    file_ids: list[str] = payload["file_ids"]
    crf: int = payload.get("crf", 18)

    paths: list[Path] = []
    for index, file_id in enumerate(file_ids):
        record = session.get(FileRecord, file_id)
        if record is None:
            raise RuntimeError(f"輸入檔已不存在: {file_id}")
        dest = tmp / f"{index:03d}{Path(record.storage_key).suffix}"
        storage.fetch(record.storage_key, dest)
        paths.append(dest)

    output_path = tmp / "merged.mp4"
    merge_auto(
        paths, output_path, crf=crf, progress_callback=_make_progress_updater(job, session)
    )

    storage_key = f"results/{job.job_id}/merged.mp4"
    storage.put(storage_key, output_path, "video/mp4")
    return {
        "storage_key": storage_key,
        "filename": "merged.mp4",
        "content_type": "video/mp4",
        "size_bytes": output_path.stat().st_size,
    }


def _run_extract(
    job: JobRecord, session: Session, storage: Storage, tmp: Path, *, last: bool
) -> dict:
    payload = json.loads(job.input_json)
    file_id: str = payload["file_ids"][0]

    record = session.get(FileRecord, file_id)
    if record is None:
        raise RuntimeError(f"輸入檔已不存在: {file_id}")

    stem = Path(record.filename).stem or "video"
    dest = tmp / f"{stem}{Path(record.storage_key).suffix}"
    storage.fetch(record.storage_key, dest)

    extractor = extract_last_frame if last else extract_first_frame
    png_path = extractor(dest)

    storage_key = f"results/{job.job_id}/{png_path.name}"
    storage.put(storage_key, png_path, "image/png")
    return {
        "storage_key": storage_key,
        "filename": png_path.name,
        "content_type": "image/png",
        "size_bytes": png_path.stat().st_size,
    }


def _run_import_url(job: JobRecord, session: Session, storage: Storage, tmp: Path) -> dict:
    settings = get_settings()
    payload = json.loads(job.input_json)
    url: str = payload["url"]
    filename = infer_filename(url, payload.get("filename"))
    suffix = Path(filename).suffix.lower() or ".mp4"
    dest = tmp / f"download{suffix}"

    updater = _make_progress_updater(job, session)

    def on_download_progress(fraction: float) -> None:
        updater(min(fraction * 0.9, 0.9))

    download_url_to_file(
        url,
        dest,
        allow_http=settings.import_url_allow_http,
        max_bytes=settings.max_file_size_bytes,
        connect_timeout=settings.import_url_connect_timeout_sec,
        total_timeout=settings.import_url_total_timeout_sec,
        max_redirects=settings.import_url_max_redirects,
        on_progress=on_download_progress,
    )
    validate_video_file(dest, filename)

    file_id = f"f_{uuid.uuid4().hex[:12]}"
    storage_key = f"uploads/{file_id}/original{suffix}"
    storage.put(storage_key, dest, "video/mp4")

    now = utcnow()
    expires_at = compute_file_expires_at(now, settings.file_ttl_hours)
    record = FileRecord(
        file_id=file_id,
        owner_key=job.owner_key,
        filename=filename,
        storage_key=storage_key,
        size_bytes=dest.stat().st_size,
        content_type="video/mp4",
        metadata_json=_probe_metadata(dest),
        created_at=now,
        expires_at=expires_at,
    )
    session.add(record)
    session.flush()

    return {
        "file_id": file_id,
        "filename": filename,
        "size_bytes": record.size_bytes,
        "expires_at": expires_at_to_api(expires_at),
    }


def _unpin_files(session: Session, job: JobRecord) -> None:
    payload = json.loads(job.input_json)
    for file_id in set(payload.get("file_ids", [])):
        record = session.get(FileRecord, file_id)
        if record is not None and record.active_jobs > 0:
            record.active_jobs -= 1


def process_job(job: JobRecord, session: Session, storage: Storage) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="mergevideo_job_") as tmp_dir:
            tmp = Path(tmp_dir)
            if job.type == "merge":
                result = _run_merge(job, session, storage, tmp)
            elif job.type == "extract_first_frame":
                result = _run_extract(job, session, storage, tmp, last=False)
            elif job.type == "extract_last_frame":
                result = _run_extract(job, session, storage, tmp, last=True)
            elif job.type == "import_url":
                result = _run_import_url(job, session, storage, tmp)
            else:
                raise RuntimeError(f"未知的任務類型: {job.type}")

        job.status = JobStatus.DONE
        job.progress = 100
        job.result_json = json.dumps(result)
    except UrlImportError as exc:
        job.status = JobStatus.FAILED
        job.error_code = exc.code
        job.error_message = exc.message
    except Exception as exc:
        traceback.print_exc()
        job.status = JobStatus.FAILED
        job.error_code = "FFMPEG_ERROR"
        job.error_message = str(exc)
    finally:
        job.completed_at = utcnow()
        _unpin_files(session, job)
        session.commit()


def process_next(session: Session, storage: Storage) -> bool:
    """處理一個佇列中的 job；有處理回傳 True。"""
    job = claim_next_job(session)
    if job is None:
        return False
    process_job(job, session, storage)
    return True


def process_pending_jobs() -> int:
    """處理所有排隊中的 job（測試 / 手動觸發用）。"""
    init_db()
    storage = get_storage()
    count = 0
    with session_scope() as session:
        while process_next(session, storage):
            count += 1
    return count


def run_forever() -> None:
    init_db()
    storage = get_storage()
    queue = get_queue()
    settings = get_settings()
    last_cleanup = 0.0
    cleanup_interval = (
        settings.cleanup_interval_seconds
        if settings.auto_cleanup_enabled
        else _CLEANUP_INTERVAL_SECONDS
    )
    print("Worker 已啟動，等待任務...")

    while True:
        with session_scope() as session:
            worked = process_next(session, storage)

            if settings.auto_cleanup_enabled and time.monotonic() - last_cleanup > cleanup_interval:
                removed = cleanup_expired(session, storage)
                if removed:
                    print(f"清理過期資源: {removed} 筆")
                last_cleanup = time.monotonic()

        if not worked:
            queue.wait(timeout=1.0)
