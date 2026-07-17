"""
Oryon AI Search Readiness Score
Core scoring engine. Takes a URL, returns 0-100 score + per-signal results + fixes.

No LLM calls. No API keys. Pure HTML parsing + signal heuristics.
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Browser-like UA to get past basic bot walls (Cloudflare, etc.).
# We still identify in Accept headers + an optional X-Tool header so we're
# not pretending to be anything we're not.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "OryonAISearchScore/1.0 (+https://seoryon.com)"
)
TIMEOUT_S = 8.0  # Stay under Vercel's hobby 10s function limit, leaving time for parsing

# ============================================================================
# SSRF GUARD — see SECURITY_REVIEW.md §3.1
#
# Goal: refuse to fetch URLs that resolve to non-public addresses (cloud
# metadata, localhost, RFC1918, link-local, etc.) so the public /api/score
# endpoint and the pip CLI can't be tricked into probing internal networks.
#
# Design — three layers of defense:
#
#   1. URL-level validation (scheme allowlist + hostname blocklist + IP-range
#      check on every resolved address). Runs on the initial URL and via
#      httpx event_hooks on every redirect hop, so a public URL that 302s
#      to 169.254.169.254 is refused at the redirect target.
#
#   2. IP-PINNING against DNS rebinding (TOCTOU). After the validator
#      resolves a host's IPs and approves them, we store them in a
#      thread-local "pin map". A module-level monkey-patch of
#      socket.getaddrinfo() consults that pin map and returns ONLY the
#      validated IPs to any subsequent lookup of the same host within this
#      thread. This means httpx's own connect-time DNS lookup cannot land
#      on a freshly-rebound private IP — it sees the IPs we already approved.
#
#   3. Fail-CLOSED: if DNS fails, the address family is unrecognized, or
#      the URL parse trips, the whole request is refused with one uniform,
#      friendly user-facing message. We do not leak which check fired (a
#      hostile probe would otherwise enumerate ranges by observing errors).
# ============================================================================

_BLOCKED_NETS = (
    # IPv4
    ipaddress.ip_network("0.0.0.0/8"),         # "this network"
    ipaddress.ip_network("10.0.0.0/8"),        # private RFC1918
    ipaddress.ip_network("100.64.0.0/10"),     # CGNAT (Python's is_private misses this on 3.14)
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("169.254.0.0/16"),    # link-local — incl. 169.254.169.254 cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),     # private RFC1918
    ipaddress.ip_network("192.0.0.0/24"),      # IETF protocol assignments
    ipaddress.ip_network("192.168.0.0/16"),    # private RFC1918
    ipaddress.ip_network("198.18.0.0/15"),     # benchmark
    ipaddress.ip_network("224.0.0.0/4"),       # multicast
    ipaddress.ip_network("240.0.0.0/4"),       # reserved
    # IPv6
    ipaddress.ip_network("::/128"),            # unspecified
    ipaddress.ip_network("::1/128"),           # loopback
    ipaddress.ip_network("fc00::/7"),          # unique local
    ipaddress.ip_network("fe80::/10"),         # link-local
    ipaddress.ip_network("ff00::/8"),          # multicast
)

# Hostnames we refuse outright (independent of DNS — defense in depth).
_BLOCKED_HOSTS = frozenset({
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "metadata",
    "metadata.google.internal",
    "metadata.aws",
    "instance-data",
})

# Internal-flavored TLDs / suffixes we refuse outright.
_BLOCKED_HOST_SUFFIXES = (".internal", ".local", ".localhost", ".intranet", ".corp", ".home", ".lan")

# Uniform refusal message — friendly, no security-detail leak.
# Same string returned regardless of which check fired (don't enumerate the blocklist for hostile probes).
_REFUSAL_MSG = "We can only score public web pages — please paste a public URL."

# Thread-local pin map: host (lower-cased) → list of validated getaddrinfo
# tuples. Set by _fetch() for the duration of one fetch; consulted by the
# monkey-patched _pinning_getaddrinfo() during httpx's connect-time lookup.
# Thread-local so concurrent _fetch() calls don't interfere.
_DNS_PIN_TLS = threading.local()

# Capture the real getaddrinfo BEFORE we replace it so the validator (and
# anything else inside this module) can do unpinned lookups.
_REAL_GETADDRINFO = socket.getaddrinfo


def _pinning_getaddrinfo(host, port, *args, **kwargs):
    """
    Module-installed replacement for socket.getaddrinfo.

    If the current thread is inside an active _fetch() and has pinned the
    host, return ONLY the pre-validated address tuples — even if the real
    resolver would now return something different (DNS rebinding).

    Otherwise, fall through to the real resolver — so unrelated code paths
    in tests, the CLI, and the user's interpreter are unaffected.
    """
    pins = getattr(_DNS_PIN_TLS, "pins", None)
    if pins is not None and isinstance(host, str):
        key = host.lower().strip().rstrip(".")
        if key in pins:
            # Adapt cached tuples to the caller's requested port.
            return [
                (family, socktype, proto, canon, _replace_port(sockaddr, port))
                for (family, socktype, proto, canon, sockaddr) in pins[key]
            ]
    return _REAL_GETADDRINFO(host, port, *args, **kwargs)


def _replace_port(sockaddr, port):
    # sockaddr is (host, port) for IPv4 or (host, port, flowinfo, scope_id) for IPv6.
    if port is None:
        port = 0
    if len(sockaddr) == 2:
        return (sockaddr[0], port)
    return (sockaddr[0], port) + tuple(sockaddr[2:])


# Install the patch once at import time. Idempotent: re-importing this module
# (e.g. in tests) won't re-wrap an already-patched getaddrinfo.
if socket.getaddrinfo is not _pinning_getaddrinfo:
    socket.getaddrinfo = _pinning_getaddrinfo


class _SSRFBlocked(httpx.HTTPError):
    """Raised by the event hook when an outbound request would target a non-public address."""
    def __init__(self) -> None:
        super().__init__(_REFUSAL_MSG)


def _ip_is_blocked(ip: ipaddress._BaseAddress) -> bool:
    # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) before checking ranges.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _BLOCKED_NETS)


def _validate_url_safety(url: str, pin_into: dict | None = None) -> str | None:
    """
    Return None if the URL is safe to fetch, else a uniform refusal reason.

    Checks (in order):
      1. Scheme allowlist: http / https only.
      2. Hostname blocklist + suffix blocklist.
      3. DNS resolution → every resolved IP must clear _BLOCKED_NETS.

    When `pin_into` is provided, the validated address tuples are written to
    `pin_into[host_lower]`. The thread-local _DNS_PIN_TLS.pins dict is the
    intended target — once populated, the monkey-patched getaddrinfo returns
    ONLY these validated addresses to httpx's connect-time DNS lookup, which
    closes the DNS-rebind TOCTOU window.

    Fails CLOSED: any parse / DNS error → refusal.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return _REFUSAL_MSG

    if parsed.scheme not in ("http", "https"):
        return _REFUSAL_MSG

    host = parsed.hostname
    if not host:
        return _REFUSAL_MSG

    host_l = host.lower().strip().rstrip(".")
    if host_l in _BLOCKED_HOSTS or host_l.endswith(_BLOCKED_HOST_SUFFIXES):
        return _REFUSAL_MSG

    # If the host is a literal IP, check directly (skip DNS).
    try:
        literal = ipaddress.ip_address(host_l)
        if _ip_is_blocked(literal):
            return _REFUSAL_MSG
        # No DNS to pin for a literal — httpx will just use the IP directly.
        return None
    except ValueError:
        pass  # not a literal IP, fall through to DNS

    # Resolve via the REAL resolver (not our pinning shim) so we get fresh
    # ground truth, then validate every record.
    try:
        infos = _REAL_GETADDRINFO(host_l, None, type=socket.SOCK_STREAM)
    except (socket.gaierror, OSError, UnicodeError):
        return _REFUSAL_MSG

    if not infos:
        return _REFUSAL_MSG

    for _family, _socktype, _proto, _canonname, sockaddr in infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return _REFUSAL_MSG  # unparseable address → fail closed
        if _ip_is_blocked(ip):
            return _REFUSAL_MSG

    # All addresses approved — pin them so httpx's connect-time lookup
    # returns ONLY these, even if DNS has since been re-poisoned.
    if pin_into is not None:
        pin_into[host_l] = infos

    return None


