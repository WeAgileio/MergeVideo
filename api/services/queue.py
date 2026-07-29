"""Job 佇列。

DB（jobs.status = queued）是任務來源的唯一真相；worker 以原子更新 claim 任務，
Redis 僅作為喚醒通知（enqueue 時 LPUSH、worker 以 BRPOP 等待），
未設定 REDIS_URL 時 worker 以固定間隔輪詢 DB。
"""

from __future__ import annotations

import time

from api.config import get_settings

_QUEUE_KEY = "mergevideo:jobs"


class JobQueue:
    def __init__(self, redis_url: str | None) -> None:
        self._redis = None
        if redis_url:
            import redis

            self._redis = redis.from_url(redis_url)

    def enqueue(self, job_id: str) -> None:
        if self._redis is not None:
            self._redis.lpush(_QUEUE_KEY, job_id)

    def wait(self, timeout: float = 1.0) -> None:
        """等待新任務通知；無 Redis 時單純 sleep。"""
        if self._redis is not None:
            self._redis.brpop(_QUEUE_KEY, timeout=int(max(timeout, 1)))
        else:
            time.sleep(timeout)


_queue: JobQueue | None = None


def get_queue() -> JobQueue:
    global _queue
    if _queue is None:
        _queue = JobQueue(get_settings().redis_url)
    return _queue


def reset_queue_cache() -> None:
    """測試用。"""
    global _queue
    _queue = None
