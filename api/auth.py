"""API key 驗證與 owner_key 綁定。"""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.config import get_settings
from api.errors import ApiError

# 以 HTTPBearer 宣告 security scheme，讓 Swagger UI 顯示 Authorize 按鈕
_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="ApiKeyBearer",
    description="填入 API key（即 .env 中 API_KEYS 的其中一組）",
)


def owner_key_for(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency：驗證 Bearer API key，回傳 owner_key。"""
    if credentials is None:
        raise ApiError(401, "UNAUTHORIZED", "缺少 Authorization: Bearer <api_key>")

    provided = credentials.credentials.strip()
    for valid in get_settings().api_keys:
        if hmac.compare_digest(provided, valid):
            return owner_key_for(provided)
    raise ApiError(401, "UNAUTHORIZED", "無效的 API key")
