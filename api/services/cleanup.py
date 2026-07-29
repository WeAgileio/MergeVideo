"""過期 file 與 result 清理。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.models import FileRecord, JobRecord, JobStatus, utcnow
from api.services.storage import Storage


def cleanup_expired(session: Session, storage: Storage) -> int:
    """刪除過期且未被 pin 的上傳檔，以及超過 TTL 的 job 結果。回傳清理筆數。"""
    settings = get_settings()
    now = utcnow()
    removed = 0

    files = session.scalars(select(FileRecord).where(FileRecord.active_jobs <= 0)).all()
    for record in files:
        if record.expires_at < now:
            storage.delete(record.storage_key)
            session.delete(record)
            removed += 1

    cutoff = now - timedelta(hours=settings.result_ttl_hours)
    jobs = session.scalars(
        select(JobRecord).where(
            JobRecord.status == JobStatus.DONE,
            JobRecord.result_json.is_not(None),
            JobRecord.completed_at < cutoff,
        )
    ).all()
    for job in jobs:
        storage.delete_prefix(f"results/{job.job_id}/")
        job.result_json = None
        removed += 1

    session.commit()
    return removed
