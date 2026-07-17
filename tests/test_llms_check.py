"""
Regression tests for the llms.txt check (0.3.0) and the honest-copy rewrite.

The bug being pinned: the old rule — HTTP 200 + body length > 50 — passed on
any SPA host whose catch-all rewrite serves the homepage for missing paths.
Proven live: the hosted scorer awarded roi.seoryon.com "llms.txt present at
site root" while roi.seoryon.com/llms.txt actually returned the HTML homepage
(text/html). The check now requires text content AND a soft-404 control probe
with fail-closed semantics on every ambiguous outcome.

Weights must stay byte-identical: the signal is worth 3 points, pass or fail.

Seams: `fetch` (the llms.txt request, returns (response, err); responses carry
`.history` like httpx's) and `probe` (the control request, returns
(status, content_type, body_head) or None). The production probe
(_probe_soft404) is resource-bounded and never raises; it is exercised
directly below through httpx.MockTransport.
"""
from __future__ import annotations

import json
import pathlib
from urllib.parse import urlparse

from oryon_score.score import (
    _LLMS_PROBE_PATH,
    _LLMS_PROBE_SNIFF_BYTES,
    _LLMS_PROBE_WALL_CLOCK_S,
    _check_llms_txt,
    _looks_like_html,
    _probe_soft404,
)

PARSED = urlparse("https://example.com")

REAL_LLMS = (
    "# Example Site\n\n"
    "> A free example site that documents examples for the example industry.\n\n"
    "## Docs\n\n- [Getting started](https://example.com/docs): the basics\n"
)

FALLBACK_HTML = (
    "<!doctype html>\n<html lang=\"en\"><head><title>Example</title></head>"
    "<body><div id=\"root\"></div><p>" + "x" * 200 + "</p></body></html>"
)


class FakeResponse:
    def __init__(self, status_code=200, text="", content_type=None, history=()):
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": content_type} if content_type else {}
        self.history = list(history)  # non-empty = arrived via redirects


def llms_fetch(resp, calls=None):
    """Fetch seam serving only /llms.txt; records calls."""
    calls = calls if calls is not None else []

    def fetch(url):
        calls.append(url)
        if url.endswith("/llms.txt") and resp is not None:
            return resp, None
        return None, "not found"

    fetch.calls = calls
    return fetch


def probe_returning(status, body="", content_type="text/plain"):
    def probe(url):
        assert url.endswith(_LLMS_PROBE_PATH)
        return status, content_type, body

    return probe


def probe_failing(url):
    return None


# ---------------------------------------------------------------------------
# Pass paths
# ---------------------------------------------------------------------------

def test_genuine_llms_txt_passes_when_site_404s_nonsense():
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain; charset=utf-8"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(404))
    assert s.passed is True
    assert s.weight == 3 and s.points == 3


def test_probe_410_counts_as_absence():
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(410))
    assert s.passed is True and s.points == 3


def test_real_text_llms_on_spa_host_passes_the_score_seoryon_case():
    """A real text llms.txt on a host whose catch-all serves the HTML shell
    for unknown paths (score.seoryon.com after this deploy)."""
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain; charset=utf-8"))
    s = _check_llms_txt(
        PARSED, fetch=fetch,
        probe=probe_returning(200, FALLBACK_HTML, "text/html; charset=utf-8"),
    )
    assert s.passed is True and s.points == 3


def test_probe_redirect_passes_when_llms_served_directly():
    """A catch-all that redirects unknown paths is a distinct handler class
    from an llms.txt answering 200 directly (empty history)."""
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain", history=()))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(302, "", "text/html"))
    assert s.passed is True and s.points == 3


