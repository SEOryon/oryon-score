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
      → If the page has a visible FAQ section, mirror it in FAQPage JSON-LD.
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
- **FAQPage schema** (only when the page has a visible FAQ — no rich-result promise; Google removed FAQ rich results for all sites in May 2026)
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

## Rate limiting (hosted `/api/score`)

The hosted endpoint at `score.seoryon.com/api/score` is rate-limited per IP
to protect against abuse:

| Window     | Cap                        |
|------------|----------------------------|
| Per minute | **20 requests / IP / min** |
| Per day    | **200 requests / IP / day** |

Either threshold returns **HTTP 429** with a friendly JSON message and a
`Retry-After` header (seconds until the next request from that IP could
succeed). A normal user evaluating the tool — or an agency auditing a whole
site in one sitting — will not hit these.

State lives in [Upstash Redis](https://upstash.com/) via its REST API
(cross-instance — every Vercel cold-start sees the same counters). The
critical-section is an atomic `INCR` so concurrent requests cannot race past
the cap. Reads are best-effort: if Upstash is unreachable, the endpoint
**fails OPEN** (serves the request, logs the error) — availability over
strict limiting for a free public tool. The SSRF guard still applies, so
the dangerous path is protected regardless.

### Activating rate limiting on your own deployment

The limiter is **off** until two env vars are present. Until then, every
request passes through and the function logs one warning at startup. To
turn it on:

1. **Create an Upstash Redis database** at [console.upstash.com](https://console.upstash.com/). The free tier is enough for low-volume use; if you expect non-trivial traffic, upgrade to Pay-As-You-Go ($0.20 per 100K commands). The rate limiter sends 4 commands per scored request — heavy traffic can drain the free tier's daily quota, which the limiter treats as an abuse signal (see "Quota burn" below).
2. From the database's **REST API** tab, copy:
   - `UPSTASH_REDIS_REST_URL`  (looks like `https://us1-foo-12345.upstash.io`)
   - `UPSTASH_REDIS_REST_TOKEN` (long opaque string)
3. In **Vercel → Project → Settings → Environment Variables**, add both for the **Production** environment (and **Preview** / **Development** if you want the same limits there). Mark the token as a Secret.
4. Optional overrides — set if you want different caps without a code change:
   - `RATE_LIMIT_PER_MINUTE` (default `20`)
   - `RATE_LIMIT_PER_DAY` (default `200`)
5. **Redeploy** the project (Vercel applies env-var changes on the next deploy). The next cold start picks up the new variables and the limiter activates automatically.

Verify it's on by sending 21 requests in under a minute from the same IP —
the 21st should return 429.

### Quota burn (why fail-CLOSED on Upstash 429/403)

Each scored request sends 4 commands to Upstash. An attacker can intentionally
drain the daily Upstash quota (free-tier: 10K commands/day) and rely on the
"store-error" path silently switching the limiter OFF. The limiter prevents
this by treating Upstash's own `429` or `403` responses as an abuse signal:
when Upstash is rate-limiting us, the endpoint **fails CLOSED** (returns 429
to every user) instead of failing OPEN. You'll notice immediately because
every request 429s; the fix is to raise the Upstash quota (upgrade the plan
or rotate to a larger DB) — an attacker that paid for proxy traffic to burn
the quota gets no bypass for their trouble.

Transient errors (timeout, 5xx, bad token, JSON parse error) still fail-OPEN,
so a real outage doesn't take the tool down.

### CLI users

The `oryon-score` CLI calls `score_url()` **directly on your own machine** —
it does NOT go through `/api/score`. CLI users are therefore not rate-
limited by the hosted endpoint; they are limited only by their own
machine's network and CPU.

---

## Changelog

### 0.3.0 — 2026-07-17

- **Fixed: the llms.txt check no longer passes on files that don't exist.** The old rule
  (`HTTP 200 + length > 50`) awarded 3/3 to any SPA host whose catch-all rewrite serves the
  homepage for missing paths — proven live against the hosted scorer itself. The check now
  requires plain text (rejects `text/html` by header or body sniff) **and** runs a soft-404
  control probe: a nonsense path at the same root must come back clearly distinct — a clean
  404/410, a redirect (while llms.txt is served directly), or the site's HTML shell. Any
  ambiguous outcome fails closed. Weight
  unchanged (3 pts); ambiguity fails closed.
- **Fixed: brotli decode.** `_fetch()` advertised `Accept-Encoding: br` without a brotli backend
  installed, so every DOM signal silently scored 0 against brotli-serving origins (most of the
  modern web) — the hosted scorer graded its own homepage 20/F. `brotli>=1.1` is now a declared
  dependency, with a regression test (`tests/test_brotli.py`).
- **Honest copy: schema fix strings no longer promise rich results or citation correlations.**
  "Highest-correlation signal for AI Overview citations" (FAQ), "Required for most AI Overview
  citations" (Article) and "Heavily lifted by AI summarizers" (HowTo) are gone — Google removed
  FAQ rich results for all sites in May 2026 (after restricting them to gov/health in 2023)
  and retired HowTo rich results in 2023; no
  controlled study supports a schema→citation correlation. The strings now describe what
  structured data actually does: make the page machine-readable and unambiguous. Copy only —
  no weight changed.
- score.seoryon.com now serves a real `/llms.txt` (text/plain), so its own llms.txt point is
  earned rather than phantom.

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
