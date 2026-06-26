# Security Review — oryon-ai-search-score / score.seoryon.com

**Date:** 2026-06-26
**Last updated:** 2026-06-26 (SSRF closed — §3.1 RESOLVED)
**Scope:** the static landing page (`web/`), the Vercel serverless backend (`api/score.py`), the published pip package (`oryon_score/`), and the GitHub repository.
**Methodology:** repo-wide grep for secrets and dangerous patterns; static review of every entry point; live probes of `/api/score` against safe SSRF canary targets; dependency review; pytest both-direction test suite for the SSRF guard.
**Ground rule applied:** safe fixes (static page, client JS, repo hygiene) were applied in the first pass. The SSRF fix (§3.1) was implemented in a dedicated second pass — with founder approval — and is now live.

---

## TL;DR

| Area | Verdict |
|---|---|
| Secrets in the repo | **Clean.** No tokens, API keys, `.env`, or credentials committed. |
| Static page / client JS | **Clean after this commit.** No third-party trackers, no inline scripts, and all dynamic strings rendered via `escapeHtml` except controlled-source `data-i18n-html` slots. |
| `/api/score` backend | **SSRF: RESOLVED** (§3.1, now closed end-to-end in `oryon_score/score.py` and shipped as `oryon-score` 0.2.0). Two MEDIUM findings remain: rate limiting is **scheduled as a dedicated next pass** with proper cross-instance infra (Upstash / Vercel KV) — deliberately not done in-memory because a per-cold-start in-memory limiter gives illusory protection. CORS is **kept open by design** (CLI `--api` mode + external integrators rely on it). |
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

### 3.1 SSRF — server-side request forgery — ✅ **RESOLVED 2026-06-26**

**What was shipped.** Defense-in-depth SSRF guard added to `oryon_score/score.py` at the single shared `_fetch()` chokepoint:

1. **Scheme allowlist** — only `http` and `https` survive validation. `file://`, `ftp://`, `gopher://`, `data:`, `javascript:`, schemeless `//host` are all refused.
2. **Hostname blocklist** — exact-match: `localhost`, `metadata`, `metadata.google.internal`, `metadata.aws`, `instance-data`, `ip6-localhost`, `ip6-loopback`. Suffix-match: `.internal`, `.local`, `.localhost`, `.intranet`, `.corp`, `.home`, `.lan`. Refused **before** any DNS call.
3. **DNS resolution + IP-range check** — `socket.getaddrinfo()` resolves the host, and **every** returned IP is checked against an explicit `_BLOCKED_NETS` list (loopback `127/8` + `::1`; RFC1918 `10/8`, `172.16/12`, `192.168/16`; CGNAT `100.64/10` — Python 3.14's `is_private` misses this so it's listed explicitly; link-local `169.254/16` incl. cloud metadata + `fe80::/10`; unique-local `fc00::/7`; unspecified `0/8` + `::/128`; multicast `224/4` + `ff00::/8`; reserved `240/4`; IETF protocol `192.0.0/24`; benchmark `198.18/15`). If **any** resolved address is in a blocked range, the request is refused.
4. **IPv4-mapped IPv6 unwrap** — `::ffff:169.254.169.254` is unwrapped to `169.254.169.254` before the range check (catches the common bypass attempt).
5. **Redirect re-validation** — the validator runs as an `httpx.Client(event_hooks={"request": [_ssrf_guard]})`. The hook fires on **every** outbound request — the initial fetch, the `/robots.txt` and `/llms.txt` secondary lookups, **and every redirect hop**. A public URL that 302s to `http://169.254.169.254/` is refused at the redirect target, not at the original URL.
6. **Fail-CLOSED** — any DNS error, parse error, or unknown address family returns the refusal, not the data.
7. **Uniform user-facing message** — every blocked case returns the same friendly string: `"We can only score public web pages — please paste a public URL."` so a hostile prober can't enumerate the blocklist by observing different errors, while a legitimate user who pastes their staging URL by mistake isn't made to feel they did something wrong.

**Proof.** `tests/test_ssrf.py` covers both directions:

