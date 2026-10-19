from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
MAX_BYTES = 1_000_000
MAX_REDIRECTS = 3
TIMEOUT_SECONDS = 15.0
USER_AGENT = "research-agent/0.1 (+fetch)"


class UnsafeURLError(ValueError):
    """Raised when a URL targets a non-public address or disallowed scheme."""


def _is_public_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def assert_public_url(url: str) -> None:
    """Reject non-http(s) URLs and hosts that resolve to non-public addresses."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError(f"Scheme not allowed: {parsed.scheme or 'none'}")
    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host")

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Cannot resolve host: {host}") from exc

    for info in infos:
        address = info[4][0].split("%")[0]
        if not _is_public_ip(address):
            raise UnsafeURLError(f"Host resolves to a non-public address: {host}")


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "title":
            self._in_title = True
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title += text
        elif not self._skip_depth:
            self._parts.append(text)

    def text(self) -> str:
        return "\n".join(self._parts)


def extract_text(body: str, content_type: str) -> tuple[str | None, str]:
    """Return (title, text) from an HTML or plain-text body."""
    if content_type.startswith("text/plain"):
        return None, body.strip()
    parser = _TextExtractor()
    parser.feed(body)
    return (parser.title or None), parser.text()


async def fetch_url(url: str, *, max_chars: int = 6000) -> dict[str, str | None]:
    """Fetch a public web page and return its title and readable text.

    Every hop (including redirects) is checked against the public-IP rule.
    Raises UnsafeURLError for blocked targets and httpx errors for network failures.
    """
    current = url
    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await assert_public_url(current)
            async with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeURLError("Redirect without Location header")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()

                content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    raise UnsafeURLError(f"Content type not allowed: {content_type or 'unknown'}")

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    chunks.append(chunk)
                    if size >= MAX_BYTES:
                        break
                body = b"".join(chunks)[:MAX_BYTES].decode(response.encoding or "utf-8", errors="replace")

                title, text = extract_text(body, content_type)
                return {"url": str(response.url), "title": title, "text": text[:max_chars]}
    raise UnsafeURLError("Too many redirects")