def test_markdown_mentioning_html_word_is_not_rejected():
    """Starts-with sniffing only: a real markdown file may mention '<html' in
    prose or a code example without being an HTML page."""
    body = REAL_LLMS + "\nOur crawler downloads raw `<html>` documents and parses them.\n"
    assert _looks_like_html(body) is False
    fetch = llms_fetch(FakeResponse(200, body, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(404))
    assert s.passed is True


# ---------------------------------------------------------------------------
# Reject paths — the live bug and its variants
# ---------------------------------------------------------------------------

def test_html_fallback_fails_the_roi_seoryon_case():
    """The exact live false positive: 200 + text/html homepage at /llms.txt."""
    probe_calls = []

    def counting_probe(url):
        probe_calls.append(url)
        return 404, "text/plain", "no"

    fetch = llms_fetch(FakeResponse(200, FALLBACK_HTML, "text/html; charset=utf-8"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=counting_probe)
    assert s.passed is False and s.points == 0
    assert "HTML" in s.detail
    # The HTML gate must reject BEFORE paying for the control probe.
    assert probe_calls == []


def test_html_fragment_starting_with_div_is_rejected():
    fragment = "<div class=\"app\">" + "content " * 50 + "</div>"
    fetch = llms_fetch(FakeResponse(200, fragment))  # no content-type header
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(404))
    assert s.passed is False


def test_bom_whitespace_and_formfeed_padded_html_is_still_html():
    """Codex evasions across rounds: BOM before <!doctype, leading whitespace
    past a naive slice window, and \\f (HTML ASCII whitespace)."""
    assert _looks_like_html("﻿<!doctype html><html><body>x</body></html>") is True
    assert _looks_like_html("\n" * 5000 + "<!doctype html><html></html>") is True
    assert _looks_like_html("\f" * 5000 + "<!doctype html><html></html>") is True
    fetch = llms_fetch(FakeResponse(200, "﻿" + FALLBACK_HTML, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(404))
    assert s.passed is False


def test_non_text_content_type_is_rejected():
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "application/octet-stream"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(404))
    assert s.passed is False and "content-type" in s.detail


def test_plaintext_catchall_fails_via_probe():
    """Any 2xx non-HTML probe response means arbitrary paths get 200 text —
    a 'real' llms.txt is indistinguishable from that catch-all. This covers
    identical, near-identical, AND distinct bodies: all score zero, which is
    why the check needs no content-similarity comparison at all."""
    catchall = "welcome to our very generic landing page " * 5
    fetch = llms_fetch(FakeResponse(200, catchall, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(200, catchall))
    assert s.passed is False and "catch-all" in s.detail

    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
    s = _check_llms_txt(
        PARSED, fetch=fetch,
        probe=probe_returning(200, "totally different text response here " * 5),
    )
    assert s.passed is False and s.points == 0


def test_probe_redirect_fails_closed_when_llms_also_redirected():
    """Codex round-5 blocker: if /llms.txt itself arrived via redirects and
    unknown paths also redirect, the handler classes are NOT distinct — a
    redirecting catch-all could be behind both. Fail closed."""
    fetch = llms_fetch(
        FakeResponse(200, REAL_LLMS, "text/plain", history=["redirect-hop"])
    )
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(301, "", "text/html"))
    assert s.passed is False and s.points == 0


def test_probe_transport_failure_fails_closed():
    """Codex round-1 blocker: a dead probe must never award credit."""
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_failing)
    assert s.passed is False and s.points == 0
    assert "not scored" in s.detail.lower()


def test_probe_non_absence_errors_fail_closed():
    """Codex round-2 blocker: 401/403/429/5xx on the probe prove nothing about
    llms.txt authenticity — only genuine absence statuses (404/410) verify."""
    for status in (400, 401, 403, 429, 500, 503):
        fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
        s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(status))
        assert s.passed is False and s.points == 0, f"probe {status} must fail closed"
        assert str(status) in s.detail


def test_probe_1xx_fails_closed():
    """Codex round-5: a 101 must not slip into the 2xx branch and mint credit."""
    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(101, "", "text/html"))
    assert s.passed is False and s.points == 0


def test_probe_exception_fails_closed_not_500():
    """Codex round-3 blocker: an exception escaping the probe crashed the
    endpoint. Any probe exception must degrade to fail-closed, never raise."""

    def exploding_probe(url):
        raise RuntimeError("boom")

    fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=exploding_probe)
    assert s.passed is False and s.points == 0


def test_probe_malformed_results_fail_closed():
    """Codex round-5: wrong tuple shapes / types from an injected probe must
    fail closed, never raise out of the check."""
    malformed = [
        lambda url: (404,),                       # too short
        lambda url: (404, "text/plain", "x", True, 5),  # too long
        lambda url: ("not-an-int-at-all", "text/plain", "x"),
        lambda url: object(),                     # not a tuple
        lambda url: [404, "text/plain", "x"],     # list, not tuple
        lambda url: (404.9, "text/plain", "x"),   # float status
        lambda url: ("404", "text/plain", "x"),   # numeric string status
        lambda url: (True, "text/plain", "x"),    # bool is not an int here
        lambda url: (404, None, "x"),             # None content-type
    ]
    for bad_probe in malformed:
        fetch = llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain"))
        s = _check_llms_txt(PARSED, fetch=fetch, probe=bad_probe)
        assert s.passed is False and s.points == 0


