import httpx
import pytest

from research_agent.agent.tools import fetch as fetch_module
from research_agent.agent.tools.fetch import UnsafeURLError, assert_public_url, extract_text, fetch_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://example.com/",
    ],
)
async def test_blocks_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        await assert_public_url(url)


async def test_allows_public_ip_literal():
    await assert_public_url("http://93.184.216.34/")


def test_extract_text_skips_scripts_and_reads_title():
    html = (
        "<html><head><title>Acme Pricing</title><style>x{}</style></head>"
        "<body><script>evil()</script><h1>Plans</h1><p>Pro is $20.</p></body></html>"
    )
    title, text = extract_text(html, "text/html")
    assert title == "Acme Pricing"
    assert "Pro is $20." in text
    assert "evil" not in text


def _patch_transport(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(
        fetch_module.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


async def test_fetch_returns_text(monkeypatch):
    def handler(request):
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<title>Hi</title><p>Hello world</p>",
        )

    _patch_transport(monkeypatch, handler)
    page = await fetch_url("http://93.184.216.34/")
    assert page["title"] == "Hi"
    assert "Hello world" in page["text"]


async def test_redirect_to_private_address_is_blocked(monkeypatch):
    def handler(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})

    _patch_transport(monkeypatch, handler)
    with pytest.raises(UnsafeURLError):
        await fetch_url("http://93.184.216.34/")


async def test_rejects_binary_content_type(monkeypatch):
    def handler(request):
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")

    _patch_transport(monkeypatch, handler)
    with pytest.raises(UnsafeURLError):
        await fetch_url("http://93.184.216.34/")
