"""
Rate-limit tests for oryon_score.rate_limit.

What the suite proves:

* IP extraction handles every shape Vercel can hand us (XFF leftmost,
  whitespace, IPv6, invalid leftmost, X-Real-IP fallback, no headers).
* Under the cap, requests pass and are counted as `enforced=True`.
* Crossing EITHER cap (per-minute OR per-day) returns `allowed=False`
  with a sensible Retry-After.
* When BOTH caps are exceeded, the binding wait is the longer one.
* Two different IPs use two different Redis keys (independence).
* Concurrent requests can't race past the cap — proven by feeding the
  limiter monotonically-increasing INCR results (the actual property of
  Redis's atomic INCR) and asserting that requests #21+ are blocked.
* Fail-SAFE: env vars unset → every request allowed, `enforced=False`.
* Fail-OPEN: any Upstash failure (timeout, 5xx, bad JSON shape,
  non-integer result) → every request allowed, `enforced=False`.
* Retry-After is at least 1 second when blocked (never 0/negative).
"""
from __future__ import annotations

import json
import socket
import time

import httpx
import pytest

from oryon_score import rate_limit as rl
from oryon_score.rate_limit import (
    FRIENDLY_429_MSG,
    PER_DAY_DEFAULT,
    PER_MINUTE_DEFAULT,
    RateLimitDecision,
    check_rate_limit,
    extract_client_ip,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_env(monkeypatch, *, url="https://upstash.test", token="t",
             per_min=PER_MINUTE_DEFAULT, per_day=PER_DAY_DEFAULT):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", url)
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", token)
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", str(per_min))
    monkeypatch.setenv("RATE_LIMIT_PER_DAY", str(per_day))


def _fake_response(status_code=200, body=None):
    """
    Build a minimal httpx.Response that mimics what _upstash_pipeline returns.

    Pass a list as `body` (the JSON-decoded payload) for happy-path tests, or
    a non-JSON `body` string + a specific `status_code` to simulate Upstash
    errors. The .json() method returns the body if it's a list/dict, else
    raises ValueError to mimic JSON-decode failures.
    """
    class _Fake:
        def __init__(self, sc, b):
            self.status_code = sc
            self._body = b
        def json(self):
            if isinstance(self._body, (list, dict)):
                return self._body
            raise ValueError(f"Mock JSON decode error: {self._body!r}")
    return _Fake(status_code, body)


def _stub_pipeline(monkeypatch, body=None, status_code=200):
    """Replace the network call with a function returning a fake httpx.Response."""
    def fake(url, token, commands):
        return _fake_response(status_code=status_code, body=body)
    monkeypatch.setattr(rl, "_upstash_pipeline", fake)


def _h(d):
    """Make a dict's .get behave like BaseHTTPRequestHandler's headers.get."""
    return d.get


def _reset_warned():
    rl._warned_unconfigured = False


# ---------------------------------------------------------------------------
# 1. extract_client_ip — header parsing
# ---------------------------------------------------------------------------

class TestExtractClientIp:
    def test_xff_leftmost_simple(self):
        assert extract_client_ip(_h({"x-forwarded-for": "1.2.3.4"})) == "1.2.3.4"

    def test_xff_leftmost_with_chain(self):
        assert extract_client_ip(_h({
            "x-forwarded-for": "1.2.3.4, 10.0.0.1, 172.16.0.1"
        })) == "1.2.3.4"

    def test_xff_leftmost_with_whitespace(self):
        assert extract_client_ip(_h({
            "x-forwarded-for": "  1.2.3.4  , 10.0.0.1"
        })) == "1.2.3.4"

    def test_xff_ipv6(self):
        assert extract_client_ip(_h({
            "x-forwarded-for": "2001:db8::1, 10.0.0.1"
        })) == "2001:db8::1"

    def test_xff_invalid_leftmost_falls_back_to_xri(self):
        # Defensive — Vercel shouldn't produce this, but a stray header chain
        # with an obviously broken first hop should still try x-real-ip.
        assert extract_client_ip(_h({
            "x-forwarded-for": "garbage,1.2.3.4",
            "x-real-ip": "5.6.7.8",
        })) == "5.6.7.8"

    def test_xri_only(self):
        assert extract_client_ip(_h({"x-real-ip": "1.2.3.4"})) == "1.2.3.4"

    def test_xri_ipv6(self):
        assert extract_client_ip(_h({"x-real-ip": "2001:db8::1"})) == "2001:db8::1"

    def test_xri_invalid_returns_none(self):
        assert extract_client_ip(_h({"x-real-ip": "not-an-ip"})) is None

    def test_no_headers_returns_none(self):
        # Caller will fail-open on None.
        assert extract_client_ip(_h({})) is None

    def test_empty_xff_returns_none(self):
        assert extract_client_ip(_h({"x-forwarded-for": ""})) is None

    def test_xff_with_port_invalid(self):
        # "1.2.3.4:5678" is not a valid ip_address — must fall back / None.
        assert extract_client_ip(_h({"x-forwarded-for": "1.2.3.4:5678"})) is None


# ---------------------------------------------------------------------------
# 2. Fail-SAFE — env vars unset
# ---------------------------------------------------------------------------

class TestFailSafe:
    def test_no_env_vars_allows(self, monkeypatch):
        monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
        _reset_warned()
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_url_set_token_missing_allows(self, monkeypatch):
        monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://x")
        monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
        _reset_warned()
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_token_set_url_missing_allows(self, monkeypatch):
        monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
        monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "t")
        _reset_warned()
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_warning_logged_once_only(self, monkeypatch, capsys):
        monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
        monkeypatch.delenv("UPSTASH_REDIS_REST_TOKEN", raising=False)
        _reset_warned()
        # Call three times — expect ONE warning print, not three.
        for _ in range(3):
            check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        out = capsys.readouterr().out
        assert out.count("[rate_limit] DISABLED") == 1


