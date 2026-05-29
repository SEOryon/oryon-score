"""
oryon-score CLI — score any URL for AI search readiness.

Usage:
    oryon-score https://example.com
    oryon-score https://example.com --json
    oryon-score https://example.com --out report.json
"""
from __future__ import annotations

import argparse
import json
import sys

from .score import score_url

# ANSI colors — keep it minimal, fall back gracefully
def _supports_color() -> bool:
    return sys.stdout.isatty() and not bool(__import__("os").environ.get("NO_COLOR"))

C = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "violet": "\033[38;5;99m",
    "green": "\033[32m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "gray": "\033[90m",
} if _supports_color() else {k: "" for k in ["reset", "bold", "dim", "violet", "green", "red", "yellow", "gray"]}


def _bar(percent: float, width: int = 24) -> str:
    filled = int(round(percent / 100 * width))
    return f"{C['violet']}{'█' * filled}{C['gray']}{'·' * (width - filled)}{C['reset']}"


def _print_report(result):
    print()
    print(f"  {C['bold']}Oryon AI Search Readiness Score{C['reset']}")
    print(f"  {C['gray']}{result.url}{C['reset']}")
    if result.page_title:
        print(f"  {C['dim']}{result.page_title[:80]}{C['reset']}")
    print()

    # Fetch failed — show that clearly instead of a fake zero score
    if result.grade == "—" or (result.score == 0 and not result.signals):
        msg = result.notes[0] if result.notes else "Fetch failed."
        print(f"  {C['red']}{C['bold']}✗ Could not score this URL{C['reset']}")
        print(f"  {C['gray']}{msg}{C['reset']}")
        print()
        print(f"  {C['dim']}Common causes: bot protection (Cloudflare), paywall, JS-only site,{C['reset']}")
        print(f"  {C['dim']}or the page requires login. Try a different URL on the same domain.{C['reset']}")
        print()
        return

    grade_color = C["green"] if result.score >= 70 else (C["yellow"] if result.score >= 50 else C["red"])
    print(f"  {grade_color}{C['bold']}{result.score}/100  ·  Grade {result.grade}{C['reset']}")
    print()

    print(f"  {C['bold']}By bucket{C['reset']}")
    for bucket, info in result.bucket_scores.items():
        name = bucket.replace("_", " ").title()
        bar = _bar(info["percent"])
        print(f"    {name:<22} {bar}  {info['earned']:>4}/{int(info['max']):<3}")
    print()

    passed = [s for s in result.signals if s.passed]
    failed = [s for s in result.signals if not s.passed]

    if failed:
        print(f"  {C['bold']}Top fixes{C['reset']}  {C['gray']}(in order of impact){C['reset']}")
        for s in sorted(failed, key=lambda s: -s.weight)[:8]:
            print(f"    {C['red']}✗{C['reset']} {C['bold']}{s.name}{C['reset']}  {C['gray']}({s.detail}){C['reset']}")
            if s.fix:
                print(f"      {C['gray']}→{C['reset']} {s.fix}")
        print()

    if passed:
        print(f"  {C['bold']}What's working{C['reset']}")
        for s in passed[:6]:
            print(f"    {C['green']}✓{C['reset']} {s.name}  {C['gray']}— {s.detail}{C['reset']}")
        print()

    print(f"  {C['dim']}Want continuous scoring across every page on your site?{C['reset']}")
    print(f"  {C['violet']}→ Try Oryon free for 3 days: seoryon.com{C['reset']}")
    print()


def main() -> int:
    p = argparse.ArgumentParser(
        prog="oryon-score",
        description="Score any URL for AI search readiness. Inspired by Oryon.",
    )
    p.add_argument("url", help="The URL to score (with or without https://)")
    p.add_argument("--json", action="store_true", help="Output JSON only, no human format")
    p.add_argument("--out", help="Write JSON report to file")
    args = p.parse_args()

    try:
        result = score_url(args.url)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Saved report to {args.out}")

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        _print_report(result)

    return 0 if result.score >= 50 else 1


if __name__ == "__main__":
    sys.exit(main())
