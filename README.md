# Oryon AI Search Readiness Score

> Score any URL for AI search readiness. Free, open-source, no signup.
> Try it live → **[score.seoryon.com](https://score.seoryon.com)**

[![License: MIT](https://img.shields.io/badge/License-MIT-9990FF.svg)](LICENSE)
[![PyPI](https://img.shields.io/badge/pip-oryon--score-9990FF)](https://pypi.org/project/oryon-score/)
[![GitHub stars](https://img.shields.io/github/stars/SEOryon/oryon-score?style=social)](https://github.com/SEOryon/oryon-score)

---

## What this is

A free tool that scores any URL on **27 signals** AI search engines use to decide what to cite, and returns the top fixes — ranked by impact.

Built and maintained by **[Oryon](https://seoryon.com)** — the SEO engine that writes and publishes articles built to rank AND get cited. This is the demo. Your whole site is the product.

```
$ oryon-score https://example.com/blog/ai-overview-guide

  Oryon AI Search Readiness Score
  https://example.com/blog/ai-overview-guide
  The AI Overview Guide: How to Get Cited by Google AI

  62/100  ·  Grade C

  By bucket
    Schema Structure       ████████████████░░░░░░░░  18.6/30
    Content Format         █████████████████░░░░░░░  17.0/25
    Authority              ████████████░░░░░░░░░░░░  12.0/20
    Crawlability           ███████████████████░░░░░  11.4/15
    Freshness              ███░░░░░░░░░░░░░░░░░░░░░   3.0/10

  Top fixes (in order of impact)
    ✗ FAQ schema  (No FAQPage schema.)
      → Wrap your FAQ section in FAQPage JSON-LD — highest-correlation signal.
    ✗ TL;DR / summary block near top  (No TL;DR or summary block found.)
      → Add a 50-word TL;DR after the H1. AI summarizers lift these at much higher rates.
    ✗ Last modified date  (No modification date detected.)
      → Expose a dateModified in JSON-LD or via Last-Modified header.
    ...

  Want continuous scoring across every page on your site?
  → Try Oryon free for 3 days: seoryon.com
```

---

## Why this exists

The market for AI citation tracking is dominated by dashboards starting at **€295/mo**. Most SEO teams just need to answer one question: *"is my page set up to get cited at all?"* That answer should be free.

This tool gives you that answer in 10 seconds. No signup. No tokens. Just paste a URL.

If you want **continuous scoring across every URL on your site**, plus AI citation tracking across ChatGPT / Perplexity / Gemini / Google AI, plus a writer that ships extractable articles automatically — that's [Oryon](https://seoryon.com). From €39/mo.

---

## What it actually checks

27 signals across 5 buckets that AI Overviews + LLM citation systems actually weight:

### Schema & structure (30 pts)
- Article / BlogPosting JSON-LD
- **FAQPage schema** (highest-correlation signal)
- HowTo schema
- BreadcrumbList schema
- Heading hierarchy (1 H1, ≥3 H2s)
- Definition lists (`<dl>`)
- Table markup
- Question-style H2s

### Content / format (25 pts)
- Word count in the 1200–3500 sweet spot
- Direct answer in the first 60 words
- TL;DR / summary block near the top
- Bold emphasis in the first section
- 3+ structured lists

### Authority (20 pts)
- Outbound links to .gov / .edu / Wikipedia
- 5–50 internal links (healthy range)
- Named author / byline (E-E-A-T)
- Outbound link density (3–30)
- `<blockquote>` / `<cite>` markup

### Crawlability (15 pts)
- HTTPS
- Canonical URL
- Mobile viewport
- Open Graph (≥3 og:* tags)
- `llms.txt` at site root
- `robots.txt` allows GPTBot, ClaudeBot, PerplexityBot, CCBot, Google-Extended, etc.

### Freshness (10 pts)
- `dateModified` or `Last-Modified` header
- Dated phrases in body ("as of May 2026")
- Year in title

Each signal has a **specific fix** — what to change, where to change it, why it matters. No fluff.

---

## Install

### Web (no install)
Just open **[score.seoryon.com](https://score.seoryon.com)** and paste a URL.

### CLI (pip)
```bash
pip install oryon-score

oryon-score https://example.com/blog/your-best-article
oryon-score https://example.com --json
oryon-score https://example.com --out report.json
```

Requires Python 3.10+.

### From source
```bash
git clone https://github.com/SEOryon/oryon-score
cd oryon-score
pip install -e .

oryon-score https://example.com
```

### Use in Python
```python
from oryon_score import score_url

result = score_url("https://example.com/blog/post")
print(result.score, result.grade)
for fix in result.fixes:
    print(" -", fix)
```

---

## Deploy your own (Vercel)

The `web/` + `api/` folders deploy as a Vercel project. Two files matter:

- `web/index.html` — the public scoring page
- `api/score.py` — the Python serverless endpoint

```bash
npm i -g vercel
vercel
```

Done. Your fork is now live at `your-project.vercel.app`. Add a custom domain in Vercel's dashboard.

---

## Sample output

See [`examples/example_output.json`](examples/example_output.json) for the full JSON shape returned by the API and the `--json` flag.

The web UI renders the same data with bucket bars, top fixes, and a "what's working" passlist.

---

## Why some sites score lower than they "should"

A score is not a verdict. It's a snapshot of *extractable* signals on the page itself. Three things this tool **does not** measure:

1. **Domain authority / backlink graph.** Out of scope. AI citation correlates with authority, but measuring it requires a third-party API and we kept this free.
2. **Whether the page is actually cited today.** Use the [Citation Intelligence MCP](https://github.com/AutomateLab-tech/citation-intelligence) by AutomateLab for live LLM citation data.
3. **Brand authority signals.** Wikipedia mentions, press coverage, Reddit references — they matter, and the tool flags some, but it can't grade them holistically.

For all three layers, see [Oryon](https://seoryon.com) — that's what the paid product does.

---

## How it stays free

- Runs on Vercel's free Python runtime
- No third-party APIs, no API keys to maintain
- No tracking, no telemetry, no user accounts
- Self-hostable in one click

Open source under MIT. Fork it, run it on your own infra, change it, ship it.

---

## SSRF guard (0.2.0+)

Both the hosted scorer and the pip CLI refuse to fetch URLs that resolve to
non-public addresses — RFC1918 / loopback / link-local (incl. `169.254.169.254`
cloud metadata) / IPv6 ULA / multicast / reserved — and re-validate on every
redirect hop. Public URLs are unaffected. See `SECURITY_REVIEW.md` §3.1 for
the full design + test matrix.

If you wrap `score_url()` behind your own hosted endpoint, **you inherit this
guard** — don't disable it without re-reading §3.1.

---

## Inspired by

This tool's structured-signal approach was inspired by [`citation-intelligence`](https://github.com/AutomateLab-tech/citation-intelligence) by AutomateLab — a self-hosted MCP server for measuring LLM citation visibility. Go check it out if you want programmatic citation data from inside Claude Code or Cursor. This tool solves a different layer (page readiness, not live citation queries) and is original work.

---

## Contributing

PRs welcome. Especially:
- New signals (anything with a published correlation study)
- Translations of the web UI
- WordPress / Webflow / Shopify integrations
- A GitHub Action that scores changed URLs on every PR

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE).

Built by **[Oryon](https://seoryon.com)** · Your Organic Growth Engine.
Follow [@SEOryon](https://instagram.com/SEOryon) for SEO content that doesn't lie.
