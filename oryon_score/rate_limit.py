"""
Cross-instance rate limiting for /api/score — Upstash Redis REST API.

Two fixed-window counters per client IP, both checked on every request:
- Per-minute  (default: 20 req/min)  — stops bursts
- Per-day     (default: 200 req/day) — stops slow sustained scraping
EITHER threshold exceeded → 429 with a friendly message + Retry-After.

Design properties — see SECURITY_REVIEW.md §3.2.

ATOMIC under concurrent requests.
    Redis INCR is atomic. Two simultaneous /api/score calls from the same
    IP serialize at Redis: one INCR returns N, the other N+1. Neither can
    miss a count. The code makes the rate-limit decision from the INCR
    return value alone — there is no read-then-write anywhere — so the
    "two requests both pass because both saw count=20" race cannot occur.

FAIL-SAFE when env vars are not set.
    UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN unset → no rate
    limiting; the endpoint serves every request unthrottled and logs a
    one-time warning at startup. This lets the limiter ship before the
    Upstash store is provisioned without breaking the live tool. Once
    the env vars are set on Vercel and the function redeploys, limiting
    activates automatically.

FAIL-OPEN on TRANSIENT Upstash error.
    For a free public tool, availability beats strict limiting when the
    store has a brief outage. Timeouts, network errors, 5xx, JSON-parse
    errors, 401 (bad token), 404 (wrong path) all fail OPEN — the SSRF
    guard from 0.2.0 still protects the dangerous path, and a brief
    abuse window during a real Redis outage is acceptable. Every fail-
    open is logged. This is best-effort rate limiting, not a hard
    guarantee — documented in SECURITY_REVIEW.md.

FAIL-CLOSED on Upstash QUOTA / ABUSE signals.
    If Upstash itself returns 429 (rate-limited) or 403 (forbidden), the
    most likely cause is a quota-burn attack: an attacker drained our
    Upstash account's daily-command quota on purpose so the limiter
    would silently switch off and let them spam unthrottled from a
    single IP. Treating 429/403 as fail-OPEN would reward that pattern.
    Instead, the limiter denies the user-facing request with a 60-second
    Retry-After. Admins will notice immediately (every user sees 429)
    and can fix the quota / token; an attacker burning quota gets no
    free pass.

Env vars (read on every call, cheap):
    UPSTASH_REDIS_REST_URL    Upstash REST endpoint, e.g.
                              https://us1-foo-12345.upstash.io
    UPSTASH_REDIS_REST_TOKEN  Bearer token for the REST API.
    RATE_LIMIT_PER_MINUTE     Optional override (default 20).
    RATE_LIMIT_PER_DAY        Optional override (default 200).
"""
from __future__ import annotations

import ipaddress
import json
import os
import time
from dataclasses import dataclass
from typing import Callable

import httpx

PER_MINUTE_DEFAULT = 20
PER_DAY_DEFAULT = 200
UPSTASH_TIMEOUT_S = 1.5

# User-facing message on 429 — friendly, no security detail.
FRIENDLY_429_MSG = (
    "You've hit the rate limit — please wait a moment before scoring more pages."
)

# Once-only "rate limiting is off" warning so we don't flood Vercel logs.
_warned_unconfigured = False


@dataclass
class RateLimitDecision:
    """Outcome of a rate-limit check."""
    allowed: bool
    retry_after_seconds: int = 0  # only meaningful when allowed=False
    enforced: bool = False         # True only when the store actually decided


def _config() -> tuple[str, str, int, int] | None:
    """Return (url, token, per_minute, per_day) or None if not configured."""
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").strip()
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "").strip()
    if not url or not token:
        return None
    # Allow tuning the caps without a code change.
    try:
        per_minute = int(os.environ.get("RATE_LIMIT_PER_MINUTE", str(PER_MINUTE_DEFAULT)))
        per_day = int(os.environ.get("RATE_LIMIT_PER_DAY", str(PER_DAY_DEFAULT)))
    except ValueError:
        per_minute, per_day = PER_MINUTE_DEFAULT, PER_DAY_DEFAULT
    return url, token, max(1, per_minute), max(1, per_day)


def _warn_unconfigured_once() -> None:
    global _warned_unconfigured
    if not _warned_unconfigured:
        print(
            "[rate_limit] DISABLED: UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN "
            "not set — endpoint will serve every request unthrottled. "
            "Provision Upstash and set the env vars in Vercel to activate.",
            flush=True,
        )
        _warned_unconfigured = True


def _is_valid_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


def extract_client_ip(get_header: Callable[[str], str | None]) -> str | None:
    """
    Return the trusted client IP, or None if it can't be determined.

    `get_header(name)` is a case-insensitive header getter — pass either a
    dict's `.get` or `BaseHTTPRequestHandler.headers.get`.

    Vercel's edge OVERWRITES x-forwarded-for with the trusted observation;
    per Vercel's docs the LEFTMOST entry is the original client IP. If
    that's missing or invalid, fall back to x-real-ip. If neither is
    available, return None and the caller fails open — better than
    grouping every visitor under one shared bucket.
    """
    xff = get_header("x-forwarded-for") or ""
    if xff:
        first = xff.split(",", 1)[0].strip()
        if _is_valid_ip(first):
            return first
    xri = (get_header("x-real-ip") or "").strip()
    if _is_valid_ip(xri):
        return xri
    return None


