"""
SSRF guard tests for oryon_score.

We test the validator at two layers:

1. _validate_url_safety(url) — pure-function unit tests for the validator
   itself: scheme allowlist, hostname/suffix blocklists, IP-range checks
   including IPv4-mapped IPv6 (::ffff:169.254.169.254).

2. _fetch(url) — integration tests proving the event hook re-validates on
   every redirect hop (the most common SSRF bypass), and that legitimate
   public URLs still pass through unchanged. We use monkeypatch +
   socket.getaddrinfo stubs so the suite has no real network dependency
   and is deterministic in CI.

Pinned symptom shapes (the bugs we're guarding against):
- a 169.254.169.254 fetch silently succeeding → must return _REFUSAL_MSG
- a public URL that 302s to an internal IP → must return _REFUSAL_MSG
- a public URL that scores normally today → unchanged behavior
"""
from __future__ import annotations

import socket

import httpx
import pytest

from oryon_score import score
from oryon_score.score import (
    _REFUSAL_MSG,
    _fetch,
    _SSRFBlocked,
    _ssrf_guard,
    _validate_url_safety,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stub_dns(mapping: dict[str, str]):
    """
    Build a replacement for socket.getaddrinfo that returns ONLY the IPs in
    `mapping`. Use `_install_stub_dns(monkeypatch, mapping)` to install it —
    we have to patch BOTH `oryon_score.score._REAL_GETADDRINFO` (what the
    validator uses) AND `socket.getaddrinfo` (what httpx uses via the
    pinning shim — though when the host is pinned the shim returns the
    pinned IPs, when it isn't the shim falls through to socket.getaddrinfo).
    """
    def fake(host, port, *args, **kwargs):
        key = host.lower().strip().rstrip(".") if isinstance(host, str) else host
        if key in mapping:
            ip = mapping[key]
        elif "*" in mapping:
            ip = mapping["*"]
        else:
            raise socket.gaierror(f"unknown host in test: {host}")
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, 0, "", (ip, port or 0))]
    return fake


def _install_stub_dns(monkeypatch, mapping):
    """
    Patch both the validator's real-resolver hook AND socket.getaddrinfo, so
    the validator sees the stub AND any fall-through call from httpx also
    sees the stub. The pinning shim already redirects pinned hosts to
    pre-validated IPs, so this just covers unpinned paths.
    """
    fn = _stub_dns(mapping)
    monkeypatch.setattr(score, "_REAL_GETADDRINFO", fn)
    monkeypatch.setattr(socket, "getaddrinfo", fn)


# ---------------------------------------------------------------------------
# 1. _validate_url_safety — scheme / hostname / IP-range checks
# ---------------------------------------------------------------------------

class TestSchemeAllowlist:
    @pytest.mark.parametrize("bad_url", [
        "file:///etc/passwd",
        "ftp://example.com/",
        "gopher://example.com/",
        "data:text/html,<script>",
        "javascript:alert(1)",
        "about:blank",
        "//example.com/no-scheme",
    ])
    def test_refuses_non_http(self, bad_url):
        assert _validate_url_safety(bad_url) == _REFUSAL_MSG

    def test_accepts_http(self):
        # public IP literal so we skip DNS entirely
        assert _validate_url_safety("http://8.8.8.8/foo") is None

    def test_accepts_https(self):
        assert _validate_url_safety("https://1.1.1.1/foo") is None


class TestHostnameBlocklist:
    @pytest.mark.parametrize("bad_url", [
        "http://localhost/",
        "http://localhost:8000/admin",
        "https://metadata.google.internal/",
        "http://metadata/",
        "http://instance-data/latest/meta-data/",
        "http://myservice.internal/",
        "http://printer.local/",
        "http://api.corp/",
        "http://nas.home/",
        "http://router.lan/",
    ])
    def test_refuses_internal_names(self, bad_url):
        # No DNS stub — these should fail at the hostname/suffix check
        # *before* DNS is even consulted.
        assert _validate_url_safety(bad_url) == _REFUSAL_MSG

    def test_strips_trailing_dot(self):
        # "localhost." is a valid DNS name for the same target.
        assert _validate_url_safety("http://localhost./") == _REFUSAL_MSG


