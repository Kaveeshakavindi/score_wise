from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.services.url_fetch import _assert_host_is_safe, fetch_url_safely, strip_html


def test_rejects_non_http_scheme() -> None:
    with pytest.raises(ValidationError):
        _assert_host_is_safe("ftp://example.com/file")


def test_rejects_url_missing_hostname() -> None:
    with pytest.raises(ValidationError):
        _assert_host_is_safe("http:///no-host")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint — classic SSRF target
        "http://0.0.0.0/",
    ],
)
def test_rejects_private_loopback_and_link_local_hosts(url: str) -> None:
    # §6.5 SSRF protection: the hostname is resolved and checked against
    # private/loopback/link-local ranges before any connection is attempted.
    with pytest.raises(ValidationError):
        _assert_host_is_safe(url)


async def test_fetch_url_safely_rejects_loopback_before_connecting() -> None:
    # The SSRF check runs before the network call, so this must fail fast with
    # a ValidationError rather than actually attempting to connect.
    with pytest.raises(ValidationError):
        await fetch_url_safely("http://127.0.0.1:1/", max_bytes=1000)


def test_strip_html_removes_tags_scripts_and_styles() -> None:
    html = (
        "<html><head><style>.a{color:red}</style></head>"
        "<body><script>evil()</script><p>Hello <b>world</b></p></body></html>"
    )
    text = strip_html(html)

    assert "evil()" not in text
    assert "color:red" not in text
    assert "<" not in text and ">" not in text
    assert "Hello" in text and "world" in text


def test_strip_html_collapses_whitespace() -> None:
    assert strip_html("<p>a</p>\n\n<p>b</p>") == "a b"
