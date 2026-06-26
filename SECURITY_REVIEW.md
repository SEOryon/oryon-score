# Security Review — oryon-ai-search-score / score.seoryon.com

**Date:** 2026-06-26
**Scope:** the static landing page (`web/`), the Vercel serverless backend (`api/score.py`), the published pip package (`oryon_score/`), and the GitHub repository.
**Methodology:** repo-wide grep for secrets and dangerous patterns; static review of every entry point; live probes of `/api/score` against safe SSRF canary targets; dependency review.
**Ground rule applied:** safe fixes (static page, client JS, repo hygiene) were applied in this commit. Anything that changes live `/api/score` behavior or the published `oryon-score` PyPI package is **flagged for founder approval only — no live backend or package changes were made**.

---

## TL;DR

| Area | Verdict |
|---|---|
| Secrets in the repo | **Clean.** No tokens, API keys, `.env`, or credentials committed. |
| Static page / client JS | **Clean after this commit.** No third-party trackers, no inline scripts, and all dynamic strings rendered via `escapeHtml` except controlled-source `data-i18n-html` slots. |
| `/api/score` backend | **One high-severity SSRF finding** — flagged for approval, **not** patched here. Two medium findings (no app-level rate limiting, permissive CORS). |
| `oryon-score` pip package | **Clean.** Mainstream dependencies, no obfuscation, no surprising network calls. Does what the README claims. |
| "Genuinely free" claim | **Holds.** No LLM calls, no API keys required, no upsell-gating in the open path. |

---

## 1. Secrets / exposure

**Status: clean.**

