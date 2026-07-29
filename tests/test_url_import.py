"""url_import SSRF 與 URL 驗證單元測試。"""

from __future__ import annotations

import socket
from pathlib import Path

import httpx
import pytest

from api.services.url_import import (
    UrlImportError,
    check_host,
    download_url_to_file,
    validate_url_scheme,
)


def test_validate_url_rejects_http_by_default():
    with pytest.raises(UrlImportError) as exc:
        validate_url_scheme("http://example.com/v.mp4", allow_http=False)
    assert exc.value.code == "INVALID_URL"


def test_validate_url_allows_http_when_enabled():
    validate_url_scheme("http://example.com/v.mp4", allow_http=True)


def test_validate_url_rejects_file_scheme():
    with pytest.raises(UrlImportError) as exc:
        validate_url_scheme("file:///etc/passwd", allow_http=True)
    assert exc.value.code == "INVALID_URL"


def test_check_host_blocks_loopback(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UrlImportError) as exc:
        check_host("localhost")
    assert exc.value.code == "URL_NOT_ALLOWED"


def test_check_host_blocks_private_10(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UrlImportError) as exc:
        check_host("internal.example")
    assert exc.value.code == "URL_NOT_ALLOWED"


def test_check_host_blocks_metadata_ip(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UrlImportError) as exc:
        check_host("metadata.google.internal")
    assert exc.value.code == "URL_NOT_ALLOWED"


def test_download_redirect_to_private_ip_blocked(monkeypatch, tmp_path):
    hosts_seen: list[str] = []

    def fake_getaddrinfo(host, port, *args, **kwargs):
        hosts_seen.append(host)
        if host == "redirect-target.test":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))]
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "source.test":
            return httpx.Response(
                302, headers={"Location": "https://redirect-target.test/file.mp4"}
            )
        return httpx.Response(200, content=b"data")

    handler_fn = handler
    import api.services.url_import as url_import_mod

    real_client = url_import_mod.httpx.Client

    def client_factory(**kw):
        return real_client(
            transport=httpx.MockTransport(handler_fn),
            timeout=kw.get("timeout"),
            follow_redirects=False,
        )

    monkeypatch.setattr(url_import_mod.httpx, "Client", client_factory)

    with pytest.raises(UrlImportError) as exc:
        download_url_to_file(
            "https://source.test/start",
            tmp_path / "out.mp4",
            allow_http=False,
            max_bytes=1024 * 1024,
            connect_timeout=5,
            total_timeout=30,
            max_redirects=3,
        )
    assert exc.value.code == "URL_NOT_ALLOWED"
    assert "redirect-target.test" in hosts_seen
