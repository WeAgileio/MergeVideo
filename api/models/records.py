"""File registry 與 Job store 資料模型。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    """UTC naive datetime（SQLite 排序 / 比較穩定）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class JobStatus:
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class FileRecord(Base):
    __tablename__ = "files"

    file_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_key: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(64), default="video/mp4")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 進行中 job 的引用數；> 0 時檔案被 pin，不得刪除或視為過期
    active_jobs: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    def is_expired(self, now: datetime | None = None) -> bool:
        moment = now or utcnow()
        return self.expires_at < moment and self.active_jobs <= 0


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_key: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED, index=True)
    input_json: Mapped[str] = mapped_column(Text)
    # 處理進度 0–100；queued 為 0，done 為 100
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
