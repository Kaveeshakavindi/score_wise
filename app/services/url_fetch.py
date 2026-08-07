from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.core.exceptions import PayloadTooLargeError, UpstreamError, ValidationError

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local
]

_USER_AGENT = "custom-chatbot-api/1.0"
_MAX_REDIRECTS = 3


@dataclass(frozen=True)
class FetchResult:
    content_type: str
    text: str


def _is_blocked_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved:
        return True
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _assert_host_is_safe(url: str) -> str:
    """Resolves the hostname and rejects private/loopback/link-local ranges
    before connecting — SSRF protection per §6.5. Returns the validated host."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValidationError("Only http(s) URLs are allowed.")
    if not parts.hostname:
        raise ValidationError("URL is missing a hostname.")

    try:
        addr_infos = socket.getaddrinfo(parts.hostname, None)
    except socket.gaierror as exc:
        raise ValidationError(f"Could not resolve host: {parts.hostname}") from exc

    for family, _, _, _, sockaddr in addr_infos:
        ip = sockaddr[0]
        if _is_blocked_ip(ip):
            raise ValidationError("URL resolves to a private/internal address and is not allowed.")

    return parts.hostname


async def fetch_url_safely(url: str, *, max_bytes: int, timeout_s: float = 8.0) -> FetchResult:
    """SSRF-hardened HTTP GET: validates scheme, resolves + checks the target IP
    against private/loopback/link-local ranges before every hop (including
    redirects), enforces a byte cap and timeout. No auto-retry — a slow/
    unreachable third-party site should fail fast (§11)."""
    current_url = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout_s) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            _assert_host_is_safe(current_url)
            try:
                async with client.stream(
                    "GET", current_url, headers={"User-Agent": _USER_AGENT}
                ) as response:
                    if response.is_redirect:
                        next_url = response.headers.get("location")
                        if not next_url:
                            raise UpstreamError("Redirect response missing Location header.")
                        current_url = httpx.URL(current_url).join(next_url).human_repr()
                        continue

                    content_type = response.headers.get("content-type", "")
                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise PayloadTooLargeError(
                                f"Response exceeded the {max_bytes}-byte ingest limit."
                            )
                        chunks.append(chunk)
                    raw = b"".join(chunks)
                    return FetchResult(content_type=content_type, text=raw.decode("utf-8", errors="replace"))
            except httpx.TimeoutException as exc:
                raise UpstreamError(f"Timed out fetching {current_url}") from exc
            except httpx.HTTPError as exc:
                raise UpstreamError(f"Failed to fetch {current_url}: {exc}") from exc

    raise UpstreamError("Too many redirects while fetching URL.")


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?is)<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
