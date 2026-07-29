"""SQLAlchemy engine 與 session 管理。"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _build_engine() -> Engine:
    url = get_settings().database_url
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # 確保 SQLite 檔案所在目錄存在
        db_path = url.split("///", 1)[-1]
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args)


def init_db() -> None:
    """建立 engine 並建表（冪等）。"""
    global _engine, _session_factory
    if _engine is None:
        _engine = _build_engine()
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    from api.models.records import Base

    Base.metadata.create_all(_engine)
    _apply_light_migrations(_engine)


def _apply_light_migrations(engine: Engine) -> None:
    """為既有資料表補新增欄位（create_all 不處理 ALTER）。"""
    from sqlalchemy import inspect, text

    columns = {col["name"] for col in inspect(engine).get_columns("jobs")}
    if "progress" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN progress INTEGER DEFAULT 0"))


def reset_db() -> None:
    """測試用：釋放 engine，讓下一次 init_db 重新讀取設定。"""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def _factory() -> sessionmaker[Session]:
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    return _session_factory


def get_session() -> Iterator[Session]:
    """FastAPI dependency。"""
    session = _factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Worker / 背景任務使用。"""
    session = _factory()()
    try:
        yield session
    finally:
        session.close()