| Category | Cases | Result |
|---|---|---|
| Scheme allowlist (file/ftp/gopher/data/javascript/about/no-scheme) | 7 | ✓ blocked |
| Hostname blocklist (localhost incl. `:8000`, metadata.google.internal, `*.internal`, `*.local`, `*.corp`, `*.home`, `*.lan`, trailing-dot variant) | 10 | ✓ blocked |
| IPv4 literals (169.254.169.254, 127/8, 10/8, 172.16/12, 192.168/16, CGNAT, 0.0.0.0, multicast, reserved, IETF protocol, benchmark) | 15 | ✓ blocked |
| IPv6 literals (`::1`, `::`, `fc00::1`, `fe80::1`, `ff00::1`) | 5 | ✓ blocked |
| IPv4-mapped IPv6 (`::ffff:169.254.169.254`, `::ffff:127.0.0.1`, `::ffff:10.0.0.1`) | 3 | ✓ blocked |
| Public IP literals (8.8.8.8, 1.1.1.1, example.com class, public IPv6) | 4 | ✓ allowed |
| DNS host → public IP | 1 | ✓ allowed |
| DNS host → metadata / loopback / RFC1918 | 3 | ✓ blocked |
| DNS error → fail-closed | 2 | ✓ blocked |
| Edge cases (no host, empty, unparseable, uniform-message invariant) | 4 | ✓ blocked / uniform |
| `_fetch()` short-circuits before any network call on initial-URL block | 8 | ✓ blocked |
| `_fetch()` passes through to a real public URL unchanged | 1 | ✓ allowed |
| **Redirect re-validation — public → 302 → metadata** | 1 | ✓ blocked at the redirect target |
| **Redirect re-validation — public → 302 → localhost** | 1 | ✓ blocked at the redirect target |
| Redirect public → public — no regression | 1 | ✓ allowed |
| `_ssrf_guard()` hook directly | 2 | ✓ correct |
| **Total** | **71** | **71 passed in 2.22s** |

**Live verification.** Probed `https://score.seoryon.com/api/score?url=…` post-deploy:
*Listed in the deploy log below this file — see the deploy notes appended at commit time.*

**DNS rebinding (TOCTOU) — closed.** The first iteration of this fix left a residual TOCTOU window between the validator's `getaddrinfo()` and httpx's connect-time DNS lookup. The Codex adversarial reviewer (Phase 7 of the build loop) caught it and refused to ship. The fix shipped is **module-level `socket.getaddrinfo` monkey-patching gated by a thread-local pin map**: when `_fetch()` enters, it stores the validator-approved IPs in `_DNS_PIN_TLS.pins`; while the pin is active, the patched `_pinning_getaddrinfo` returns ONLY those validated IPs for the same host within that thread; on `_fetch()` exit (success, error, or exception — `try/finally`) the pin is cleared. httpx's underlying transport calls `socket.getaddrinfo` internally to connect, so it hits the pinning shim and lands on a pre-approved IP. No second resolver call can be observed by the attacker, so DNS rebinding has no window to exploit.

Tested in `tests/test_ssrf.py::TestDnsRebinding` with a deliberately-flipping fake DNS that returns a public IP on the first call and `169.254.169.254` on the second. The test asserts the connect-time lookup returns only the public IP. (See also the tests covering pin scoping per host, pin clearing on exit, and pass-through when no pin is active.)

**One honest residual remains: per-thread isolation, not per-task.** The pin lives in a `threading.local()`. Python's `asyncio` runs many tasks on a single thread, so if `oryon-score` is ever wrapped to call `score_url()` concurrently from multiple asyncio tasks on the SAME thread, the pin would be shared and could be stomped on. This product's surface (Vercel serverless invocation per request + a sync `httpx.Client`) doesn't expose that pattern, but anyone embedding the package in an `asyncio` server should serialize `score_url()` calls or switch to a `contextvars`-based pin.

**Out of scope but worth flagging:** the same SSRF guard now also protects the **pip CLI**. A user running `oryon-score` locally still cannot use it to probe their own internal network — which protects anyone who later wraps the package behind a "scoring-as-a-service" without realising they'd inherit the SSRF.

### 3.2 No application-level rate limiting — **MEDIUM · SCHEDULED NEXT (deliberate separate pass)**

`api/score.py` has no per-IP / per-minute limit. Vercel's platform offers DDoS protection but nothing per-key. Anyone can run sustained scoring loops today. With the SSRF guard now closed (§3.1) the worst-case damage is Vercel compute cost, not data exposure — which lowers the urgency without eliminating it.

**This is being handled as a SEPARATE dedicated pass — not silently deferred.** The reason it wasn't bundled with the SSRF fix:

- A per-cold-start **in-memory** token bucket in a serverless function gives **illusory** protection: each function instance has its own counter, so a moderately popular `IP_HASH` lands on many instances and the effective rate limit is `n_instances × declared_limit`. That's not "rate limiting" — that's theater.
- Correct rate limiting needs **cross-instance state**: either Upstash Redis (`@upstash/ratelimit`), Vercel KV, or Vercel Edge Config. That's a small infrastructure addition that deserves its own review (latency budget against the 8 s function ceiling, fallback behavior on the rate-limit store being unreachable, how aggressive to be for the CLI's `--api` mode which legitimately fires bursts).

**Scheduled approach for the next pass:**
1. Add Upstash Redis as a Vercel integration (free tier covers tens of thousands of requests/day).
2. `@upstash/ratelimit` sliding window, ~30 req/min per IP, 90 req/min per IP burst.
3. Fail-OPEN on Upstash unreachable (don't take down the free public tool when the rate-limit store has an outage — log + degrade).
4. Returns HTTP 429 with `Retry-After`.

### 3.3 Permissive CORS — **MEDIUM · KEPT OPEN BY DESIGN**

`Access-Control-Allow-Origin: *` is intentional and **kept that way** after explicit review:
- The `oryon-score` CLI's `--api` mode (and the README example for calling `/api/score` from a notebook or CI) **depends on** open CORS.
- External integrators have started embedding the scorer; tightening would silently break them.
- With SSRF closed (§3.1), the cross-origin abuse vector this previously enabled — "any website's JS can use score.seoryon.com to scan internal addresses" — no longer applies.
- Residual risk (a third-party site using the open CORS to fire scoring loops from a visitor's browser) is mitigated by the rate-limit work above (§3.2), not by CORS tightening.

Decision: keep `*`, revisit only if a concrete abuse pattern emerges.

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

## What the first pass applied (safe items only)

1. Replaced the favicon with the SEOryon S-mark (no security impact, brand cleanup).
2. Made the landing trilingual + added the GEO education + FAQ + FAQPage JSON-LD.
3. Fixed the misstated "30-day" trial copy to the correct 3-day terms.
4. Added a `/privacy` page that **accurately** describes the data flow — including the backend, including the absence of analytics — rather than copy-pasting the Inspect "100% local" claim that would be **false** for this product.
5. Added `robots.txt` and `sitemap.xml` (the route table was tightened, with `/privacy` ahead of the catch-all).

## What the second pass applied (SSRF — with founder approval)

6. **Closed §3.1 (SSRF) at the shared `_fetch()` chokepoint** in `oryon_score/score.py`. Defense in depth: scheme allowlist + hostname blocklist + DNS-resolved IP range check + IPv4-mapped IPv6 unwrap + redirect re-validation via `event_hooks`. Fail-CLOSED on any error.
7. **Added `tests/test_ssrf.py`** — 71 cases, both directions including the public→302→internal redirect bypass.
8. **Bumped `oryon-score` to 0.2.0** and rebuilt the wheel (`dist/oryon_score-0.2.0-py3-none-any.whl`). PyPI upload is the founder's to run.

## What is still deliberately deferred

- **Rate limiting (§3.2): SCHEDULED NEXT** as a dedicated pass with Upstash / Vercel KV (the only way to get correct cross-instance limits in a serverless function). Listed in this file rather than dropped.
- **CORS (§3.3): kept open by design** (CLI `--api` mode and external integrators rely on it). With SSRF closed, the previous abuse vector no longer applies.
- **Error response shape (§3.4)**, **CSP headers (§2)**, **`pip-audit` in CI**: low-impact follow-ups, not blocking anything.

---

## Recommended next steps (in order of impact)

1. ~~**Approve the SSRF fix** (§3.1)~~ — ✅ shipped 2026-06-26 as `oryon-score` 0.2.0 + deployed backend.
2. **Republish `oryon-score` 0.2.0 to PyPI** (`twine upload dist/oryon_score-0.2.0*`) so CLI users inherit the protection.
3. **Add the rate limit** (§3.2): Upstash integration → `@upstash/ratelimit` → 30 req/min/IP sliding window → 429 with `Retry-After`. Fail-OPEN on Upstash unreachable.
4. **Tighten error response** (§3.4): generic 500 to the client, full exception in Vercel logs.
5. **Add CSP + security headers** to `vercel.json` (§2). Low risk, free win.
6. (Optional) **Add `pip-audit` to CI** so dependency CVEs surface automatically.