# ---------------------------------------------------------------------------
# 3. Under the cap — normal pass-through
# ---------------------------------------------------------------------------

class TestUnderLimit:
    def test_first_request_allowed_and_enforced(self, monkeypatch):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, [
            {"result": 1}, {"result": 1},  # INCR min, EXPIRE min NX (set)
            {"result": 1}, {"result": 1},  # INCR day, EXPIRE day NX (set)
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is True
        assert d.retry_after_seconds == 0

    def test_request_at_min_cap_exactly_still_allowed(self, monkeypatch):
        _set_env(monkeypatch, per_min=20)
        # 20th request returns INCR=20, which equals the cap, NOT exceeds.
        _stub_pipeline(monkeypatch, [
            {"result": 20}, {"result": 0},
            {"result": 20}, {"result": 0},
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True

    def test_request_at_day_cap_exactly_still_allowed(self, monkeypatch):
        _set_env(monkeypatch, per_day=200)
        _stub_pipeline(monkeypatch, [
            {"result": 5}, {"result": 0},
            {"result": 200}, {"result": 0},
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True


# ---------------------------------------------------------------------------
# 4. Over the cap — 429 + Retry-After
# ---------------------------------------------------------------------------

class TestOverMinuteLimit:
    def test_21st_request_blocked(self, monkeypatch):
        _set_env(monkeypatch, per_min=20)
        _stub_pipeline(monkeypatch, [
            {"result": 21}, {"result": 0},
            {"result": 21}, {"result": 0},
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is False
        assert d.enforced is True
        # Minute window: 1..60 seconds out (never negative, never zero).
        assert 1 <= d.retry_after_seconds <= 60

    def test_retry_after_never_zero(self, monkeypatch):
        _set_env(monkeypatch, per_min=20)
        _stub_pipeline(monkeypatch, [
            {"result": 100}, {"result": 0},
            {"result": 100}, {"result": 0},
        ])
        # Even right at a minute boundary, Retry-After should be >= 1.
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.retry_after_seconds >= 1


class TestOverDayLimit:
    def test_201st_request_blocked(self, monkeypatch):
        _set_env(monkeypatch, per_day=200)
        _stub_pipeline(monkeypatch, [
            {"result": 5}, {"result": 0},    # min: well under
            {"result": 201}, {"result": 0},  # day: over
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is False
        # Day window: up to 86400 seconds.
        assert d.retry_after_seconds > 60
        assert d.retry_after_seconds <= 86400

    def test_both_exceeded_uses_longer_wait(self, monkeypatch):
        _set_env(monkeypatch, per_min=20, per_day=200)
        _stub_pipeline(monkeypatch, [
            {"result": 25}, {"result": 0},
            {"result": 250}, {"result": 0},
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is False
        # Day reset is far further out than the minute reset → it dominates.
        assert d.retry_after_seconds > 60


# ---------------------------------------------------------------------------
# 5. IP independence
# ---------------------------------------------------------------------------

class TestIpIndependence:
    def test_different_ips_use_different_keys(self, monkeypatch):
        _set_env(monkeypatch)
        seen_keys = []

        def capture(url, token, commands):
            # The INCR key is the second element of the first command.
            seen_keys.append(commands[0][1])
            return _fake_response(200, [
                {"result": 1}, {"result": 1},
                {"result": 1}, {"result": 1},
            ])
        monkeypatch.setattr(rl, "_upstash_pipeline", capture)

        check_rate_limit(_h({"x-forwarded-for": "1.1.1.1"}))
        check_rate_limit(_h({"x-forwarded-for": "2.2.2.2"}))

        assert seen_keys[0] != seen_keys[1]
        assert "1.1.1.1" in seen_keys[0]
        assert "2.2.2.2" in seen_keys[1]

    def test_same_ip_uses_same_minute_key(self, monkeypatch):
        _set_env(monkeypatch)
        seen_keys = []

        def capture(url, token, commands):
            seen_keys.append(commands[0][1])  # INCR min key
            return _fake_response(200, [
                {"result": 1}, {"result": 1},
                {"result": 1}, {"result": 1},
            ])
        monkeypatch.setattr(rl, "_upstash_pipeline", capture)

        # Two back-to-back calls within the same minute → same key.
        check_rate_limit(_h({"x-forwarded-for": "1.1.1.1"}))
        check_rate_limit(_h({"x-forwarded-for": "1.1.1.1"}))

        assert seen_keys[0] == seen_keys[1]


# ---------------------------------------------------------------------------
# 6. Atomic race-safety
# ---------------------------------------------------------------------------

class TestAtomicRaceSafety:
    """
    The decision MUST be made from the INCR return value alone, with no
    read-then-write step. We simulate Redis's atomic INCR by giving the
    fake pipeline a counter that advances by one on every call (monotonic,
    serialized — exactly what Redis would return). If the limit logic
    were doing read-then-write, two "concurrent" requests could both see
    the same count and both pass; with the real INCR semantics they
    can't, and that's what this test confirms.
    """

    def test_first_20_pass_request_21_blocks(self, monkeypatch):
        _set_env(monkeypatch, per_min=20, per_day=200)
        counter = {"n": 0}

        def fake(url, token, commands):
            counter["n"] += 1
            n = counter["n"]
            return _fake_response(200, [
                {"result": n},                       # INCR min
                {"result": 1 if n == 1 else 0},      # EXPIRE NX
                {"result": n},                       # INCR day
                {"result": 1 if n == 1 else 0},
            ])
        monkeypatch.setattr(rl, "_upstash_pipeline", fake)

        decisions = [
            check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
            for _ in range(30)
        ]
        allowed_idx = [i for i, d in enumerate(decisions, 1) if d.allowed]
        blocked_idx = [i for i, d in enumerate(decisions, 1) if not d.allowed]

        # Requests 1..20 pass (INCR returned 1..20 ≤ cap).
        # Requests 21..30 block (INCR returned 21..30 > cap).
        assert allowed_idx == list(range(1, 21))
        assert blocked_idx == list(range(21, 31))


# ---------------------------------------------------------------------------
# 7. Fail-OPEN — Upstash errors
# ---------------------------------------------------------------------------

class TestFailOpen:
    """Transient Upstash trouble → serve the request (best-effort)."""

    def test_timeout_allows(self, monkeypatch):
        _set_env(monkeypatch)
        def boom(*a, **kw):
            raise httpx.TimeoutException("upstash slow")
        monkeypatch.setattr(rl, "_upstash_pipeline", boom)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_connect_error_allows(self, monkeypatch):
        _set_env(monkeypatch)
        def boom(*a, **kw):
            raise httpx.ConnectError("upstash unreachable")
        monkeypatch.setattr(rl, "_upstash_pipeline", boom)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_5xx_response_allows(self, monkeypatch):
        # Upstash outage — fail-OPEN (transient).
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=500)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_503_response_allows(self, monkeypatch):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=503)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True

    def test_401_bad_token_fails_OPEN_with_warning(self, monkeypatch, capsys):
        # Misconfigured token → admin needs to fix it; don't lock every user
        # out forever.
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=401)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        out = capsys.readouterr().out
        assert "[rate_limit] fail-open" in out
        assert "401" in out

    def test_404_wrong_path_allows(self, monkeypatch):
        # Misconfigured URL — same logic as 401.
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=404)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True

    def test_arbitrary_exception_allows(self, monkeypatch):
        _set_env(monkeypatch)
        def boom(*a, **kw):
            raise RuntimeError("unexpected")
        monkeypatch.setattr(rl, "_upstash_pipeline", boom)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True

    def test_bad_shape_response_allows(self, monkeypatch):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body="not a list", status_code=200)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True
        assert d.enforced is False

    def test_short_response_allows(self, monkeypatch):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=[{"result": 1}, {"result": 1}])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True

    def test_non_integer_incr_result_allows(self, monkeypatch):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=[
            {"error": "OOM"}, {"result": 0},
            {"result": 1}, {"result": 0},
        ])
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is True

    def test_no_client_ip_fails_open(self, monkeypatch):
        # If Vercel's headers are missing, do NOT group every visitor as one
        # bucket — fail open and log.
        _set_env(monkeypatch)
        d = check_rate_limit(_h({}))
        assert d.allowed is True
        assert d.enforced is False


class TestFailClosedOnQuotaBurn:
    """
    Upstash returning 429 or 403 is the signal of a quota-burn attack:
    an attacker intentionally drained our daily-command quota to push
    the limiter into the fail-OPEN state. Counter-measure: treat those
    statuses as enforcement — return 429 to the user-facing request.
    Admins notice immediately (every user gets 429) and can fix; an
    attacker who paid for proxy traffic gets no bypass.
    """

    def test_upstash_429_fails_CLOSED(self, monkeypatch, capsys):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=429)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is False, (
            "Upstash 429 must fail CLOSED to prevent quota-burn bypass"
        )
        assert d.enforced is True
        assert d.retry_after_seconds > 0
        out = capsys.readouterr().out
        assert "fail-closed" in out and "429" in out

    def test_upstash_403_fails_CLOSED(self, monkeypatch, capsys):
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=403)
        d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
        assert d.allowed is False, (
            "Upstash 403 must fail CLOSED to prevent quota-burn bypass"
        )
        assert d.enforced is True
        assert d.retry_after_seconds > 0
        out = capsys.readouterr().out
        assert "fail-closed" in out

    def test_quota_burn_doesnt_open_subsequent_requests(self, monkeypatch):
        """
        Once Upstash starts returning 429, EVERY subsequent request should
        also be blocked — never a single fail-OPEN slip-through.
        """
        _set_env(monkeypatch)
        _stub_pipeline(monkeypatch, body=None, status_code=429)
        # 100 'requests' under sustained quota-burn — all blocked.
        for _ in range(100):
            d = check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))
            assert d.allowed is False, "Quota-burn must not leak any pass-throughs"


