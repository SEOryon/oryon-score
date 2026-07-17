"""
Regression test for the brotli decode bug.

_fetch() sends `Accept-Encoding: gzip, deflate, br`, but httpx only decodes
`Content-Encoding: br` responses when a brotli backend (brotli / brotlicffi)
is importable. When it isn't, httpx falls back to the identity decoder and
hands the *undecoded* brotli bytes to BeautifulSoup, which parses binary
garbage: page_title comes back None and every DOM-based signal silently
scores 0, while non-DOM signals (HTTPS, robots.txt, Last-Modified) keep
passing. Production shipped in exactly that state — score.seoryon.com scored
itself 20/F; the identical engine with brotli installed scores it 39/F.

These tests fail loudly if the brotli dependency is ever dropped again.
No scoring logic is touched; we only verify the fetch->parse pipeline.
"""
from __future__ import annotations

import httpx
import pytest
from bs4 import BeautifulSoup

HTML = (
    "<!doctype html><html><head>"
    "<title>Brotli decode canary · oryon-score</title>"
    "</head><body>"
    "<h1>Heading survives brotli</h1>"
    "<p>If you can read this in r.text, httpx decoded the br body.</p>"
    "</body></html>"
)


def test_brotli_backend_installed():
    """The dependency itself: api/requirements.txt and pyproject must keep a
    brotli backend, or _fetch()'s `br` in Accept-Encoding is a lie."""
    try:
        import brotli  # noqa: F401
    except ImportError:
        try:
            import brotlicffi  # noqa: F401
        except ImportError:
            pytest.fail(
                "No brotli backend importable. httpx will silently return "
                "undecoded bytes for Content-Encoding: br responses and every "
                "DOM signal will score 0. Restore `brotli` in api/requirements.txt "
                "and pyproject.toml."
            )


def test_page_title_parses_from_br_encoded_response():
    """End-to-end through httpx's decoding pipeline: serve genuinely
    brotli-compressed HTML with Content-Encoding: br, then parse r.text the
    exact way score_url() does. Without a brotli backend, r.text is mojibake,
    soup.find('title') is None, and this test fails."""
    brotli = pytest.importorskip("brotli")
    compressed = brotli.compress(HTML.encode("utf-8"))
    assert compressed != HTML.encode("utf-8")  # really compressed, not a no-op

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=compressed,
            headers={
                "Content-Encoding": "br",
                "Content-Type": "text/html; charset=utf-8",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        r = client.get("https://brotli-canary.example/")

    # Mirror score_url()'s parse path exactly.
    soup = BeautifulSoup(r.text, "lxml")
    title_tag = soup.find("title")
    page_title = title_tag.get_text(strip=True) if title_tag else None

    assert page_title is not None, (
        "page_title parsed as None from a br-encoded response — the brotli "
        "decode regression is back."
    )
    assert page_title == "Brotli decode canary · oryon-score"

    # The bug's signature was every DOM signal reading 0 — assert the DOM
    # actually survived, not just the <title>.
    assert len(soup.find_all("h1")) == 1
    assert len(soup.find_all("p")) == 1