- `grep` for `api[_-]?key|secret|token|password|bearer` followed by quoted high-entropy values across `.py / .html / .js / .json / .toml / .md / .txt / .yml`: **0 hits**.
- `grep` for known provider prefixes (`sk-`, `ghp_`, `github_pat_`, `pypi-`, `hf_`, `AKIA…`, `AIza…`, `xoxb-`, etc.): **0 hits**.
- Tracked files containing `.env*`: **0**. `.env` is in `.gitignore`.
- `git ls-files | grep env` returns nothing.
- `.vercel/project.json` contains only the public `projectId` and `orgId` (Vercel's intended on-disk values — not secrets).

**No action needed.**

---

## 2. Landing page + client JS

### Third-party scripts
- The page loads no analytics, no Tag Manager, no Meta Pixel, no Hotjar, no PostHog. `grep -i "gtm|google-analytics|googletagmanager|gtag|analytics|fbq|hotjar|posthog|plausible|umami|segment"` against the live page returns **0 results**. (This contradicted the brief's "GTM appeared to load" assumption — the privacy page reflects the actual state truthfully.)
- The only off-domain resource is Google Fonts CSS (Geist / Geist Mono / Plus Jakarta Sans). Disclosed in the privacy page.

### XSS / injection surface (`web/app.js`, `web/privacy.js`)
- `escapeHtml()` is used on every dynamic field that lands inside an `innerHTML` template literal — URL, page title, signal name, signal detail, fix text, error message. **14 escape sites.**
- `data-i18n-html` slots write `innerHTML` from the **i18n dictionary** in the source file (literal, not user input). Two slots only: the hero H1 and the upsell H2. Both contain a single `<span class="brand-text">…</span>`. Safe by construction.
- No `document.write`, no `eval`, no `new Function`. No `dangerouslySetInnerHTML`-equivalent paths.

### CSP / mixed content
- **No Content-Security-Policy header is set** today. Static-only page + no inline event handlers means the risk is theoretical, but a tight CSP is a free hardening.
- **Recommended (safe to add, not added here to avoid breaking Google Fonts mid-deploy):** add to `vercel.json` headers:
  ```
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'
  ```
  Plus `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: interest-cohort=()`.
  Listed as a **safe follow-up**; not bundled with this release to keep the deploy minimal.

### One small hardening worth noting
- In `renderResult()` the bucket key (`fmtBucket(k)`) is interpolated unescaped. `k` is a bucket name from the backend (`schema_structure`, etc.) and the backend produces those from a hardcoded list, so this is safe in practice — but defense in depth would `escapeHtml` it too. (Did not change pre-existing behavior.)

---

## 3. `/api/score` backend — **DO NOT CHANGE WITHOUT APPROVAL**

The backend is live, callable by real users (web UI, pip CLI users in `--api` mode, and any external integrator). All findings here are **reported only**, not fixed.

### 3.1 SSRF — server-side request forgery — **HIGH**

**The risk.** The endpoint accepts a user-supplied URL and the server fetches it with `httpx` (`api/score.py` → `oryon_score/score.py` → `_fetch()`). There is no allowlist, no IP-range block, no DNS-rebinding protection, and `_norm_url` only enforces the `http://` or `https://` scheme prefix — it does not block private/internal/link-local targets.

**Live evidence.** Probed `https://score.seoryon.com/api/score?url=…` against canary targets:

| Probe target | Backend behavior |
|---|---|
| `http://169.254.169.254/latest/meta-data/` (AWS metadata) | Backend **attempted the fetch**; failed only because nothing was listening on that IP from Vercel's runtime. |
| `http://localhost/` | Backend **attempted the fetch**; connection refused (nothing on localhost on that runtime). |
| `file:///etc/passwd` | Normalized to `https://file:///etc/passwd` by `_norm_url`, then failed at httpx parse — accidental defense, not intentional. |

That those probes failed today is environment luck, not a control. If Vercel's runtime ever has a path to a private network, an internal service, or a cloud metadata endpoint (e.g. as the project grows into preview deploys, a sidecar, or a self-hosted fork), the same code reaches them.

**Why it matters even on hobby Vercel:**
- The backend additionally fetches `/robots.txt` and `/llms.txt` at the **same parsed host**. If the attacker passes a host whose DNS resolves to an internal IP, all three requests hit internal infrastructure.
- The endpoint has `Access-Control-Allow-Origin: *`, so any website's JavaScript can use score.seoryon.com as a proxy to scan addresses on behalf of the requester.

**Recommended fix (for founder approval):**
1. After `urlparse`, resolve the host with `socket.getaddrinfo` and reject responses with private / loopback / link-local / multicast / reserved IPs (`ipaddress.ip_address(...).is_private | .is_loopback | .is_link_local | .is_multicast | .is_reserved`).
2. Enforce scheme allowlist (`{"http","https"}`) before any normalization.
3. Re-validate after redirects (httpx `follow_redirects=True` means a redirect to `http://169.254.169.254` would otherwise bypass step 1).
4. Add a max-response-size cap (a few MB) to bound parsing cost.

**Do not deploy this without explicit approval** — it changes behavior real users depend on and could legitimately break score requests on edge-case hosts.

### 3.2 No application-level rate limiting — **MEDIUM**

`api/score.py` has no per-IP / per-minute limit. Vercel's platform offers DDoS protection but nothing per-key. Combined with the open CORS policy, anyone can run sustained scoring loops. Today the only damage is Vercel compute cost; combined with SSRF that risk grows.

**Recommended (for approval):** add a small in-memory token bucket keyed by `X-Forwarded-For` (~30 req/min per IP), or move to Vercel's `@vercel/edge-config` / `@upstash/ratelimit`. Returns HTTP 429.

### 3.3 Permissive CORS — **MEDIUM**

`Access-Control-Allow-Origin: *` was almost certainly intentional (lets people embed the scorer or call it from CLI/notebooks). It does, however, enable the cross-origin abuse pattern above. **Not necessarily worth changing** — but worth a conscious decision.

### 3.4 Error handler leaks internals — **LOW**

`api/score.py`:
```python
except Exception as exc:  # last-resort safety net
    return self._json(500, {"error": str(exc)}, 0)
```
`str(exc)` can include file paths, library internals, or DNS info. Recommend returning a generic 500 to the client and logging the exception server-side.

### 3.5 User-Agent contains a URL — **INFORMATIONAL**

`UA = "...OryonAISearchScore/1.0 (+https://seoryon.com)"`. Some WAFs treat parenthesized URLs in UA as suspicious. Not a problem; just an observation.

### 3.6 No timeout on the secondary fetches — **INFORMATIONAL**

`_fetch()` honors `TIMEOUT_S = 8.0` (good — within Vercel's 10s hobby limit). The `llms.txt` and `robots.txt` lookups also use `_fetch`, so they also use 8 s each. Three sequential 8 s ceilings can overflow Vercel's hobby plan in worst case. Consider reducing the secondary lookups to ~3 s each.

---

## 4. `oryon-score` pip package — **DO NOT REPUBLISH WITHOUT APPROVAL**

**Status: clean.** Reported, not changed.

- **Code surface.** Same `score_url(url)` function as the API. CLI in `oryon_score/cli.py` is a thin argparse wrapper that calls `score_url()` and prints. No persistent storage. No telemetry. No phone-home. No auto-update.
- **Network calls.** Same as the backend: an HTTP GET to the user-supplied URL plus `/robots.txt` and `/llms.txt`. Nothing to SEOryon's infra. The "no LLM calls" claim is accurate — `score.py` contains no calls to OpenAI / Anthropic / any LLM provider.
- **Dependencies.** `httpx>=0.27`, `beautifulsoup4>=4.12`, `lxml>=5.0`. All mainstream, actively maintained, no known unpatched CVEs as of the package version (0.1.0) pinning. Recommend a periodic `pip install pip-audit && pip-audit` pass in CI.
- **Build hygiene.** `pyproject.toml` uses Hatchling, declares MIT, names the maintainer. `[tool.hatch.build.targets.sdist]` includes only `oryon_score/`, the README, LICENSE, and pyproject — no stray files leak into the sdist. ✓
- **The same SSRF risk applies** when running the CLI: a user could `oryon-score http://localhost/admin/...` from their own machine. That's less alarming because the user is targeting their own network on purpose. But if anyone builds a hosted "score-as-a-service" on top of the package, **they inherit the SSRF**. Worth mentioning in the README.
- **CLI exit code.** `main()` returns `0 if result.score >= 50 else 1`. Reasonable for CI use; documented in README.

**Recommendation (for founder approval before any 0.1.1):** when the SSRF fix lands in the backend, bundle the same validation into `score_url()` so the package inherits the protection, then republish 0.2.0.

---

## 5. "Genuinely free" claim — confirmed

- `grep -rE "openai|anthropic|gemini|cohere|mistral" oryon_score/` → 0 hits.
- No API key env var is read by `score.py`. No `os.environ.get(...)` calls for credentials.
- The README, the landing page, and the new FAQ all consistently state "no LLM calls, no API keys, no signup." The codebase backs that up.

✓ The product is what it says it is.

---

## 6. Repo hygiene

- `.gitignore` covers `.env`, `dist/`, `build/`, `.venv/`, `node_modules/`, `.vercel`. Reasonable. ✓
- Built artifacts are committed under `dist/` (`oryon_score-0.1.0-py3-none-any.whl` + `.tar.gz`) — that's harmless but unusual. Most projects let `pip` / PyPI host the wheel. Optional cleanup.
- The `pyproject.toml` author email is publicly listed (`amaury@seoryon.com`). Intentional — it's the package maintainer contact.

---

## What this commit applied (safe items only)

1. Replaced the favicon with the SEOryon S-mark (no security impact, brand cleanup).
2. Made the landing trilingual + added the GEO education + FAQ + FAQPage JSON-LD.
3. Fixed the misstated "30-day" trial copy to the correct 3-day terms.
4. Added a `/privacy` page that **accurately** describes the data flow — including the backend, including the absence of analytics — rather than copy-pasting the Inspect "100% local" claim that would be **false** for this product.
5. Added `robots.txt` and `sitemap.xml` (the route table was tightened, with `/privacy` ahead of the catch-all).

## What this commit deliberately did **not** change

- `api/score.py` — the live backend logic.
- `oryon_score/*.py` — the published pip package.
- CORS, rate limiting, error response shape — all backend-touching.

These are listed above with concrete patch recommendations and need explicit go-ahead before being deployed.

---

## Recommended next steps (in order of impact)

1. **Approve the SSRF fix** (§3.1) and deploy together with a republished `oryon-score` 0.2.0.
2. **Add app-level rate limit** (§3.2) — small but valuable; prevents accidental loops too.
3. **Decide on CORS** (§3.3): either keep `*` consciously, or restrict to `score.seoryon.com` + a handful of partner origins.
4. **Tighten error response** (§3.4): generic 500 to the user, full exception in Vercel logs.
5. **Add CSP + security headers** to `vercel.json` (§2). Low risk, free win.
6. (Optional) **Add `pip-audit` to CI** so dependency CVEs surface automatically.