class TestIpLiterals:
    """When the host is a literal IP we skip DNS and check it directly."""

    @pytest.mark.parametrize("bad_url", [
        # cloud metadata
        "http://169.254.169.254/latest/meta-data/",
        # loopback
        "http://127.0.0.1/",
        "http://127.255.255.254/",
        # RFC1918 private
        "http://10.0.0.1/",
        "http://10.255.255.255/",
        "http://172.16.0.1/",
        "http://172.31.255.255/",
        "http://192.168.1.1/",
        # CGNAT (Python 3.14 doesn't flag is_private for this — explicit net required)
        "http://100.64.0.1/",
        "http://100.127.255.255/",
        # unspecified
        "http://0.0.0.0/",
        # multicast
        "http://224.0.0.1/",
        # reserved
        "http://240.0.0.1/",
        # IETF protocol
        "http://192.0.0.1/",
        # benchmark
        "http://198.18.0.1/",
        # IPv6 loopback / unspec
        "http://[::1]/",
        "http://[::]/",
        # IPv6 unique-local + link-local
        "http://[fc00::1]/",
        "http://[fe80::1]/",
        # IPv6 multicast
        "http://[ff00::1]/",
        # IPv4-mapped IPv6 — must unwrap and recheck the v4 portion
        "http://[::ffff:169.254.169.254]/",
        "http://[::ffff:127.0.0.1]/",
        "http://[::ffff:10.0.0.1]/",
    ])
    def test_refuses_blocked_ip_literals(self, bad_url):
        assert _validate_url_safety(bad_url) == _REFUSAL_MSG

    @pytest.mark.parametrize("good_url", [
        "http://8.8.8.8/",         # Google DNS
        "https://1.1.1.1/",        # Cloudflare DNS
        "https://142.250.80.46/",  # example.com class
        "https://[2606:4700:4700::1111]/",  # Cloudflare DNS v6 (public)
    ])
    def test_accepts_public_ip_literals(self, good_url):
        assert _validate_url_safety(good_url) is None


class TestDnsResolution:
    """Hostnames that aren't IPs go through getaddrinfo — every resolved IP must pass."""

    def test_public_host_with_public_ip_passes(self, monkeypatch):
        _install_stub_dns(monkeypatch, {"example.com": "93.184.216.34"})
        assert _validate_url_safety("https://example.com/article") is None

    def test_host_that_resolves_to_metadata_is_blocked(self, monkeypatch):
        # The classic DNS-based SSRF: attacker controls a domain that resolves
        # to 169.254.169.254. Without IP-level checks this would slip through.
        _install_stub_dns(monkeypatch, {"evil.example.com": "169.254.169.254"})
        assert _validate_url_safety("https://evil.example.com/leak") == _REFUSAL_MSG

    def test_host_that_resolves_to_loopback_is_blocked(self, monkeypatch):
        _install_stub_dns(monkeypatch, {"local.evil.example": "127.0.0.1"})
        assert _validate_url_safety("http://local.evil.example/") == _REFUSAL_MSG

    def test_host_that_resolves_to_rfc1918_is_blocked(self, monkeypatch):
        _install_stub_dns(monkeypatch, {"internal.example": "10.0.0.5"})
        assert _validate_url_safety("http://internal.example/admin") == _REFUSAL_MSG

    def test_failed_dns_fails_closed(self, monkeypatch):
        def boom(*a, **kw):
            raise socket.gaierror("nope")
        monkeypatch.setattr(score, "_REAL_GETADDRINFO", boom)
        # Fail-CLOSED: if we can't resolve, we don't fetch.
        assert _validate_url_safety("http://does-not-exist.example/") == _REFUSAL_MSG

    def test_idn_unicode_host_doesnt_crash(self, monkeypatch):
        # If getaddrinfo refuses an IDN, we must still fail closed, not throw.
        def boom(*a, **kw):
            raise UnicodeError("encoding")
        monkeypatch.setattr(score, "_REAL_GETADDRINFO", boom)
        assert _validate_url_safety("http://xn--zckzah.example/") == _REFUSAL_MSG


class TestEdgeCases:
    def test_no_host(self):
        assert _validate_url_safety("https:///just-a-path") == _REFUSAL_MSG

    def test_empty_string(self):
        assert _validate_url_safety("") == _REFUSAL_MSG

    def test_unparseable(self):
        # Don't crash, fail closed
        assert _validate_url_safety("http://[invalid::ipv6/") == _REFUSAL_MSG

    def test_uniform_message(self):
        # Security property: every refusal returns the SAME string so a
        # hostile prober can't tell which check fired.
        assert _validate_url_safety("file:///etc/passwd") == _REFUSAL_MSG
        assert _validate_url_safety("http://localhost/") == _REFUSAL_MSG
        assert _validate_url_safety("http://169.254.169.254/") == _REFUSAL_MSG
        assert _validate_url_safety("http://[::1]/") == _REFUSAL_MSG


