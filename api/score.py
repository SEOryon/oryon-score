"""
Vercel Python serverless function: GET /api/score?url=...
Returns the JSON score for the requested URL.

Two protective layers run BEFORE the scoring engine:

  1. Rate limit (oryon_score.rate_limit) — Upstash-backed, cross-instance,
     20 req/min + 200 req/day per IP. Fails SAFE if env vars unset (ships
     before Upstash is provisioned); fails OPEN on Upstash error.

  2. SSRF guard (oryon_score.score._fetch) — refuses URLs that resolve to
     non-public addresses, validates every redirect hop, and pins the DNS
     answer to defeat rebinding. Always on; no env vars needed.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Make oryon_score importable when this file is the Vercel entry point.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oryon_score.score import score_url  # noqa: E402
from oryon_score.rate_limit import check_rate_limit, FRIENDLY_429_MSG  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict, cache_seconds: int = 600,
              extra_headers: dict | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if status == 200:
            self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
        if extra_headers:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        try:
            # Layer 1 — rate limit. Decides BEFORE we do any URL fetching or
            # scoring work, so an abuser can't drive load even on bad inputs.
            decision = check_rate_limit(self.headers.get)
            if not decision.allowed:
                return self._json(
                    429,
                    {"error": FRIENDLY_429_MSG},
                    cache_seconds=0,
                    extra_headers={"Retry-After": str(decision.retry_after_seconds)},
                )

            # Existing handler logic — unchanged.
            qs = parse_qs(urlparse(self.path).query)
            url_list = qs.get("url", [])
            url = url_list[0] if url_list else None
            if not url:
                return self._json(400, {"error": "Missing 'url' query parameter."}, 0)
            result = score_url(url)
            return self._json(200, result.to_dict())
        except Exception as exc:  # pragma: no cover - last-resort safety net
            return self._json(500, {"error": str(exc)}, 0)