def test_404_fails_with_no_probe_call():
    probe_calls = []

    def counting_probe(url):
        probe_calls.append(url)
        return 404, "text/plain", "no"

    fetch = llms_fetch(FakeResponse(404, "nope"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=counting_probe)
    assert s.passed is False and s.points == 0
    assert probe_calls == []  # common case pays no probe cost


def test_short_body_fails():
    fetch = llms_fetch(FakeResponse(200, "hi", "text/plain"))
    s = _check_llms_txt(PARSED, fetch=fetch, probe=probe_returning(404))
    assert s.passed is False


# ---------------------------------------------------------------------------
# The PRODUCTION probe, exercised through httpx.MockTransport.
# ---------------------------------------------------------------------------

def _mock_probe(handler):
    """Run the real _probe_soft404 against an httpx.MockTransport, patching
    URL validation out (MockTransport never touches the network; production
    SSRF behavior is covered by tests/test_ssrf.py)."""
    import httpx
    from unittest import mock
    import oryon_score.score as score_mod

    transport = httpx.MockTransport(handler)
    with mock.patch.object(score_mod, "_validate_url_safety", return_value=None):
        return _probe_soft404("https://example.com" + _LLMS_PROBE_PATH,
                              _transport=transport)


def test_production_probe_does_not_follow_redirects():
    import httpx
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://example.com/"})

    result = _mock_probe(handler)
    assert result is not None
    status, ctype, head = result
    assert status == 302
    assert len(calls) == 1  # the redirect target was never fetched


def test_production_probe_requests_identity_and_refuses_encoded_bodies():
    """Codex round-5 blocker: iter_bytes is post-decode, so a small gzip bomb
    could materialize megabytes before a byte cap runs. The probe asks for
    identity and refuses any response that still declares an encoding."""
    import httpx

    seen_headers = {}

    def handler(request):
        seen_headers.update(request.headers)
        return httpx.Response(
            200,
            content=b"\x1f\x8b" + b"\x00" * 100,
            headers={"content-type": "text/plain", "content-encoding": "gzip"},
        )

    assert _mock_probe(handler) is None  # refused, fail closed
    assert seen_headers.get("accept-encoding") == "identity"


def test_production_probe_reads_at_most_sniff_bytes():
    import httpx

    big = b"x" * (_LLMS_PROBE_SNIFF_BYTES * 50)

    def handler(request):
        return httpx.Response(200, content=big, headers={"content-type": "text/plain"})

    result = _mock_probe(handler)
    assert result is not None
    status, ctype, head = result
    assert status == 200
    assert len(head) <= _LLMS_PROBE_SNIFF_BYTES


def test_production_probe_deadline_bounds_slow_drip():
    """A generator dripping bytes must be cut off near the wall-clock deadline
    — not read to the end."""
    import time as _time
    import httpx

    def dripping_body():
        for _ in range(200):
            _time.sleep(0.05)
            yield b"a" * 10

    def handler(request):
        return httpx.Response(200, content=dripping_body(),
                              headers={"content-type": "text/plain"})

    start = _time.monotonic()
    result = _mock_probe(handler)
    elapsed = _time.monotonic() - start
    assert elapsed < _LLMS_PROBE_WALL_CLOCK_S + 2.0, f"probe ran {elapsed:.1f}s"
    # Round-6 rule: evidence that outlives the deadline is EXPIRED and must be
    # None (fail closed) — never a partial tuple a pass branch could score.
    assert result is None


def test_production_probe_skips_body_for_non_2xx():
    import httpx
    body_reads = {"n": 0}

    def gen():
        body_reads["n"] += 1
        yield b"should never be read"

    def handler(request):
        return httpx.Response(403, content=gen(), headers={"content-type": "text/html"})

    result = _mock_probe(handler)
    assert result is not None
    status, ctype, head = result
    assert status == 403 and head == ""
    assert body_reads["n"] == 0  # the body generator was never consumed


def test_production_probe_never_raises_on_transport_error():
    import httpx

    def handler(request):
        raise httpx.ConnectError("boom")

    assert _mock_probe(handler) is None


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

def test_weight_is_untouched_in_every_branch():
    branches = [
        (llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain")), probe_returning(404)),
        (llms_fetch(FakeResponse(200, FALLBACK_HTML, "text/html")), probe_returning(404)),
        (llms_fetch(FakeResponse(404, "")), probe_returning(404)),
        (llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain")), probe_failing),
        (llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain")), probe_returning(503)),
        (llms_fetch(FakeResponse(200, REAL_LLMS, "text/plain")), probe_returning(302)),
    ]
    for fetch, probe in branches:
        s = _check_llms_txt(PARSED, fetch=fetch, probe=probe)
        assert s.weight == 3
        assert s.points in (0, 3)
        assert s.bucket == "crawlability"
        assert s.name == "llms.txt file"


def test_version_is_consistent():
    """Codex round-1 finding: __init__ and pyproject disagreed."""
    import oryon_score
    root = pathlib.Path(__file__).resolve().parent.parent
    pyproject = (root / "pyproject.toml").read_text()
    assert f'version = "{oryon_score.__version__}"' in pyproject


# ---------------------------------------------------------------------------
# Copy honesty: the overclaiming strings must never come back — in the code,
# the README, or the committed sample output.
# ---------------------------------------------------------------------------

BANNED_COPY = (
    "highest-correlation",
    "Required for most AI Overview citations",
    "Heavily lifted by AI summarizers",
)

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _is_quoted_debunk(line: str, phrase: str) -> bool:
    """The changelog may quote an old phrase while documenting its removal.
    Allowed ONLY when the phrase sits directly inside quotation marks AND the
    line explicitly says it's gone. A line merely mentioning 'removed'
    somewhere while asserting the claim unquoted does not qualify."""
    import re
    directly_quoted = re.search(r'["“]' + re.escape(phrase), line) is not None
    says_gone = any(m in line.lower() for m in ("are gone", "removed", "no longer"))
    return directly_quoted and says_gone


def test_no_overclaiming_copy_anywhere():
    targets = [
        ROOT / "oryon_score" / "score.py",
        ROOT / "README.md",
        ROOT / "examples" / "example_output.json",
    ]
    offenders = []
    for path in targets:
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            for phrase in BANNED_COPY:
                if phrase in line and not _is_quoted_debunk(line, phrase):
                    offenders.append(f"{path.name}:{lineno}: {phrase!r}")
    assert not offenders, (
        "Overclaiming copy is back — these promises contradict Google's docs "
        f"and the only controlled study: {offenders}"
    )


def test_example_output_is_valid_json():
    json.loads((ROOT / "examples" / "example_output.json").read_text())


def test_production_probe_expired_evidence_is_never_returned():
    """Codex round-6 blocker: a chunk arriving after the deadline must yield
    None (fail closed) — not a valid-looking tuple that the HTML branch can
    score. Reproduction shape: slow HTML fallback."""
    import time as _time
    import httpx
    from unittest import mock
    import oryon_score.score as score_mod

    def slow_html_body():
        _time.sleep(0.3)  # past the shrunken deadline below
        yield b"<html><body>fallback</body></html>"

    def handler(request):
        return httpx.Response(200, content=slow_html_body(),
                              headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    with mock.patch.object(score_mod, "_validate_url_safety", return_value=None), \
         mock.patch.object(score_mod, "_LLMS_PROBE_WALL_CLOCK_S", 0.05):
        result = score_mod._probe_soft404(
            "https://example.com" + _LLMS_PROBE_PATH, _transport=transport)
    assert result is None


def test_production_probe_buffers_at_most_sniff_bytes():
    """Codex round-6 nit: a single raw read can be 64KB+; the probe must not
    BUFFER past the cap, not merely slice afterwards."""
    import httpx
    from unittest import mock
    import oryon_score.score as score_mod

    big = b"x" * (_LLMS_PROBE_SNIFF_BYTES * 50)

    def handler(request):
        return httpx.Response(200, content=big, headers={"content-type": "text/plain"})

    transport = httpx.MockTransport(handler)
    with mock.patch.object(score_mod, "_validate_url_safety", return_value=None):
        result = score_mod._probe_soft404(
            "https://example.com" + _LLMS_PROBE_PATH, _transport=transport)
    assert result is not None
    assert len(result[2]) <= _LLMS_PROBE_SNIFF_BYTES
