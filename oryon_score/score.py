"""
Oryon AI Search Readiness Score
Core scoring engine. Takes a URL, returns 0-100 score + per-signal results + fixes.

No LLM calls. No API keys. Pure HTML parsing + signal heuristics.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# Browser-like UA to get past basic bot walls (Cloudflare, etc.).
# We still identify in Accept headers + an optional X-Tool header so we're
# not pretending to be anything we're not.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 "
    "OryonAISearchScore/1.0 (+https://seoryon.com)"
)
TIMEOUT_S = 8.0  # Stay under Vercel's hobby 10s function limit, leaving time for parsing

# AI crawler user agents we check robots.txt against
AI_CRAWLERS = [
    "GPTBot",
    "ClaudeBot",
    "PerplexityBot",
    "CCBot",
    "Google-Extended",
    "Applebot-Extended",
    "Bytespider",
    "anthropic-ai",
    "FacebookBot",
]

# 5 buckets that add up to 100
WEIGHTS = {
    "schema_structure": 30,
    "content_format": 25,
    "authority": 20,
    "crawlability": 15,
    "freshness": 10,
}


@dataclass
class SignalResult:
    name: str
    bucket: str
    passed: bool
    weight: float                 # points possible if signal == binary; or weight share within bucket
    points: float                 # actual points earned (0..weight)
    detail: str
    fix: str | None = None        # 1-line actionable fix when failed


@dataclass
class ScoreResult:
    url: str
    score: int                    # 0-100
    grade: str                    # A+ A B C D F
    fetched_at: str
    page_title: str | None
    bucket_scores: dict[str, dict[str, float]] = field(default_factory=dict)
    signals: list[SignalResult] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["signals"] = [asdict(s) for s in self.signals]
        return d


def _grade(score: int) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "F"


def _norm_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _fetch(url: str) -> tuple[httpx.Response | None, str | None]:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Tool": "OryonAISearchScore/1.0",
    }
    try:
        with httpx.Client(
            timeout=TIMEOUT_S, follow_redirects=True, headers=headers
        ) as client:
            r = client.get(url)
        if r.status_code >= 400:
            sc = r.status_code
            if sc == 404:
                msg = f"HTTP 404 — that URL doesn't exist. Double-check the path."
            elif sc in (401, 403):
                msg = f"HTTP {sc} — the site blocked our request (bot protection / paywall / login required)."
            elif sc == 429:
                msg = f"HTTP 429 — rate-limited. Wait a minute and try again."
            elif sc >= 500:
                msg = f"HTTP {sc} — the site is broken right now. Try again later."
            else:
                msg = f"HTTP {sc} {r.reason_phrase}"
            return None, msg
        return r, None
    except httpx.HTTPError as e:
        return None, f"Fetch failed: {e!s}"


def _fetch_text(url: str) -> str:
    r, _ = _fetch(url)
    if r is None or r.status_code >= 400:
        return ""
    return r.text


# ============ SIGNAL CHECKS ============

def _check_https(parsed_url) -> SignalResult:
    ok = parsed_url.scheme == "https"
    return SignalResult(
        name="HTTPS",
        bucket="crawlability",
        passed=ok,
        weight=2,
        points=2 if ok else 0,
        detail="Served over HTTPS." if ok else "Page is not HTTPS.",
        fix=None if ok else "Move the site to HTTPS — AI crawlers and Google demote http URLs.",
    )


def _check_canonical(soup: BeautifulSoup, url: str) -> SignalResult:
    tag = soup.find("link", attrs={"rel": "canonical"})
    if not tag or not tag.get("href"):
        return SignalResult(
            "Canonical URL", "crawlability", False, 2, 0,
            "No canonical link tag found.",
            "Add a `<link rel=\"canonical\" href=\"...\">` to lock the canonical URL for this page.",
        )
    return SignalResult(
        "Canonical URL", "crawlability", True, 2, 2,
        f"Canonical: {tag['href']}", None,
    )


def _check_viewport(soup: BeautifulSoup) -> SignalResult:
    tag = soup.find("meta", attrs={"name": "viewport"})
    ok = bool(tag and tag.get("content"))
    return SignalResult(
        "Mobile viewport", "crawlability", ok, 2, 2 if ok else 0,
        "Mobile viewport meta present." if ok else "No mobile viewport meta tag.",
        None if ok else "Add `<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">` to head.",
    )


def _check_open_graph(soup: BeautifulSoup) -> SignalResult:
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
    ok = len(og_tags) >= 3
    return SignalResult(
        "Open Graph tags", "crawlability", ok, 2, 2 if ok else 0,
        f"Found {len(og_tags)} og:* tags." if og_tags else "No Open Graph tags.",
        None if ok else "Add og:title, og:description, og:image, og:url — AI summarizers lift them.",
    )


def _check_llms_txt(parsed_url) -> SignalResult:
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"
    r, _ = _fetch(f"{base}/llms.txt")
    ok = r is not None and r.status_code == 200 and len(r.text) > 50
    return SignalResult(
        "llms.txt file", "crawlability", ok, 3, 3 if ok else 0,
        "llms.txt present at site root." if ok else "No /llms.txt found.",
        None if ok else "Add a /llms.txt file at the site root following llmstxt.org spec.",
    )


def _check_robots_ai(parsed_url) -> SignalResult:
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"
    r, _ = _fetch(f"{base}/robots.txt")
    if r is None or r.status_code != 200:
        return SignalResult(
            "Robots allows AI crawlers", "crawlability", True, 4, 4,
            "No robots.txt — AI crawlers can fetch by default.", None,
        )
    text = r.text.lower()
    blocked = []
    for bot in AI_CRAWLERS:
        pat = re.compile(
            rf"user-agent:\s*{re.escape(bot.lower())}\s*\n((?:[a-z-]+:.*\n?)+)",
            re.IGNORECASE,
        )
        for m in pat.finditer(text):
            block = m.group(1)
            if re.search(r"disallow:\s*/(\s|$)", block):
                blocked.append(bot)
                break
    if blocked:
        return SignalResult(
            "Robots allows AI crawlers", "crawlability", False, 4, max(0, 4 - len(blocked)),
            f"Blocking these AI crawlers via robots.txt: {', '.join(blocked)}.",
            f"Remove the Disallow rules for: {', '.join(blocked)} unless intentional. AI overviews need access to cite you.",
        )
    return SignalResult(
        "Robots allows AI crawlers", "crawlability", True, 4, 4,
        "All major AI crawlers allowed in robots.txt.", None,
    )


# Schema & structure
def _extract_jsonld(soup: BeautifulSoup) -> list[dict]:
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            out.extend([d for d in data if isinstance(d, dict)])
    return out


def _schema_types(jsonld: list[dict]) -> set[str]:
    types: set[str] = set()
    for entry in jsonld:
        graph = entry.get("@graph", [entry]) if "@graph" in entry else [entry]
        for node in graph:
            t = node.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                types.update(str(x) for x in t)
    return types


def _check_article_schema(types: set[str]) -> SignalResult:
    has = bool(types & {"Article", "NewsArticle", "BlogPosting", "TechArticle"})
    return SignalResult(
        "Article schema", "schema_structure", has, 5, 5 if has else 0,
        f"Article-type schema present: {sorted(types & {'Article', 'NewsArticle', 'BlogPosting', 'TechArticle'})}" if has
        else "No Article / BlogPosting / NewsArticle schema found.",
        None if has else "Add JSON-LD with @type: Article (or BlogPosting). Required for most AI Overview citations.",
    )


def _check_faq_schema(types: set[str]) -> SignalResult:
    has = "FAQPage" in types
    return SignalResult(
        "FAQ schema", "schema_structure", has, 6, 6 if has else 0,
        "FAQPage JSON-LD present." if has else "No FAQPage schema.",
        None if has else "Wrap your FAQ section in FAQPage JSON-LD — highest-correlation signal for AI Overview citations.",
    )


def _check_howto_schema(types: set[str]) -> SignalResult:
    has = "HowTo" in types
    return SignalResult(
        "HowTo schema", "schema_structure", has, 3, 3 if has else 0,
        "HowTo schema present." if has else "No HowTo schema.",
        None if has else "If your page has steps, add HowTo schema. Heavily lifted by AI summarizers.",
    )


def _check_breadcrumb_schema(types: set[str]) -> SignalResult:
    has = "BreadcrumbList" in types
    return SignalResult(
        "Breadcrumb schema", "schema_structure", has, 3, 3 if has else 0,
        "BreadcrumbList schema present." if has else "No BreadcrumbList schema.",
        None if has else "Add BreadcrumbList JSON-LD — helps AI understand site hierarchy.",
    )


def _check_heading_structure(soup: BeautifulSoup) -> SignalResult:
    # Count semantic h1s + ARIA-level-1 headings (modern frameworks often do <div role="heading" aria-level="1">)
    h1s = soup.find_all("h1")
    aria_h1s = soup.find_all(attrs={"role": "heading", "aria-level": "1"})
    h2s = soup.find_all("h2") + soup.find_all(attrs={"role": "heading", "aria-level": "2"})
    h1_count = len(h1s) + len(aria_h1s)
    h2_count = len(h2s)

    # Many modern pages style the title with CSS instead of <h1>. If we found a title tag,
    # treat that as the implicit primary heading.
    if h1_count == 0 and soup.find("title"):
        h1_count = 1
        detail_h1 = "(no explicit <h1>; using <title> as implicit primary heading)"
    else:
        detail_h1 = ""

    if h1_count == 1 and h2_count >= 3:
        return SignalResult(
            "Heading structure", "schema_structure", True, 4, 4,
            f"1 H1, {h2_count} H2s. Clean hierarchy. {detail_h1}".strip(), None,
        )
    fix = []
    if h1_count == 0:
        fix.append("No H1 detected. Add exactly one <h1> with the page's primary title.")
    elif h1_count > 1:
        fix.append(f"{h1_count} H1 tags found — should be exactly one.")
    if h2_count < 3:
        fix.append(f"Only {h2_count} H2s. AI extractors chunk by H2 — add more sectioning.")
    partial = 2 if (h1_count >= 1 and h2_count >= 2) else 1
    return SignalResult(
        "Heading structure", "schema_structure", False, 4, partial,
        f"{h1_count} H1, {h2_count} H2s. {detail_h1}".strip(),
        " ".join(fix) if fix else "Improve heading hierarchy.",
    )


def _check_definition_lists(soup: BeautifulSoup) -> SignalResult:
    dl = soup.find_all("dl")
    ok = len(dl) >= 1
    return SignalResult(
        "Definition lists", "schema_structure", ok, 3, 3 if ok else 0,
        f"{len(dl)} `<dl>` elements." if ok else "No definition lists.",
        None if ok else "Use `<dl><dt>term</dt><dd>definition</dd></dl>` for glossary-style content — strong lift signal.",
    )


def _check_tables(soup: BeautifulSoup) -> SignalResult:
    tables = soup.find_all("table")
    ok = len(tables) >= 1
    return SignalResult(
        "Table markup", "schema_structure", ok, 3, 3 if ok else 0,
        f"{len(tables)} `<table>` element(s)." if ok else "No tables.",
        None if ok else "Comparison data deserves real `<table>` markup, not images of tables. AI lifts these.",
    )


def _check_question_h2s(soup: BeautifulSoup) -> SignalResult:
    h2s = soup.find_all("h2")
    q_count = sum(1 for h in h2s if h.get_text(strip=True).rstrip().endswith("?"))
    ok = q_count >= 2
    return SignalResult(
        "Question-style H2s", "schema_structure", ok, 3, min(3, q_count),
        f"{q_count} H2s end with a question mark." if q_count else "No question-style H2s.",
        None if ok else "Convert ≥2 H2s to actual user questions. AI Overviews extract Q&A patterns disproportionately.",
    )


# Content / format
def _word_count(soup: BeautifulSoup) -> int:
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return len(re.findall(r"\b\w+\b", text))


def _check_word_count(wc: int) -> SignalResult:
    if 1200 <= wc <= 3500:
        return SignalResult(
            "Word count (lift-worthy range)", "content_format", True, 5, 5,
            f"{wc} words — in the lift-worthy range (1200–3500).", None,
        )
    if 800 <= wc < 1200 or 3500 < wc <= 5000:
        return SignalResult(
            "Word count (lift-worthy range)", "content_format", False, 5, 2,
            f"{wc} words — outside the sweet spot (1200–3500).",
            "Aim for 1500–2500 words. Thin pages and bloated pages both lose extraction priority.",
        )
    return SignalResult(
        "Word count (lift-worthy range)", "content_format", False, 5, 0,
        f"{wc} words — too {'thin' if wc < 800 else 'long'}.",
        "Aim for 1500–2500 words with one clear answer per section.",
    )


def _check_first_paragraph_answer(soup: BeautifulSoup) -> SignalResult:
    article = soup.find("article") or soup.find("main") or soup.body
    if not article:
        return SignalResult(
            "Answer in first 60 words", "content_format", False, 5, 0,
            "Could not detect a main content region.",
            "Wrap the article body in `<article>` or `<main>` for clean extraction.",
        )
    # Skip empty / very-short paragraphs (captions, bylines, image text) before finding the real first paragraph
    first_text = ""
    first_word_n = 0
    for p in article.find_all("p"):
        text = p.get_text(strip=True)
        if not text:
            continue
        words = re.findall(r"\b\w+\b", text)
        if len(words) < 8:
            continue
        first_text = text
        first_word_n = len(words)
        break

    if first_word_n == 0:
        return SignalResult(
            "Answer in first 60 words", "content_format", False, 5, 0,
            "No non-trivial first paragraph found in main content.",
            "Open with a real <p> of 15–60 words that directly answers the page's question.",
        )

    ok = 15 <= first_word_n <= 60 and first_text.endswith((".", "!", "?"))
    return SignalResult(
        "Answer in first 60 words", "content_format", ok, 5,
        5 if ok else (2 if first_word_n >= 15 else 1),
        f"First real paragraph: {first_word_n} words." if ok
        else f"First real paragraph is {first_word_n} words — outside the AI-lift sweet spot of 15–60.",
        None if ok else "Cut the intro. The first paragraph should be a 15–60 word direct answer to the page's core question.",
    )


def _check_tldr(soup: BeautifulSoup) -> SignalResult:
    text = soup.get_text(separator=" ", strip=True).lower()
    has = bool(re.search(r"\btl;dr\b|\btldr\b|\bin short\b|\bsummary\b", text[:2000]))
    return SignalResult(
        "TL;DR / summary block near top", "content_format", has, 5, 5 if has else 0,
        "TL;DR or summary detected near the top of the page." if has else "No TL;DR or summary block found.",
        None if has else "Add a 50-word TL;DR after the H1. AI summarizers lift TL;DR blocks at much higher rates.",
    )


def _check_bold_answer(soup: BeautifulSoup) -> SignalResult:
    article = soup.find("article") or soup.find("main") or soup.body
    if not article:
        return SignalResult("Bold answer in first section", "content_format", False, 5, 0,
                            "No main content region detected.", None)
    first_p = article.find("p")
    if not first_p:
        return SignalResult("Bold answer in first section", "content_format", False, 5, 0,
                            "No paragraph found.", None)
    has_bold = bool(first_p.find(["strong", "b"]))
    return SignalResult(
        "Bold answer in first section", "content_format", has_bold, 5, 5 if has_bold else 0,
        "First paragraph contains a `<strong>` or `<b>` tag." if has_bold
        else "First paragraph has no bold emphasis.",
        None if has_bold else "Bold the literal answer in the first paragraph. Visual emphasis = extraction signal.",
    )


def _check_lists(soup: BeautifulSoup) -> SignalResult:
    lists = soup.find_all(["ol", "ul"])
    ok = len(lists) >= 3
    return SignalResult(
        "Structured lists", "content_format", ok, 5, min(5, len(lists)),
        f"{len(lists)} list elements." if lists else "No ordered/unordered lists.",
        None if ok else "Use real list markup (3+ ol/ul) — AI Overviews favor structured enumeration.",
    )


# Authority
def _check_external_authority_links(soup: BeautifulSoup, page_host: str) -> SignalResult:
    links = soup.find_all("a", href=True)
    external_auth = 0
    auth_tlds = (".gov", ".edu", ".ac.uk", "wikipedia.org")
    for a in links:
        try:
            href = a["href"]
            if not href.startswith("http"):
                continue
            host = urlparse(href).netloc.lower()
            if host == page_host:
                continue
            if any(host.endswith(t) for t in auth_tlds):
                external_auth += 1
        except (KeyError, ValueError):
            continue
    ok = external_auth >= 2
    return SignalResult(
        "Authority outbound links", "authority", ok, 5, min(5, external_auth),
        f"{external_auth} link(s) to .gov / .edu / Wikipedia." if external_auth
        else "No outbound links to authority domains.",
        None if ok else "Cite 2+ authority sources (.gov, .edu, Wikipedia). Provenance is an extraction signal.",
    )


def _check_internal_links(soup: BeautifulSoup, page_host: str) -> SignalResult:
    links = soup.find_all("a", href=True)
    internal = 0
    for a in links:
        href = a["href"]
        if href.startswith("/") and not href.startswith("//"):
            internal += 1
        elif href.startswith("http"):
            try:
                if urlparse(href).netloc.lower() == page_host:
                    internal += 1
            except ValueError:
                continue
    ok = 5 <= internal <= 50
    return SignalResult(
        "Internal linking", "authority", ok, 4, 4 if ok else (2 if internal else 0),
        f"{internal} internal links." if internal else "No internal links detected.",
        None if ok else "5–50 internal links is the healthy range. Below = orphan; above = link soup.",
    )


def _check_author_byline(soup: BeautifulSoup, jsonld: list[dict]) -> SignalResult:
    # JSON-LD author field
    has_author = False
    for entry in jsonld:
        nodes = entry.get("@graph", [entry])
        for n in nodes:
            if isinstance(n, dict) and n.get("author"):
                has_author = True
                break
        if has_author:
            break
    # Or visible byline
    if not has_author:
        text = soup.get_text(separator=" ", strip=True).lower()
        has_author = bool(re.search(r"\bby [a-z]+\s+[a-z]+\b|written by\b|author:", text[:3000]))
    return SignalResult(
        "Named author / byline", "authority", has_author, 5, 5 if has_author else 0,
        "Author named (schema or visible byline)." if has_author else "No author byline detected.",
        None if has_author else "Name a real author with a profile page. E-E-A-T's first E = experience, and that means a person.",
    )


def _check_external_link_density(soup: BeautifulSoup, page_host: str) -> SignalResult:
    links = soup.find_all("a", href=True)
    external = 0
    for a in links:
        href = a["href"]
        if href.startswith("http"):
            try:
                if urlparse(href).netloc.lower() != page_host:
                    external += 1
            except ValueError:
                continue
    ok = 3 <= external <= 30
    return SignalResult(
        "Outbound link density", "authority", ok, 3, 3 if ok else 1,
        f"{external} outbound links." if external else "No outbound links.",
        None if ok else "Cite sources liberally (3–30 outbound). AI prioritizes content with clear provenance.",
    )


def _check_reviews_or_quotes(soup: BeautifulSoup) -> SignalResult:
    blockquotes = soup.find_all("blockquote")
    cites = soup.find_all("cite")
    total = len(blockquotes) + len(cites)
    ok = total >= 1
    return SignalResult(
        "Quotes & citations markup", "authority", ok, 3, 3 if ok else 0,
        f"{len(blockquotes)} `<blockquote>`, {len(cites)} `<cite>`." if total else "No `<blockquote>` or `<cite>` tags.",
        None if ok else "Wrap quotes in `<blockquote>`. AI summarizers credit quoted sources back to the original.",
    )


# Freshness
def _check_last_modified(response, jsonld: list[dict]) -> SignalResult:
    # Try Last-Modified header
    lm = response.headers.get("last-modified") if response else None
    # Try date in JSON-LD
    date_modified = None
    for entry in jsonld:
        nodes = entry.get("@graph", [entry])
        for n in nodes:
            if isinstance(n, dict):
                if n.get("dateModified"):
                    date_modified = n["dateModified"]
                    break
        if date_modified:
            break
    has = bool(lm or date_modified)
    detail = f"dateModified: {date_modified}" if date_modified else (f"Last-Modified: {lm}" if lm else "No modification date detected.")
    return SignalResult(
        "Last modified date", "freshness", has, 4, 4 if has else 0,
        detail,
        None if has else "Expose a dateModified in JSON-LD or via Last-Modified header. AI prioritizes fresh content.",
    )


def _check_dated_claims(soup: BeautifulSoup) -> SignalResult:
    text = soup.get_text(separator=" ", strip=True)
    # Look for "in 2024", "in 2025", "in 2026", "as of {month} 2026", etc.
    has_date_phrases = bool(
        re.search(r"\b(in|as of|updated|since)\s+(202[3-6]|january|february|march|april|may|june|july|august|september|october|november|december)\b", text, re.I)
    )
    return SignalResult(
        "Dated claims in body", "freshness", has_date_phrases, 3, 3 if has_date_phrases else 0,
        "Body contains explicit dated phrases." if has_date_phrases else "No dated phrases in body text.",
        None if has_date_phrases else "Use 'As of {month} 2026' on every claim. Undated content reads stale to AI models.",
    )


def _check_year_in_title(soup: BeautifulSoup) -> SignalResult:
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""
    has_year = bool(re.search(r"\b(202[4-6])\b", title))
    return SignalResult(
        "Year in title", "freshness", has_year, 3, 3 if has_year else 0,
        f"Title contains a year." if has_year else "No year in H1/title.",
        None if has_year else "If the content is time-sensitive, include the year in the title (e.g. '... in 2026').",
    )


# ============ ORCHESTRATOR ============

def score_url(url: str) -> ScoreResult:
    url = _norm_url(url)
    result = ScoreResult(
        url=url,
        score=0,
        grade="F",
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        page_title=None,
    )

    response, err = _fetch(url)
    if response is None:
        result.notes.append(err or "Fetch failed for unknown reason.")
        result.grade = "—"
        return result

    soup = BeautifulSoup(response.text, "lxml")
    parsed_url = urlparse(str(response.url))
    page_host = parsed_url.netloc.lower()

    title_tag = soup.find("title")
    result.page_title = title_tag.get_text(strip=True) if title_tag else None

    jsonld = _extract_jsonld(soup)
    schema_set = _schema_types(jsonld)
    wc = _word_count(soup)

    # Detect likely JS-rendered SPA: lots of script tags + very few semantic content tags.
    # If we see ≥3 scripts but fewer than 3 <p> tags AND fewer than 50 words of body text,
    # this page is almost certainly client-side rendered.
    script_count = len(soup.find_all("script"))
    semantic_p = len(soup.find_all("p"))
    if script_count >= 3 and semantic_p < 3 and wc < 200:
        result.notes.append(
            "⚠ This page appears to be JavaScript-rendered. AI crawlers see what we see — not what you see in your browser. "
            "The score reflects what's actually in the raw HTML response."
        )

    signals: list[SignalResult] = [
        # Crawlability bucket (15 pts max)
        _check_https(parsed_url),
        _check_canonical(soup, url),
        _check_viewport(soup),
        _check_open_graph(soup),
        _check_llms_txt(parsed_url),
        _check_robots_ai(parsed_url),

        # Schema & structure (30 pts max)
        _check_article_schema(schema_set),
        _check_faq_schema(schema_set),
        _check_howto_schema(schema_set),
        _check_breadcrumb_schema(schema_set),
        _check_heading_structure(soup),
        _check_definition_lists(soup),
        _check_tables(soup),
        _check_question_h2s(soup),

        # Content / format (25 pts max)
        _check_word_count(wc),
        _check_first_paragraph_answer(soup),
        _check_tldr(soup),
        _check_bold_answer(soup),
        _check_lists(soup),

        # Authority (20 pts max)
        _check_external_authority_links(soup, page_host),
        _check_internal_links(soup, page_host),
        _check_author_byline(soup, jsonld),
        _check_external_link_density(soup, page_host),
        _check_reviews_or_quotes(soup),

        # Freshness (10 pts max)
        _check_last_modified(response, jsonld),
        _check_dated_claims(soup),
        _check_year_in_title(soup),
    ]

    # Aggregate per bucket
    bucket_raw: dict[str, list[SignalResult]] = {b: [] for b in WEIGHTS}
    for s in signals:
        bucket_raw[s.bucket].append(s)

    bucket_summary: dict[str, dict[str, float]] = {}
    total_points = 0.0
    for bucket, weight_max in WEIGHTS.items():
        bs = bucket_raw[bucket]
        bucket_weight = sum(s.weight for s in bs) or 1
        bucket_earned = sum(s.points for s in bs)
        # Normalize to the bucket weight cap
        scaled = (bucket_earned / bucket_weight) * weight_max if bucket_weight else 0
        bucket_summary[bucket] = {
            "earned": round(scaled, 1),
            "max": float(weight_max),
            "percent": round(100 * scaled / weight_max, 1) if weight_max else 0,
        }
        total_points += scaled

    score_int = max(0, min(100, round(total_points)))
    result.score = score_int
    result.grade = _grade(score_int)
    result.bucket_scores = bucket_summary
    result.signals = signals
    result.fixes = [s.fix for s in signals if s.fix][:10]  # top 10 actionable fixes
    return result


# Convenience for serverless / CLI
def score_url_json(url: str) -> str:
    return json.dumps(score_url(url).to_dict(), indent=2)