# ---------------------------------------------------------------------------
# 8. Pipeline composition — the right Redis commands are sent
# ---------------------------------------------------------------------------

class TestPipelineCommands:
    def test_pipeline_has_four_atomic_commands(self, monkeypatch):
        _set_env(monkeypatch)
        seen = {}

        def capture(url, token, commands):
            seen["commands"] = commands
            return _fake_response(200, [
                {"result": 1}, {"result": 1},
                {"result": 1}, {"result": 1},
            ])
        monkeypatch.setattr(rl, "_upstash_pipeline", capture)

        check_rate_limit(_h({"x-forwarded-for": "1.2.3.4"}))

        cmds = seen["commands"]
        # Exactly 4 commands, in this order:
        assert len(cmds) == 4
        assert cmds[0][0] == "INCR"
        assert cmds[1][0] == "EXPIRE"
        assert cmds[2][0] == "INCR"
        assert cmds[3][0] == "EXPIRE"
        # EXPIRE must use the NX flag so we don't re-extend an active window.
        assert "NX" in cmds[1]
        assert "NX" in cmds[3]
        # TTLs match the windows.
        assert "60" in cmds[1]
        assert "86400" in cmds[3]
        # Keys are bucketed by IP + bucket-index.
        assert cmds[0][1].startswith("rl:min:1.2.3.4:")
        assert cmds[2][1].startswith("rl:day:1.2.3.4:")
