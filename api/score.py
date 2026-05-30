"""
Vercel Python serverless function: GET /api/score?url=...
Returns the JSON score for the requested URL.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Make src/ importable when this file is the entry point
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from oryon_score.score import score_url  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict, cache_seconds: int = 600) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if status == 200:
            self.send_header("Cache-Control", f"public, max-age={cache_seconds}")
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
            qs = parse_qs(urlparse(self.path).query)
            url_list = qs.get("url", [])
            url = url_list[0] if url_list else None
            if not url:
                return self._json(400, {"error": "Missing 'url' query parameter."}, 0)
            result = score_url(url)
            return self._json(200, result.to_dict())
        except Exception as exc:  # pragma: no cover - last-resort safety net
            return self._json(500, {"error": str(exc)}, 0)