# ---------------------------------------------------------------------------
# 2. _fetch — event hook + redirect re-validation
# ---------------------------------------------------------------------------

class TestFetchBlocksInternal:
    """Initial-URL blocking must short-circuit before any network call."""

    @pytest.mark.parametrize("bad_url", [
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://[::ffff:169.254.169.254]/",
        "file:///etc/passwd",
    ])
    def test_internal_target_refused_with_friendly_message(self, bad_url):
        response, err = _fetch(bad_url)
        assert response is None
        assert err == _REFUSAL_MSG


class TestFetchAllowsPublic:
    def test_public_url_passes_through(self, monkeypatch):
        # Stub DNS so the validator passes, then stub the actual HTTP call.
        _install_stub_dns(monkeypatch, {"example.com": "93.184.216.34"})

        captured = {"calls": 0}
        def handler(request: httpx.Request) -> httpx.Response:
            captured["calls"] += 1
            return httpx.Response(200, text="<html><title>OK</title><body>hi</body></html>")

        original_client = httpx.Client
        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)
        monkeypatch.setattr(score.httpx, "Client", patched_client)

        response, err = _fetch("https://example.com/article")
        assert err is None
        assert response is not None
        assert response.status_code == 200
        assert captured["calls"] == 1


class TestRedirectRevalidation:
    """
    The most common SSRF bypass: a permitted public URL that 302s to an
    internal target. The event_hook fires per-request, including redirect
    hops, so the second request must be refused.
    """

    def test_public_url_that_302s_to_metadata_is_refused(self, monkeypatch):
        # Both hosts resolve cleanly so the *validator* would pass them
        # individually — what stops the bypass is the IP-range check on
        # the redirect target (169.254.169.254 is a literal IP, blocked).
        _install_stub_dns(monkeypatch, {
            "redirector.example.com": "93.184.216.34",
            "*": "169.254.169.254",
        })

        hops = []
        def handler(request: httpx.Request) -> httpx.Response:
            hops.append(str(request.url))
            if "redirector.example.com" in str(request.url):
                # 302 to the AWS metadata service
                return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
            # If we ever reach here, the SSRF bypass worked — fail the test loudly
            return httpx.Response(200, text="LEAKED METADATA")

        original_client = httpx.Client
        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)
        monkeypatch.setattr(score.httpx, "Client", patched_client)

        response, err = _fetch("http://redirector.example.com/innocent")
        assert response is None
        assert err == _REFUSAL_MSG
        # The first hop made it (public host), but the redirect target was refused.
        assert len(hops) == 1, f"redirect hop should have been refused but got hops={hops}"

    def test_public_url_that_302s_to_localhost_is_refused(self, monkeypatch):
        _install_stub_dns(monkeypatch, {
            "redirector.example.com": "93.184.216.34",
            "localhost": "127.0.0.1",
        })

        hops = []
        def handler(request: httpx.Request) -> httpx.Response:
            hops.append(str(request.url))
            return httpx.Response(302, headers={"location": "http://localhost/admin"})

        original_client = httpx.Client
        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)
        monkeypatch.setattr(score.httpx, "Client", patched_client)

        response, err = _fetch("http://redirector.example.com/")
        assert response is None
        assert err == _REFUSAL_MSG
        assert len(hops) == 1

    def test_public_to_public_redirect_still_succeeds(self, monkeypatch):
        """A normal public 302 → public must still work (no regression)."""
        _install_stub_dns(monkeypatch, {
            "a.example.com": "93.184.216.34",
            "b.example.com": "151.101.1.69",
        })

        hops = []
        def handler(request: httpx.Request) -> httpx.Response:
            hops.append(str(request.url))
            if "a.example.com" in str(request.url):
                return httpx.Response(302, headers={"location": "https://b.example.com/article"})
            return httpx.Response(200, text="<html>real article</html>")

        original_client = httpx.Client
        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)
        monkeypatch.setattr(score.httpx, "Client", patched_client)

        response, err = _fetch("https://a.example.com/start")
        assert err is None
        assert response is not None
        assert response.status_code == 200
        assert len(hops) == 2


class TestSsrfGuardHook:
    """The event hook itself — exercised directly without the full Client."""

    def test_raises_ssrf_blocked_on_internal(self):
        request = httpx.Request("GET", "http://169.254.169.254/")
        with pytest.raises(_SSRFBlocked) as exc:
            _ssrf_guard(request)
        # The exception's message is the user-facing refusal — friendly, uniform.
        assert str(exc.value) == _REFUSAL_MSG

    def test_passes_on_public_ip_literal(self):
        request = httpx.Request("GET", "https://8.8.8.8/")
        # Should not raise
        _ssrf_guard(request)


