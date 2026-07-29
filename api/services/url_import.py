"""從 URL 下載影片（含 SSRF 防護）。"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import httpx

from scanner import VIDEO_EXTENSIONS


class UrlImportError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


def infer_filename(url: str, override: str | None) -> str:
    if override:
        return Path(override).name
    path = unquote(urlparse(url).path)
    name = Path(path).name
    return name if name else "video.mp4"


def validate_url_scheme(url: str, *, allow_http: bool) -> None:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("https", "http"):
        raise UrlImportError(
            "INVALID_URL", f"不支援的 URL scheme: {parsed.scheme or '(空)'}"
        )
    if parsed.scheme == "http" and not allow_http:
        raise UrlImportError(
            "INVALID_URL", "僅允許 https URL（或設定 IMPORT_URL_ALLOW_HTTP=true）"
        )
    if not parsed.hostname:
        raise UrlImportError("INVALID_URL", "URL 缺少 hostname")
    if parsed.username or parsed.password:
        raise UrlImportError("INVALID_URL", "URL 不可含使用者名稱或密碼")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    ):
        return True
    return ip == ipaddress.ip_address("169.254.169.254")


def check_host(host: str) -> None:
    """DNS 解析後檢查 IP 是否在 blocklist（SSRF 防護）。"""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UrlImportError("DOWNLOAD_FAILED", f"無法解析 hostname: {host}") from exc

    for info in infos:
        ip_str = info[4][0]
        ip = ipaddress.ip_address(ip_str)
        if _is_blocked_ip(ip):
            raise UrlImportError("URL_NOT_ALLOWED", f"URL 指向不允許的位址: {ip_str}")


def validate_video_file(path: Path, filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise UrlImportError(
            "UNSUPPORTED_FORMAT",
            f"不支援的檔案格式: {suffix or '(無副檔名)'}",
        )
    try:
        from probe import probe_video

        probe_video(path)
    except Exception as exc:
        raise UrlImportError("UNSUPPORTED_FORMAT", f"無法解析影片: {exc}") from exc


def download_url_to_file(
    url: str,
    dest: Path,
    *,
    allow_http: bool,
    max_bytes: int,
    connect_timeout: float,
    total_timeout: float,
    max_redirects: int,
    on_progress: Callable[[float], None] | None = None,
) -> None:
    """Streaming 下載 URL 至 dest；redirect 每次 re-check IP。"""
    current = url.strip()
    timeout = httpx.Timeout(total_timeout, connect=connect_timeout)

    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        redirects = 0
        while True:
            validate_url_scheme(current, allow_http=allow_http)
            hostname = urlparse(current).hostname
            if not hostname:
                raise UrlImportError("INVALID_URL", "URL 缺少 hostname")
            check_host(hostname)

            with client.stream("GET", current) as response:
                if 300 <= response.status_code < 400:
                    redirects += 1
                    if redirects > max_redirects:
                        raise UrlImportError("DOWNLOAD_FAILED", "超過 redirect 次數上限")
                    location = response.headers.get("location")
                    if not location:
                        raise UrlImportError("DOWNLOAD_FAILED", "redirect 缺少 Location header")
                    current = urljoin(current, location)
                    continue

                if response.status_code >= 400:
                    raise UrlImportError(
                        "DOWNLOAD_FAILED",
                        f"下載失敗 HTTP {response.status_code}",
                    )

                content_length = response.headers.get("content-length")
                total: int | None = int(content_length) if content_length else None
                if total is not None and total > max_bytes:
                    raise UrlImportError(
                        "FILE_TOO_LARGE",
                        f"檔案超過大小上限 {max_bytes // (1024 * 1024)} MB",
                    )

                downloaded = 0
                with dest.open("wb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            raise UrlImportError(
                                "FILE_TOO_LARGE",
                                f"檔案超過大小上限 {max_bytes // (1024 * 1024)} MB",
                            )
                        handle.write(chunk)
                        if on_progress is not None and total:
                            on_progress(min(downloaded / total, 1.0))
                return