def _ssrf_guard(request: httpx.Request) -> None:
    """
    httpx event hook — runs on every outbound request, including each
    redirect hop. Validates the new target, and (when called from inside
    _fetch) pins the validated IPs so httpx's own connect-time DNS lookup
    cannot land on a rebound private address.
    """
    pins = getattr(_DNS_PIN_TLS, "pins", None)
    reason = _validate_url_safety(str(request.url), pin_into=pins)
    if reason is not None:
        raise _SSRFBlocked()


# AI crawler user agents we check robots.txt against
AI_CRAWLERS = [
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "CCBot",
    "Google-Extended",
    "Applebot-Extended",
    "Bytespider",
    "anthropic-ai",
    "FacebookBot",
]

# 5 buckets that add up to 100
WEIGHTS = {
    "schema_structure": 30,
    "content_format": 25,
    "authority": 20,
    "crawlability": 15,
    "freshness": 10,
}


@dataclass
class SignalResult:
    name: str
    bucket: str
    passed: bool
    weight: float                 # points possible if signal == binary; or weight share within bucket
    points: float                 # actual points earned (0..weight)
    detail: str
    fix: str | None = None        # 1-line actionable fix when failed


@dataclass
class ScoreResult:
    url: str
    score: int                    # 0-100
    grade: str                    # A+ A B C D F
    fetched_at: str
    page_title: str | None
    bucket_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    signals: list[SignalResult] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["signals"] = [asdict(s) for s in self.signals]
        return d


def _grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "F"


def _norm_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


_REQUEST_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "X-Tool": "OryonAISearchScore/1.0",
}


def _fetch(url: str) -> tuple[httpx.Response | None, str | None]:
    headers = _REQUEST_HEADERS
    # Install a fresh per-fetch IP-pin map. _validate_url_safety() writes
    # validated address tuples into it; the monkey-patched getaddrinfo reads
    # from it. This is what closes the DNS-rebind TOCTOU window.
    pins: dict = {}
    # Pre-validate the initial URL so we never open a TCP connection to a
    # blocked target — even before the event hook fires.
    reason = _validate_url_safety(url, pin_into=pins)
    if reason is not None:
        return None, reason
    _DNS_PIN_TLS.pins = pins
    try:
        # event_hooks fires on the initial request AND on every redirect hop,
        # which closes the "public URL 302-redirects to 169.254.169.254" bypass.
        # The hook re-validates AND re-pins each new host, so httpx's
        # connect-time DNS lookup also lands on a pre-approved IP.
        with httpx.Client(
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers=headers,
            event_hooks={"request": [_ssrf_guard]},
        ) as client:
            r = client.get(url)
        if r.status_code >= 400:
            sc = r.status_code
            if sc == 404:
                msg = f"HTTP 404 — that URL doesn't exist. Double-check the path."
            elif sc in (401, 403):
                msg = f"HTTP {sc} — the site blocked our request (bot protection / paywall / login required)."
            elif sc == 429:
                msg = f"HTTP 429 — rate-limited. Wait a minute and try again."
            elif sc >= 500:
                msg = f"HTTP {sc} — the site is broken right now. Try again later."
            else:
                msg = f"HTTP {sc} {r.reason_phrase}"
            return None, msg
        return r, None
    except _SSRFBlocked:
        # Friendly refusal — same message for every blocked-target reason
        # (don't enumerate the blocklist back to a hostile prober).
        return None, _REFUSAL_MSG
    except httpx.HTTPError as e:
        return None, f"Fetch failed: {e!s}"
    finally:
        # Always clear the pin so unrelated code (other Python in this
        # thread) sees the real resolver again.
        _DNS_PIN_TLS.pins = None


def _fetch_text(url: str) -> str:
    r, _ = _fetch(url)
    if r is None or r.status_code >= 400:
        return ""
    return r.text


# ============ SIGNAL CHECKS ============

def _check_https(parsed_url) -> SignalResult:
    ok = parsed_url.scheme == "https"
    return SignalResult(
        name="HTTPS",
        bucket="crawlability",
        passed=ok,
        weight=2,
        points=2 if ok else 0,
        detail="Served over HTTPS." if ok else "Page is not HTTPS.",
        fix=None if ok else "Move the site to HTTPS — AI crawlers and Google demote http URLs.",
    )


def _check_canonical(soup: BeautifulSoup, url: str) -> SignalResult:
    tag = soup.find("link", attrs={"rel": "canonical"})
    if not tag or not tag.get("href"):
        return SignalResult(
            "Canonical URL", "crawlability", False, 2, 0,
            "No canonical link tag found.",
            "Add a `<link rel=\"canonical\" href=\"...\">` to lock the canonical URL for this page.",
        )
    return SignalResult(
        "Canonical URL", "crawlability", True, 2, 2,
        f"Canonical: {tag['href']}", None,
    )