class TestDnsRebinding:
    """
    The TOCTOU bypass: a malicious DNS server returns a public IP on the
    validator's lookup, then a private IP on httpx's connect-time lookup.

    Our defense: the validator stores the validated IPs in a thread-local
    pin map, and the module-installed _pinning_getaddrinfo() returns ONLY
    those pinned IPs for the same host within this thread. So even if the
    "DNS oracle" we simulate flips its answer between the two lookups,
    httpx's connect-time lookup hits the pin and gets the pre-validated IPs.
    """

    def test_pinning_getaddrinfo_returns_pinned_only(self, monkeypatch):
        # Arrange a fake DNS that returns a PUBLIC IP first, then a PRIVATE IP.
        # If pinning works, the second call (from "httpx") never sees the private IP.
        call_count = {"n": 0}
        def flipping_dns(host, port, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First lookup: public — what the validator sees and approves
                return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port or 0))]
            # Subsequent lookups: REBOUND to the cloud metadata service
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", port or 0))]

        monkeypatch.setattr(score, "_REAL_GETADDRINFO", flipping_dns)

        # Validator runs first, pins "evil.example.com" → 93.184.216.34
        pins = {}
        assert _validate_url_safety("https://evil.example.com/article", pin_into=pins) is None
        assert "evil.example.com" in pins

        # Simulate the second lookup coming from httpx with the pin active.
        score._DNS_PIN_TLS.pins = pins
        try:
            result = score._pinning_getaddrinfo("evil.example.com", 443)
        finally:
            score._DNS_PIN_TLS.pins = None

        # The pinning shim must return ONLY 93.184.216.34 — never 169.254.169.254
        # (which is what the next call to the underlying flipping_dns would have given).
        ips = [info[4][0] for info in result]
        assert ips == ["93.184.216.34"], (
            f"DNS-rebind bypass! Pinning returned {ips!r} but should have returned only "
            "the validator-approved IP. If 169.254.169.254 appears here, the TOCTOU window "
            "is open."
        )

    def test_pinning_falls_through_when_no_pin(self, monkeypatch):
        # When no pin is active, the shim must NOT intercept lookups.
        # (Otherwise other parts of the program — tests, the CLI in non-fetch
        # contexts, user code — would see the wrong resolver.)
        called = {"n": 0}
        def real(host, port, *args, **kwargs):
            called["n"] += 1
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("203.0.113.1", port or 0))]
        monkeypatch.setattr(score, "_REAL_GETADDRINFO", real)
        score._DNS_PIN_TLS.pins = None  # explicit no-pin

        result = score._pinning_getaddrinfo("anything.example.com", 80)
        assert called["n"] == 1, "pinning shim must fall through to real resolver when no pin"
        assert result[0][4][0] == "203.0.113.1"

    def test_pin_only_applies_to_pinned_host(self, monkeypatch):
        # Pin example.com → public IP, then look up a DIFFERENT host. The
        # pin must NOT apply to the unpinned host (no over-broad matching).
        real_calls = []
        def real(host, port, *args, **kwargs):
            real_calls.append(host)
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", port or 0))]
        monkeypatch.setattr(score, "_REAL_GETADDRINFO", real)

        score._DNS_PIN_TLS.pins = {
            "example.com": [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]
        }
        try:
            # Pinned host: served from the pin
            assert score._pinning_getaddrinfo("example.com", 443)[0][4][0] == "93.184.216.34"
            assert real_calls == []
            # Different host: falls through
            assert score._pinning_getaddrinfo("other.example.com", 80)[0][4][0] == "8.8.8.8"
            assert real_calls == ["other.example.com"]
        finally:
            score._DNS_PIN_TLS.pins = None

    def test_pin_cleared_after_fetch(self, monkeypatch):
        # The pin must be cleared on every _fetch() exit so concurrent calls
        # in the same thread (or sequential calls) don't see stale pins.
        _install_stub_dns(monkeypatch, {"example.com": "93.184.216.34"})

        def handler(request):
            return httpx.Response(200, text="ok")
        original_client = httpx.Client
        def patched_client(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original_client(*args, **kwargs)
        monkeypatch.setattr(score.httpx, "Client", patched_client)

        # Inside _fetch the pin would be set; after _fetch returns it must be cleared.
        assert getattr(score._DNS_PIN_TLS, "pins", None) is None
        r, err = _fetch("https://example.com/")
        assert err is None
        # After return:
        assert getattr(score._DNS_PIN_TLS, "pins", None) is None