def _retry_after_seconds(now: int, min_count: int, day_count: int,
                        per_min: int, per_day: int) -> int:
    """
    Seconds until a fresh request from this IP could plausibly succeed.

    If only the minute window is exceeded, wait for it to roll over
    (≤ 60 s). If the day window is exceeded, that's the binding wait
    (≤ 86400 s) — the per-minute reset wouldn't help.
    """
    candidates: list[int] = []
    if min_count > per_min:
        candidates.append(60 - (now % 60))
    if day_count > per_day:
        candidates.append(86400 - (now % 86400))
    return max(candidates) if candidates else 0


def _upstash_pipeline(url: str, token: str, commands: list) -> httpx.Response:
    """
    Single round-trip to Upstash. Returns the raw httpx.Response so the
    caller can inspect status codes (a 429/403 from Upstash means our
    own quota was drained — see check_rate_limit for that policy).
    """
    return httpx.post(
        url.rstrip("/") + "/pipeline",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        content=json.dumps(commands).encode("utf-8"),
        timeout=UPSTASH_TIMEOUT_S,
    )


def check_rate_limit(get_header: Callable[[str], str | None]) -> RateLimitDecision:
    """
    Decide whether to allow this /api/score request.

    `get_header(name) -> str | None` reads a request header by lowercase
    name (e.g. self.headers.get from BaseHTTPRequestHandler).

    Returns:
        RateLimitDecision(allowed=True, enforced=False) on fail-safe / fail-open
        RateLimitDecision(allowed=True, enforced=True)  under the cap
        RateLimitDecision(allowed=False, retry_after_seconds=N, enforced=True) over
    """
    cfg = _config()
    if cfg is None:
        _warn_unconfigured_once()
        return RateLimitDecision(allowed=True, enforced=False)
    url, token, per_min, per_day = cfg

    ip = extract_client_ip(get_header)
    if ip is None:
        # Should not happen on Vercel — the edge always sets x-forwarded-for.
        # If it does, fail open rather than rate-limit every visitor as one IP.
        print("[rate_limit] fail-open: no x-forwarded-for / x-real-ip on request",
              flush=True)
        return RateLimitDecision(allowed=True, enforced=False)

    now = int(time.time())
    # Fixed-window bucket indices (UTC, integer division — auto-rollover).
    min_bucket = now // 60
    day_bucket = now // 86400
    min_key = f"rl:min:{ip}:{min_bucket}"
    day_key = f"rl:day:{ip}:{day_bucket}"

    # Four commands batched into ONE Upstash round-trip.
    # INCR is atomic at Redis; EXPIRE … NX only sets TTL on first touch
    # (so subsequent INCRs in the same bucket don't extend the lifetime).
    try:
        response = _upstash_pipeline(url, token, [
            ["INCR", min_key],
            ["EXPIRE", min_key, "60", "NX"],
            ["INCR", day_key],
            ["EXPIRE", day_key, "86400", "NX"],
        ])
    except Exception as e:
        # Network error, timeout, transport layer failure — TRANSIENT.
        # Fail-OPEN: don't take down the public tool when Upstash is briefly
        # unreachable. The SSRF guard still protects the dangerous path.
        print(f"[rate_limit] fail-open: Upstash error: {e!r}", flush=True)
        return RateLimitDecision(allowed=True, enforced=False)

    # Inspect the HTTP status code BEFORE parsing the body, so we can
    # distinguish a quota-burn attack (429/403) from a transient outage.
    status = response.status_code
    if status in (429, 403):
        # Upstash itself is rate-limiting us OR refusing the request —
        # the most likely cause is a quota-burn attack: an attacker
        # intentionally drained our daily-command quota so this very
        # limiter would silently switch off. Treat as ABUSE, fail CLOSED.
        # Admins notice immediately (every user gets 429) and can fix
        # the quota or token; an attacker doesn't get the bypass they
        # paid proxy traffic for.
        print(f"[rate_limit] fail-closed: Upstash {status} — likely quota burn",
              flush=True)
        return RateLimitDecision(
            allowed=False,
            retry_after_seconds=60,  # short, generic — not tied to a real bucket
            enforced=True,
        )
    if status >= 400:
        # 401 (bad token), 404 (wrong path), 5xx (Upstash outage) — these
        # are CONFIGURATION or TRANSIENT, not abuse signals. Fail-OPEN
        # with a loud log so admins notice and fix.
        print(f"[rate_limit] fail-open: Upstash HTTP {status}", flush=True)
        return RateLimitDecision(allowed=True, enforced=False)

    # 2xx — parse the body.
    try:
        results = response.json()
    except (ValueError, json.JSONDecodeError) as e:
        print(f"[rate_limit] fail-open: Upstash JSON decode error: {e!r}",
              flush=True)
        return RateLimitDecision(allowed=True, enforced=False)

    if not isinstance(results, list) or len(results) < 4:
        print(f"[rate_limit] fail-open: bad Upstash response shape: {results!r}",
              flush=True)
        return RateLimitDecision(allowed=True, enforced=False)

    def _int_result(idx: int) -> int | None:
        entry = results[idx]
        if isinstance(entry, dict):
            v = entry.get("result")
            if isinstance(v, int):
                return v
        return None

    min_count = _int_result(0)
    day_count = _int_result(2)
    if min_count is None or day_count is None:
        print(f"[rate_limit] fail-open: non-integer INCR result: {results!r}",
              flush=True)
        return RateLimitDecision(allowed=True, enforced=False)

    if min_count > per_min or day_count > per_day:
        retry_after = _retry_after_seconds(now, min_count, day_count, per_min, per_day)
        return RateLimitDecision(
            allowed=False,
            retry_after_seconds=max(1, retry_after),
            enforced=True,
        )

    return RateLimitDecision(allowed=True, enforced=True)