def _check_viewport(soup: BeautifulSoup) -> SignalResult:
    tag = soup.find("meta", attrs={"name": "viewport"})
    ok = bool(tag and tag.get("content"))
    return SignalResult(
        "Mobile viewport", "crawlability", ok, 2, 2 if ok else 0,
        "Mobile viewport meta present." if ok else "No mobile viewport meta tag.",
        None if ok else "Add `<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">` to head.",
    )


def _check_open_graph(soup: BeautifulSoup) -> SignalResult:
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
    ok = len(og_tags) >= 3
    return SignalResult(
        "Open Graph tags", "crawlability", ok, 2, 2 if ok else 0,
        f"Found {len(og_tags)} og:* tags." if og_tags else "No Open Graph tags.",
        None if ok else "Add og:title, og:description, og:image, og:url — AI summarizers lift them.",
    )


_LLMS_PROBE_PATH = "/oryon-soft404-probe-do-not-create.txt"
# Soft-404 control path for the llms.txt check. Deliberately weird so no real
# site has a file there; anything answering 200 for it answers 200 for
# everything. (A site could special-case this exact path to game the check —
# but anyone with that much control could just create a real llms.txt.)

_LLMS_PROBE_TIMEOUT_S = 3.0     # httpx per-phase timeout inside the probe
_LLMS_PROBE_WALL_CLOCK_S = 4.0  # hard deadline across the whole probe call
_LLMS_PROBE_SNIFF_BYTES = 4096  # the probe only ever needs enough to sniff

# Probe statuses that genuinely mean "this path does not exist here". Anything
# else >= 400 (401/403/429/5xx) proves nothing about llms.txt authenticity and
# fails closed — a throttled, WAF-guarded, or erroring probe is not a
# verification.
_PROBE_ABSENCE_STATUSES = frozenset({404, 410})


def _probe_soft404(url: str, _transport=None) -> tuple[int, str, str] | None:
    """Fetch the soft-404 control path with hard, authoritative resource bounds.

    Returns (status_code, content_type, body_head) or None on ANY failure —
    SSRF refusal, DNS error, timeout, deadline, unexpected content-encoding,
    anything. The caller treats None as "could not verify" and fails closed,
    so this function must never raise.

    The probe's only jobs are: report the status of a nonsense path, and carry
    enough of the body to sniff HTML. It therefore reads AT MOST
    _LLMS_PROBE_SNIFF_BYTES and only for 2xx responses. Bound mechanics, each
    chosen against a specific reproduced bypass:
      - follow_redirects=False: intermediate redirect bodies would be read in
        full outside our loop. A redirect IS a probe result.
      - Accept-Encoding: identity, and any response that still declares a
        content-encoding is refused: iter_bytes() is post-decode, so a 2KB
        gzip bomb could materialize megabytes before a byte-capped loop runs.
        With identity encoding, raw bytes ARE the body.
      - iter_raw() with no chunk_size yields each network read as it arrives,
        so a slow drip hits the deadline check on every arrival instead of
        starving a rechunking buffer.
      - The wall-clock deadline starts before URL validation/DNS, and is
        checked after headers and per raw chunk.
    `_transport` is a test seam (httpx.MockTransport); production passes None.
    """
    try:
        deadline = time.monotonic() + _LLMS_PROBE_WALL_CLOCK_S
        pins: dict = {}
        if _validate_url_safety(url, pin_into=pins) is not None:
            return None
        _DNS_PIN_TLS.pins = pins
        try:
            headers = dict(_REQUEST_HEADERS)
            headers["Accept-Encoding"] = "identity"
            client_kwargs: dict = {
                "timeout": _LLMS_PROBE_TIMEOUT_S,
                "follow_redirects": False,
                "headers": headers,
                "event_hooks": {"request": [_ssrf_guard]},
            }
            if _transport is not None:
                client_kwargs["transport"] = _transport
            with httpx.Client(**client_kwargs) as client:
                with client.stream("GET", url) as r:
                    status = r.status_code
                    ctype = (r.headers.get("content-type") or "").lower()
                    if time.monotonic() > deadline:
                        return None
                    if not (200 <= status < 300):
                        # Body irrelevant for non-2xx probe results.
                        return status, ctype, ""
                    if (r.headers.get("content-encoding") or "").strip().lower() not in ("", "identity"):
                        # Server ignored identity — refuse rather than decode.
                        return None
                    chunks: list[bytes] = []
                    total = 0
                    try:
                        for chunk in r.iter_raw():
                            # Deadline expiry means the evidence took too long
                            # to arrive — expired evidence must NEVER be
                            # scored, so this is None (fail closed), not a
                            # break-and-return. Only the byte cap breaks: a
                            # full sniff window read in time is complete
                            # evidence.
                            if time.monotonic() > deadline:
                                return None
                            # Keep only what the sniff needs — a single raw
                            # network read can be 64KB+; don't buffer past
                            # the cap.
                            needed = _LLMS_PROBE_SNIFF_BYTES - total
                            chunks.append(chunk[:needed])
                            total += min(len(chunk), needed)
                            if total >= _LLMS_PROBE_SNIFF_BYTES:
                                break
                    except httpx.StreamConsumed:
                        # Preloaded responses (e.g. MockTransport byte content)
                        # can't be re-streamed; their body is already in memory.
                        chunks = [r.content[:_LLMS_PROBE_SNIFF_BYTES]]
                    if time.monotonic() > deadline:
                        return None
            head = b"".join(chunks)[:_LLMS_PROBE_SNIFF_BYTES].decode("utf-8", "replace")
            return status, ctype, head
        finally:
            _DNS_PIN_TLS.pins = None
    except Exception:
        return None


# HTML "ASCII whitespace" plus the BOM — everything a browser skips before the
# first tag. \f (form feed) and \v included; omitting \f was a reproduced bypass.
_LEADING_JUNK = "\ufeff \t\r\n\f\v"


def _looks_like_html(text: str) -> bool:
    # Starts-with only, deliberately: fallback/error pages virtually always open
    # with a tag ("<!doctype", "<html", "<div", "<script", ...), while a real
    # llms.txt is markdown and opens with "# " (H1 first, per llmstxt.org).
    # A markdown body that merely *mentions* "<html" mid-text must NOT be
    # rejected. Junk is stripped BEFORE slicing, so padding cannot push the
    # tag past the window.
    head = text.lstrip(_LEADING_JUNK)[:64].lower()
    return head.startswith("<")


def _check_llms_txt(parsed_url, fetch=None, probe=None) -> SignalResult:
    # A 200 alone proves nothing: SPA hosts serve their index.html for every
    # missing path, so the old `200 and len > 50` check awarded 3/3 phantom
    # credit to sites whose /llms.txt has never existed. Gates, in order:
    #   1. 200 + non-trivial body.
    #   2. Text content: content-type must be text/* (or absent) and never
    #      text/html; body must not open like markup.
    #   3. Soft-404 control probe (resource-bounded, single hop, never raises):
    #        - 404/410           -> path genuinely absent -> verification PASSES
    #        - 3xx, and llms.txt was served WITHOUT redirects -> catch-all
    #                               redirects unknown paths while llms.txt
    #                               answers directly -> distinct handlers -> PASSES
    #        - 3xx, but llms.txt itself arrived via redirects -> same handler
    #                               class -> can't distinguish -> FAIL CLOSED
    #        - other >= 400      -> WAF/throttle/error -> can't verify -> FAIL CLOSED
    #        - transport failure -> can't verify -> FAIL CLOSED
    #        - 2xx HTML-ish      -> SPA shell for unknown paths while llms.txt
    #                               is text -> distinct handlers -> PASSES
    #        - 2xx anything else -> the site 200s arbitrary paths with
    #                               non-HTML content; a "real" llms.txt is
    #                               indistinguishable from that catch-all
    #                               (near-identical or not — both score zero,
    #                               so no content comparison is needed) -> FAIL CLOSED
    #        - anything else (1xx, malformed result) -> FAIL CLOSED
    fetch = fetch or _fetch
    probe = probe or _probe_soft404
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"
    name, bucket, weight = "llms.txt file", "crawlability", 3
    fix = "Add a real /llms.txt file (text/plain, llmstxt.org spec) at the site root."

    r, _ = fetch(f"{base}/llms.txt")
    if r is None or r.status_code != 200 or len(r.text) <= 50:
        return SignalResult(name, bucket, False, weight, 0, "No /llms.txt found.", fix)

    ctype = (r.headers.get("content-type") or "").lower()
    if "text/html" in ctype or _looks_like_html(r.text):
        return SignalResult(
            name, bucket, False, weight, 0,
            "The /llms.txt URL returns an HTML page — almost always the site's "
            "fallback page for missing paths, not a real llms.txt.",
            fix + " An HTML fallback page doesn't count.",
        )
    if ctype and not ctype.startswith("text/"):
        return SignalResult(
            name, bucket, False, weight, 0,
            f"The /llms.txt URL returns content-type {ctype.split(';')[0]!r} — "
            "a real llms.txt is a plain-text (markdown) file.",
            fix,
        )

    # Only candidate passes pay for the control probe, so the common case
    # (no llms.txt -> 404) costs no extra fetch. The whole probe interaction —
    # call, shape validation, typing — sits inside one fail-closed boundary:
    # a malformed result from an injected probe must degrade to "could not
    # verify", never to a crash.
    probe_status = probe_ctype = probe_head = None
    try:
        result = probe(f"{base}{_LLMS_PROBE_PATH}")
        # Strict shape: exactly (int, str, str) in a tuple. Coercion would let
        # a malformed result (a list, a float status) sneak into a pass branch.
        if (
            isinstance(result, tuple)
            and len(result) == 3
            and type(result[0]) is int
            and isinstance(result[1], str)
            and isinstance(result[2], str)
        ):
            probe_status = result[0]
            probe_ctype = result[1].lower()
            probe_head = result[2]
    except Exception:
        probe_status = None
    if probe_status is None:
        return SignalResult(
            name, bucket, False, weight, 0,
            "Found a plain-text /llms.txt, but the soft-404 control probe failed "
            "(network error or deadline), so it can't be distinguished from a "
            "catch-all response. Not scored — re-run to verify.",
            fix + " (Could not verify this attempt; transient — re-running may succeed.)",
        )
    if probe_status in _PROBE_ABSENCE_STATUSES:
        return SignalResult(
            name, bucket, True, weight, 3,
            "llms.txt present at site root (plain text; unknown paths correctly "
            "return not-found).",
            None,
        )
    if 300 <= probe_status < 400:
        # Only distinct if the llms.txt itself was served WITHOUT redirects —
        # _fetch follows redirects silently, so consult response.history.
        if getattr(r, "history", None):
            return SignalResult(
                name, bucket, False, weight, 0,
                "Both /llms.txt and unknown paths respond with redirects on this "
                "site, so a real file can't be distinguished from a redirecting "
                "catch-all. Not scored.",
                fix + " Serve /llms.txt directly (no redirect) so it is verifiable.",
            )
        return SignalResult(
            name, bucket, True, weight, 3,
            "llms.txt present at site root (plain text, served directly while "
            "unknown paths redirect).",
            None,
        )
    if probe_status >= 400:
        return SignalResult(
            name, bucket, False, weight, 0,
            f"Found a plain-text /llms.txt, but this site answers unknown paths "
            f"with HTTP {probe_status} (a WAF or security layer, not a clean 404), "
            "so a real file can't be distinguished from a protected fallback. Not scored.",
            fix + " Make unknown paths return 404 so a real llms.txt is verifiable.",
        )
    if 200 <= probe_status < 300:
        if "text/html" in probe_ctype or _looks_like_html(probe_head):
            return SignalResult(
                name, bucket, True, weight, 3,
                "llms.txt present at site root (plain text, distinct from the "
                "site's HTML fallback for unknown paths).",
                None,
            )
        return SignalResult(
            name, bucket, False, weight, 0,
            "This site serves 200 non-HTML responses for arbitrary paths, so the "
            "/llms.txt response can't be distinguished from a catch-all. Not scored.",
            fix + " Make unknown paths return 404 so a real llms.txt is verifiable.",
        )
    # 1xx or anything unclassified: no evidence either way.
    return SignalResult(
        name, bucket, False, weight, 0,
        f"The soft-404 control probe returned an unexpected HTTP {probe_status}, "
        "so llms.txt authenticity can't be verified. Not scored.",
        fix + " (Could not verify this attempt; ambiguity is not scored.)",
    )


def _check_robots_ai(parsed_url) -> SignalResult:
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"
    r, _ = _fetch(f"{base}/robots.txt")
    if r is None or r.status_code != 200:
        return SignalResult(
            "Robots allows AI crawlers", "crawlability", True, 4, 4,
            "No robots.txt — AI crawlers can fetch by default.", None,
        )
    text = r.text.lower()
    blocked = []
    for bot in AI_CRAWLERS:
        pat = re.compile(
            rf"user-agent:\s*{re.escape(bot.lower())}\s*\n((?:[a-z-]+:.*\n?)+)",
            re.IGNORECASE,
        )
        for m in pat.finditer(text):
            block = m.group(1)
            if re.search(r"disallow:\s*/(\s|$)", block):
                blocked.append(bot)
                break
    if blocked:
        return SignalResult(
            "Robots allows AI crawlers", "crawlability", False, 4, max(0, 4 - len(blocked)),
            f"Blocking these AI crawlers via robots.txt: {', '.join(blocked)}.",
            f"Remove the Disallow rules for: {', '.join(blocked)} unless intentional. AI overviews need access to cite you.",
        )
    return SignalResult(
        "Robots allows AI crawlers", "crawlability", True, 4, 4,
        "All major AI crawlers allowed in robots.txt.", None,
    )


# Schema & structure
def _extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend([d for d in data if isinstance(d, dict)])
    return out


def _schema_types(jsonld: list[dict]) -> set[str]:
    types: set[str] = set()
    for entry in jsonld:
        graph = entry.get("@graph", [entry]) if "@graph" in entry else [entry]
        for node in graph:
            t = node.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                types.update(str(x) for x in t)
    return types


def _check_article_schema(types: set[str]) -> SignalResult:
    has = bool(types & {"Article", "NewsArticle", "BlogPosting", "TechArticle"})
    return SignalResult(
        "Article schema", "schema_structure", has, 5, 5 if has else 0,
        f"Article-type schema present: {sorted(types & {'Article', 'NewsArticle', 'BlogPosting', 'TechArticle'})}" if has
        else "No Article / BlogPosting / NewsArticle schema found.",
        None if has else "Add JSON-LD with @type: Article (or BlogPosting) — a machine-readable statement of what this page is, who wrote it, and when it changed.",
    )


def _check_faq_schema(types: set[str]) -> SignalResult:
    has = "FAQPage" in types
    return SignalResult(
        "FAQ schema", "schema_structure", has, 6, 6 if has else 0,
        "FAQPage JSON-LD present." if has else "No FAQPage schema.",
        None if has else "If the page has a visible FAQ section, mirror it in FAQPage JSON-LD so the Q&A is machine-readable. No rich-result promise — Google restricted FAQ rich results to government and health sites in 2023 and removed them for all sites in May 2026.",
    )


def _check_howto_schema(types: set[str]) -> SignalResult:
    has = "HowTo" in types
    return SignalResult(
        "HowTo schema", "schema_structure", has, 3, 3 if has else 0,
        "HowTo schema present." if has else "No HowTo schema.",
        None if has else "If the page documents real steps, mirror them in HowTo JSON-LD so the sequence is machine-readable. HowTo rich results are gone — the value is unambiguous extraction, not a SERP feature.",
    )


def _check_breadcrumb_schema(types: set[str]) -> SignalResult:
    has = "BreadcrumbList" in types
    return SignalResult(
        "Breadcrumb schema", "schema_structure", has, 3, 3 if has else 0,
        "BreadcrumbList schema present." if has else "No BreadcrumbList schema.",
        None if has else "Add BreadcrumbList JSON-LD — helps AI understand site hierarchy.",
    )


def _check_heading_structure(soup: BeautifulSoup) -> SignalResult:
    # Count semantic h1s + ARIA-level-1 headings (modern frameworks often do <div role="heading" aria-level="1">)
    h1s = soup.find_all("h1")
    aria_h1s = soup.find_all(attrs={"role": "heading", "aria-level": "1"})
    h2s = soup.find_all("h2") + soup.find_all(attrs={"role": "heading", "aria-level": "2"})
    h1_count = len(h1s) + len(aria_h1s)
    h2_count = len(h2s)

    # Many modern pages style the title with CSS instead of <h1>. If we found a title tag,
    # treat that as the implicit primary heading.
    if h1_count == 0 and soup.find("title"):
        h1_count = 1
        detail_h1 = "(no explicit <h1>; using <title> as implicit primary heading)"
    else:
        detail_h1 = ""

    if h1_count == 1 and h2_count >= 3:
        return SignalResult(
            "Heading structure", "schema_structure", True, 4, 4,
            f"1 H1, {h2_count} H2s. Clean hierarchy. {detail_h1}".strip(), None,
        )
    fix = []
    if h1_count == 0:
        fix.append("No H1 detected. Add exactly one <h1> with the page's primary title.")
    elif h1_count > 1:
        fix.append(f"{h1_count} H1 tags found — should be exactly one.")
    if h2_count < 3:
        fix.append(f"Only {h2_count} H2s. AI extractors chunk by H2 — add more sectioning.")
    partial = 2 if (h1_count >= 1 and h2_count >= 2) else 1
    return SignalResult(
        "Heading structure", "schema_structure", False, 4, partial,
        f"{h1_count} H1, {h2_count} H2s. {detail_h1}".strip(),
        " ".join(fix) if fix else "Improve heading hierarchy.",
    )


def _check_definition_lists(soup: BeautifulSoup) -> SignalResult:
    dl = soup.find_all("dl")
    ok = len(dl) >= 1
    return SignalResult(
        "Definition lists", "schema_structure", ok, 3, 3 if ok else 0,
        f"{len(dl)} `<dl>` elements." if ok else "No definition lists.",
        None if ok else "Use `<dl><dt>term</dt><dd>definition</dd></dl>` for glossary-style content — strong lift signal.",
    )


def _check_tables(soup: BeautifulSoup) -> SignalResult:
    tables = soup.find_all("table")
    ok = len(tables) >= 1
    return SignalResult(
        "Table markup", "schema_structure", ok, 3, 3 if ok else 0,
        f"{len(tables)} `<table>` element(s)." if ok else "No tables.",
        None if ok else "Comparison data deserves real `<table>` markup, not images of tables. AI lifts these.",
    )


def _check_question_h2s(soup: BeautifulSoup) -> SignalResult:
    h2s = soup.find_all("h2")
    q_count = sum(1 for h in h2s if h.get_text(strip=True).rstrip().endswith("?"))
    ok = q_count >= 2
    return SignalResult(
        "Question-style H2s", "schema_structure", ok, 3, min(3, q_count),
        f"{q_count} H2s end with a question mark." if q_count else "No question-style H2s.",
        None if ok else "Convert ≥2 H2s to actual user questions. AI Overviews extract Q&A patterns disproportionately.",
    )


# Content / format
def _word_count(soup: BeautifulSoup) -> int:
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return len(re.findall(r"\b\w+\b", text))


def _check_word_count(wc: int) -> SignalResult:
    if 1200 <= wc <= 3500:
        return SignalResult(
            "Word count (lift-worthy range)", "content_format", True, 5, 5,
            f"{wc} words — in the lift-worthy range (1200–3500).", None,
        )
    if 800 <= wc < 1200 or 3500 < wc <= 5000:
        return SignalResult(
            "Word count (lift-worthy range)", "content_format", False, 5, 2,
            f"{wc} words — outside the sweet spot (1200–3500).",
            "Aim for 1500–2500 words. Thin pages and bloated pages both lose extraction priority.",
        )
    return SignalResult(
        "Word count (lift-worthy range)", "content_format", False, 5, 0,
        f"{wc} words — too {'thin' if wc < 800 else 'long'}.",
        "Aim for 1500–2500 words with one clear answer per section.",
    )


def _check_first_paragraph_answer(soup: BeautifulSoup) -> SignalResult:
    article = soup.find("article") or soup.find("main") or soup.body
    if not article:
        return SignalResult(
            "Answer in first 60 words", "content_format", False, 5, 0,
            "Could not detect a main content region.",
            "Wrap the article body in `<article>` or `<main>` for clean extraction.",
        )
    # Skip empty / very-short paragraphs (captions, bylines, image text) before finding the real first paragraph
    first_text = ""
    first_word_n = 0
    for p in article.find_all("p"):
        text = p.get_text(strip=True)
        if not text:
            continue
        words = re.findall(r"\b\w+\b", text)
        if len(words) < 8:
            continue
        first_text = text
        first_word_n = len(words)
        break

    if first_word_n == 0:
        return SignalResult(
            "Answer in first 60 words", "content_format", False, 5, 0,
            "No non-trivial first paragraph found in main content.",
            "Open with a real <p> of 15–60 words that directly answers the page's question.",
        )

    ok = 15 <= first_word_n <= 60 and first_text.endswith((".", "!", "?"))
    return SignalResult(
        "Answer in first 60 words", "content_format", ok, 5,
        5 if ok else (2 if first_word_n >= 15 else 1),
        f"First real paragraph: {first_word_n} words." if ok
        else f"First real paragraph is {first_word_n} words — outside the AI-lift sweet spot of 15–60.",
        None if ok else "Cut the intro. The first paragraph should be a 15–60 word direct answer to the page's core question.",
    )


def _check_tldr(soup: BeautifulSoup) -> SignalResult:
    text = soup.get_text(separator=" ", strip=True).lower()
    has = bool(re.search(r"\btl;dr\b|\btldr\b|\bin short\b|\bsummary\b", text[:2000]))
    return SignalResult(
        "TL;DR / summary block near top", "content_format", has, 5, 5 if has else 0,
        "TL;DR or summary detected near the top of the page." if has else "No TL;DR or summary block found.",
        None if has else "Add a 50-word TL;DR after the H1. AI summarizers lift TL;DR blocks at much higher rates.",
    )


def _check_bold_answer(soup: BeautifulSoup) -> SignalResult:
    article = soup.find("article") or soup.find("main") or soup.body
    if not article:
        return SignalResult("Bold answer in first section", "content_format", False, 5, 0,
                            "No main content region detected.", None)
    first_p = article.find("p")
    if not first_p:
        return SignalResult("Bold answer in first section", "content_format", False, 5, 0,
                            "No paragraph found.", None)
    has_bold = bool(first_p.find(["strong", "b"]))
    return SignalResult(
        "Bold answer in first section", "content_format", has_bold, 5, 5 if has_bold else 0,
        "First paragraph contains a `<strong>` or `<b>` tag." if has_bold
        else "First paragraph has no bold emphasis.",
        None if has_bold else "Bold the literal answer in the first paragraph. Visual emphasis = extraction signal.",
    )


def _check_lists(soup: BeautifulSoup) -> SignalResult:
    lists = soup.find_all(["ol", "ul"])
    ok = len(lists) >= 3
    return SignalResult(
        "Structured lists", "content_format", ok, 5, min(5, len(lists)),
        f"{len(lists)} list elements." if lists else "No ordered/unordered lists.",
        None if ok else "Use real list markup (3+ ol/ul) — AI Overviews favor structured enumeration.",
    )


# Authority
def _check_external_authority_links(soup: BeautifulSoup, page_host: str) -> SignalResult:
    links = soup.find_all("a", href=True)
    external_auth = 0
    auth_tlds = (".gov", ".edu", ".ac.uk", "wikipedia.org")
    for a in links:
        try:
            href = a["href"]
            if not href.startswith("http"):
                continue
            host = urlparse(href).netloc.lower()
            if host == page_host:
                continue
            if any(host.endswith(t) for t in auth_tlds):
                external_auth += 1
        except (KeyError, ValueError):
            continue
    ok = external_auth >= 2
    return SignalResult(
        "Authority outbound links", "authority", ok, 5, min(5, external_auth),
        f"{external_auth} link(s) to .gov / .edu / Wikipedia." if external_auth
        else "No outbound links to authority domains.",
        None if ok else "Cite 2+ authority sources (.gov, .edu, Wikipedia). Provenance is an extraction signal.",
    )


def _check_internal_links(soup: BeautifulSoup, page_host: str) -> SignalResult:
    links = soup.find_all("a", href=True)
    internal = 0
    for a in links:
        href = a["href"]
        if href.startswith("/") and not href.startswith("//"):
            internal += 1
        elif href.startswith("http"):
            try:
                if urlparse(href).netloc.lower() == page_host:
                    internal += 1
            except ValueError:
                continue
    ok = 5 <= internal <= 50
    return SignalResult(
        "Internal linking", "authority", ok, 4, 4 if ok else (2 if internal else 0),
        f"{internal} internal links." if internal else "No internal links detected.",
        None if ok else "5–50 internal links is the healthy range. Below = orphan; above = link soup.",
    )


# --- Named-author detection -------------------------------------------------
# A real byline names a *person*: "Jane Smith", "By A. K. Rowling", "Jane de Sousa".
# The distinguishing signal is proper-noun capitalization, which is why these
# patterns are case-SENSITIVE. The old check lowercased the whole page and matched
# `by [a-z]+ [a-z]+`, so ordinary prose like "backed by a public poll" scored a
# byline (proven live on roi.seoryon.com). We now credit an author only from
# structured data, a <meta name="author"> tag, or a byline *anchored to author
# context* — an author-marked element, or a "By <Name>" line at the head of a
# short block (a dateline/header). Arbitrary body prose never counts; ambiguity
# fails closed.
_UP = r"[^\W\d_a-z]"                       # one uppercase letter (Unicode-aware)
# A capitalized name word ("Jane", "O'Brien", "Anne-Marie"). It must END on a
# letter/digit — never on a trailing ' . or - — so "By Jane O'Brien's report"
# can't backtrack the last token down to "O'" and slip past the tail guard.
_NAME_CORE = _UP + r"(?:[\w.'’\-]*[^\W_])?"
_INITIAL = _UP + r"\."                      # a single initial, e.g. "A." in "A. K. Rowling"
_PARTICLE = r"(?:de|del|della|der|di|da|dos|van|von|la|le|bin|al)"  # nobiliary particles
# The first token is a real capitalized word or initial (not a bare particle);
# each following token may also be a nobiliary particle. 1–3 extra tokens
# guarantees at least a first + last name.
_NAME_HEAD = r"(?:" + _NAME_CORE + r"|" + _INITIAL + r")"
_NAME_TOKEN = r"(?:" + _NAME_CORE + r"|" + _INITIAL + r"|" + _PARTICLE + r")"
_AUTHOR_NAME = _NAME_HEAD + r"(?:\s+" + _NAME_TOKEN + r"){1,3}"
# Negative tail: a byline ends or is followed by a separator/date — never by a
# lowercase word or a possessive. Rejects "By Jane Smith's estimate…" (the name
# backtracks to "Jane Smith", leaving a dangling "'s") and "By December Analysts
# expect…", while keeping "By Jane Smith", "By Jane Smith · 2026", "By Jane
# O'Brien". The apostrophe alternative catches the possessive; the \s+[a-z]
# alternative catches a following lowercase word.
_BYLINE_TAIL = r"(?![’'a-z]|\s+[a-z])"
_BY = r"(?:[Ww]ritten\s+)?[Bb]y[:\s]\s*"
# "By <Name>" anchored to the start of a text block (a byline/dateline line).
_BYLINE_HEAD_RE = re.compile(r"^" + _BY + r"(" + _AUTHOR_NAME + r")" + _BYLINE_TAIL)
# "By <Name>" anywhere inside an already author-scoped element.
_BYLINE_INLINE_RE = re.compile(r"\b" + _BY + r"(" + _AUTHOR_NAME + r")" + _BYLINE_TAIL)
# A bare capitalized full name — only trusted inside author-scoped markup.
_BARE_NAME_RE = re.compile(_AUTHOR_NAME)
# class/id that names an author, without matching "authority"/"authored-*noise".
_AUTHOR_ATTR_RE = re.compile(r"byline|author(?!ity)", re.IGNORECASE)
# A byline element's own text stays short; longer text is prose, not a byline.
_BYLINE_MAX_LEN = 120
# Tags that can hold a byline line. Heading tags (h1–h6) are deliberately absent:
# real bylines don't live in headings, but Title-Case headings ("By Popular
# Demand", "By Design") would otherwise read as "By <Name>". Author-classed
# headings are still caught via the markup path.
_BYLINE_TAGS = ("p", "div", "span", "address", "header", "li", "small",
                "cite", "figcaption", "td")
# Common capitalized UI/nav bigrams that are not personal names. A "name" made up
# entirely of these is rejected, so a `rel="author"` link reading "Read More"
# doesn't score a byline.
_NON_NAME_WORDS = frozenset({
    "read", "more", "learn", "home", "page", "pages", "next", "previous", "prev",
    "back", "all", "view", "views", "share", "shares", "related", "post", "posts",
    "comment", "comments", "reply", "sign", "log", "login", "menu", "search",
    "subscribe", "newsletter", "follow", "contact", "about", "privacy", "terms",
    "cookie", "cookies", "skip", "toggle", "close", "open", "show", "hide",
    "the", "and", "our", "team", "staff", "editor", "editors", "admin",
})


def _jsonld_names_author(jsonld: list[dict]) -> bool:
    """True if any JSON-LD node carries a non-empty author."""
    for entry in jsonld:
        nodes = entry.get("@graph", [entry]) if isinstance(entry, dict) else []
        for n in nodes:
            if isinstance(n, dict) and n.get("author"):
                return True
    return False


def _meta_names_author(soup: BeautifulSoup) -> bool:
    """True if a <meta name=author> (or article:author) names someone."""
    for tag in soup.find_all("meta"):
        key = (tag.get("name") or tag.get("property") or "").strip().lower()
        if key in ("author", "article:author") and (tag.get("content") or "").strip():
            return True
    return False


def _is_author_element(tag) -> bool:
    """True if a tag is explicitly marked as author/byline context."""
    rel = tag.get("rel")
    if rel:
        rels = rel if isinstance(rel, list) else [rel]
        if any("author" in str(r).lower() for r in rels):
            return True
    itemprop = tag.get("itemprop")
    if itemprop:
        props = itemprop if isinstance(itemprop, list) else [itemprop]
        if any("author" in str(p).lower() for p in props):
            return True
    cls = tag.get("class") or []
    hay = " ".join(cls if isinstance(cls, list) else [cls]) + " " + (tag.get("id") or "")
    return bool(hay.strip()) and bool(_AUTHOR_ATTR_RE.search(hay))


def _is_person_name(name: str) -> bool:
    """Reject 'names' made only of UI/nav words ('Read More', 'View All')."""
    tokens = [t.strip(".'’-") for t in name.split() if t.strip(".'’-")]
    return any(t.lower() not in _NON_NAME_WORDS for t in tokens)


def _markup_names_author(soup: BeautifulSoup) -> bool:
    """True if author-marked markup contains a real name."""
    for tag in soup.find_all(_is_author_element):
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        m = _BYLINE_INLINE_RE.search(text)
        if m and _is_person_name(m.group(1)):
            return True
        if len(text) <= _BYLINE_MAX_LEN:
            m = _BARE_NAME_RE.search(text)
            if m and _is_person_name(m.group(0)):
                return True
    return False


def _visible_byline(soup: BeautifulSoup) -> bool:
    """True if a short block *starts with* a 'By <Name>' byline (dateline/header)."""
    for tag in soup.find_all(_BYLINE_TAGS):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > _BYLINE_MAX_LEN:
            continue
        m = _BYLINE_HEAD_RE.match(text)
        if m and _is_person_name(m.group(1)):
            return True
    return False


def _named_author_source(soup: BeautifulSoup, jsonld: list[dict]) -> str | None:
    """Return which honest source names an author, or None. Fails closed."""
    if _jsonld_names_author(jsonld):
        return "jsonld"
    if _meta_names_author(soup):
        return "meta"
    if _markup_names_author(soup):
        return "markup"
    if _visible_byline(soup):
        return "byline"
    return None


def _check_author_byline(soup: BeautifulSoup, jsonld: list[dict]) -> SignalResult:
    source = _named_author_source(soup, jsonld)
    passed = source is not None
    detail = {
        "jsonld": "Author named in JSON-LD structured data.",
        "meta": "Author named in a <meta name=\"author\"> tag.",
        "markup": "Named author found in author/byline markup.",
        "byline": "Visible \"By <Name>\" byline detected.",
    }.get(source or "",
          "No named author found — no JSON-LD/meta author, and no byline markup "
          "or \"By <Name>\" line (prose mentions of \"by …\" don't count).")
    return SignalResult(
        "Named author / byline", "authority", passed, 5, 5 if passed else 0,
        detail,
        None if passed else "Name a real author with a profile page. E-E-A-T's first E = experience, and that means a person.",
    )


def _check_external_link_density(soup: BeautifulSoup, page_host: str) -> SignalResult:
    links = soup.find_all("a", href=True)
    external = 0
    for a in links:
        href = a["href"]
        if href.startswith("http"):
            try:
                if urlparse(href).netloc.lower() != page_host:
                    external += 1
            except ValueError:
                continue
    ok = 3 <= external <= 30
    return SignalResult(
        "Outbound link density", "authority", ok, 3, 3 if ok else 1,
        f"{external} outbound links." if external else "No outbound links.",
        None if ok else "Cite sources liberally (3–30 outbound). AI prioritizes content with clear provenance.",
    )


def _check_reviews_or_quotes(soup: BeautifulSoup) -> SignalResult:
    blockquotes = soup.find_all("blockquote")
    cites = soup.find_all("cite")
    total = len(blockquotes) + len(cites)
    ok = total >= 1
    return SignalResult(
        "Quotes & citations markup", "authority", ok, 3, 3 if ok else 0,
        f"{len(blockquotes)} `<blockquote>`, {len(cites)} `<cite>`." if total else "No `<blockquote>` or `<cite>` tags.",
        None if ok else "Wrap quotes in `<blockquote>`. AI summarizers credit quoted sources back to the original.",
    )


# Freshness
def _check_last_modified(response, jsonld: list[dict]) -> SignalResult:
    # Try Last-Modified header
    lm = response.headers.get("last-modified") if response else None
    # Try date in JSON-LD
    date_modified = None
    for entry in jsonld:
        nodes = entry.get("@graph", [entry])
        for n in nodes:
            if isinstance(n, dict):
                if n.get("dateModified"):
                    date_modified = n["dateModified"]
                    break
        if date_modified:
            break
    has = bool(lm or date_modified)
    detail = f"dateModified: {date_modified}" if date_modified else (f"Last-Modified: {lm}" if lm else "No modification date detected.")
    return SignalResult(
        "Last modified date", "freshness", has, 4, 4 if has else 0,
        detail,
        None if has else "Expose a dateModified in JSON-LD or via Last-Modified header. AI prioritizes fresh content.",
    )


def _check_dated_claims(soup: BeautifulSoup) -> SignalResult:
    text = soup.get_text(separator=" ", strip=True)
    # Look for "in 2024", "in 2025", "in 2026", "as of {month} 2026", etc.
    has_date_phrases = bool(
        re.search(r"\b(in|as of|updated|since)\s+(202[3-6]|january|february|march|april|may|june|july|august|september|october|november|december)\b", text, re.I)
    )
    return SignalResult(
        "Dated claims in body", "freshness", has_date_phrases, 3, 3 if has_date_phrases else 0,
        "Body contains explicit dated phrases." if has_date_phrases else "No dated phrases in body text.",
        None if has_date_phrases else "Use 'As of {month} 2026' on every claim. Undated content reads stale to AI models.",
    )


def _check_year_in_title(soup: BeautifulSoup) -> SignalResult:
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    has_year = bool(re.search(r"\b(202[4-6])\b", title))
    return SignalResult(
        "Year in title", "freshness", has_year, 3, 3 if has_year else 0,
        f"Title contains a year." if has_year else "No year in H1/title.",
        None if has_year else "If the content is time-sensitive, include the year in the title (e.g. '... in 2026').",
    )


# ============ ORCHESTRATOR ============

def score_url(url: str) -> ScoreResult:
    url = _norm_url(url)
    result = ScoreResult(
        url=url,
        score=0,
        grade="F",
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        page_title=None,
    )

    response, err = _fetch(url)
    if response is None:
        result.notes.append(err or "Fetch failed for unknown reason.")
        result.grade = "—"
        return result

    soup = BeautifulSoup(response.text, "lxml")
    parsed_url = urlparse(str(response.url))
    page_host = parsed_url.netloc.lower()

    title_tag = soup.find("title")
    result.page_title = title_tag.get_text(strip=True) if title_tag else None

    jsonld = _extract_jsonld(soup)
    schema_set = _schema_types(jsonld)
    wc = _word_count(soup)

    # Detect likely JS-rendered SPA: lots of script tags + very few semantic content tags.
    # If we see ≥3 scripts but fewer than 3 <p> tags AND fewer than 50 words of body text,
    # this page is almost certainly client-side rendered.
    script_count = len(soup.find_all("script"))
    semantic_p = len(soup.find_all("p"))
    if script_count >= 3 and semantic_p < 3 and wc < 200:
        result.notes.append(
            "⚠ This page appears to be JavaScript-rendered. AI crawlers see what we see — not what you see in your browser. "
            "The score reflects what's actually in the raw HTML response."
        )

    signals: list[SignalResult] = [
        # Crawlability bucket (15 pts max)
        _check_https(parsed_url),
        _check_canonical(soup, url),
        _check_viewport(soup),
        _check_open_graph(soup),
        _check_llms_txt(parsed_url),
        _check_robots_ai(parsed_url),

        # Schema & structure (30 pts max)
        _check_article_schema(schema_set),
        _check_faq_schema(schema_set),
        _check_howto_schema(schema_set),
        _check_breadcrumb_schema(schema_set),
        _check_heading_structure(soup),
        _check_definition_lists(soup),
        _check_tables(soup),
        _check_question_h2s(soup),

        # Content / format (25 pts max)
        _check_word_count(wc),
        _check_first_paragraph_answer(soup),
        _check_tldr(soup),
        _check_bold_answer(soup),
        _check_lists(soup),

        # Authority (20 pts max)
        _check_external_authority_links(soup, page_host),
        _check_internal_links(soup, page_host),
        _check_author_byline(soup, jsonld),
        _check_external_link_density(soup, page_host),
        _check_reviews_or_quotes(soup),

        # Freshness (10 pts max)
        _check_last_modified(response, jsonld),
        _check_dated_claims(soup),
        _check_year_in_title(soup),
    ]

    # Aggregate per bucket
    bucket_raw: dict[str, list[SignalResult]] = {b: [] for b in WEIGHTS}
    for s in signals:
        bucket_raw[s.bucket].append(s)

    bucket_summary: dict[str, dict[str, float]] = {}
    total_points = 0.0
    for bucket, weight_max in WEIGHTS.items():
        bs = bucket_raw[bucket]
        bucket_weight = sum(s.weight for s in bs) or 1
        bucket_earned = sum(s.points for s in bs)
        # Normalize to the bucket weight cap
        scaled = (bucket_earned / bucket_weight) * weight_max if bucket_weight else 0
        bucket_summary[bucket] = {
            "earned": round(scaled, 1),
            "max": float(weight_max),
            "percent": round(100 * scaled / weight_max, 1) if weight_max else 0,
        }
        total_points += scaled

    score_int = max(0, min(100, round(total_points)))
    result.score = score_int
    result.grade = _grade(score_int)
    result.bucket_scores = bucket_summary
    result.signals = signals
    result.fixes = [s.fix for s in signals if s.fix][:10]  # top 10 actionable fixes
    return result


# Convenience for serverless / CLI
def score_url_json(url: str) -> str:
    return json.dumps(score_url(url).to_dict(), indent=2)
