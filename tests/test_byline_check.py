"""
Regression tests for the "Named author / byline" check (0.3.1).

The bug being pinned: the old rule lowercased the entire page and matched
`by [a-z]+ [a-z]+`, so any ordinary prose containing "... by <word> <word> ..."
scored a byline. Proven live: roi.seoryon.com — whose body says "conservative
industry range backed by a public poll of 4,000 buyers" and "the default by
business type" — was awarded 5/5 for "Named author / byline" with no author
named anywhere on the page.

The check now credits an author only from an honest source:
  * JSON-LD `author`,
  * a <meta name="author"> (or article:author) tag, or
  * a byline *anchored to author context* — author/byline-marked markup, or a
    "By <Capitalized Name>" line at the head of a short block (a dateline/header).
Arbitrary body prose never counts, and every ambiguous case fails closed.

Weight is unchanged: the signal is worth 5 points, pass or fail.

The two mandated regressions:
  * roi-shaped body prose must NOT pass,
  * a real "By Jane Smith" byline must pass.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

from oryon_score.score import (
    _check_author_byline,
    _extract_jsonld,
    _named_author_source,
)


def _source(html: str):
    """Which honest source (if any) names an author for this HTML."""
    soup = BeautifulSoup(html, "html.parser")
    return _named_author_source(soup, _extract_jsonld(soup))


def _signal(html: str):
    soup = BeautifulSoup(html, "html.parser")
    return _check_author_byline(soup, _extract_jsonld(soup))


def _wrap(body: str) -> str:
    return f"<!doctype html><html><head><title>t</title></head><body>{body}</body></html>"


# The prose that fooled the old regex, taken from roi.seoryon.com's own copy.
ROI_BODY = _wrap(
    "<main><article>"
    "<h1>ROI Calculator</h1>"
    "<p>Take the conservative industry range backed by a public poll of 4,000 "
    "buyers. If you have real conversion data, use it. If not, the default by "
    "business type (1–3%) is a safe starting point for the estimate.</p>"
    "<p>Everything here is powered by simple arithmetic — no tracking, no "
    "accounts, results driven by the numbers you enter.</p>"
    "</article></main>"
)


# ---------------------------------------------------------------------------
# Mandated regressions
# ---------------------------------------------------------------------------
def test_roi_shaped_prose_does_not_pass():
    """The exact class of body text that produced the live false positive."""
    assert _source(ROI_BODY) is None
    sig = _signal(ROI_BODY)
    assert sig.passed is False
    assert sig.points == 0


def test_real_by_jane_smith_byline_passes():
    """A real 'By Jane Smith' byline must still be credited."""
    html = _wrap('<article><p class="byline">By Jane Smith</p><p>Body copy here.</p></article>')
    assert _source(html) is not None
    sig = _signal(html)
    assert sig.passed is True
    assert sig.points == 5


# ---------------------------------------------------------------------------
# Honest sources that SHOULD pass
# ---------------------------------------------------------------------------
def test_jsonld_author_passes():
    html = _wrap(
        '<script type="application/ld+json">'
        '{"@type":"Article","author":{"@type":"Person","name":"Jane Smith"}}'
        "</script><p>Body.</p>"
    )
    assert _source(html) == "jsonld"


def test_jsonld_author_in_graph_passes():
    html = _wrap(
        '<script type="application/ld+json">'
        '{"@graph":[{"@type":"WebPage"},{"@type":"Article","author":"Jane Smith"}]}'
        "</script><p>Body.</p>"
    )
    assert _source(html) == "jsonld"


def test_meta_author_passes():
    html = _wrap('<p>Body.</p>')
    html = html.replace("<title>t</title>", '<title>t</title><meta name="author" content="Jane Smith">')
    assert _source(html) == "meta"


def test_meta_article_author_passes():
    html = _wrap('<p>Body.</p>').replace(
        "<title>t</title>",
        '<title>t</title><meta property="article:author" content="https://example.com/jane">',
    )
    assert _source(html) == "meta"


def test_bare_by_line_at_head_of_block_passes():
    """A dateline-style 'By <Name>' line with no author class still counts."""
    html = _wrap("<article><p>By Jane Smith</p><p>The rest of the article body.</p></article>")
    assert _source(html) == "byline"


def test_by_line_with_dateline_passes():
    html = _wrap("<article><header><p>By Jane Smith · July 17, 2026</p></header><p>Body.</p></article>")
    assert _source(html) == "byline"


def test_written_by_passes():
    html = _wrap('<div class="post-meta"><span>Written by John Doe</span></div>')
    assert _source(html) is not None


def test_middle_initials_pass():
    html = _wrap("<article><p>By A. K. Rowling</p><p>Body.</p></article>")
    assert _source(html) == "byline"


def test_hyphenated_and_particle_names_pass():
    for name in ("Anne-Marie Slaughter", "Jane de Sousa", "Chen Wei", "Maria O'Brien"):
        html = _wrap(f'<p class="byline">By {name}</p>')
        assert _source(html) is not None, name


def test_author_class_bare_name_passes():
    html = _wrap('<span class="author-name">Maria Rodriguez</span>')
    assert _source(html) == "markup"


def test_rel_author_link_passes():
    html = _wrap('<a rel="author" href="/authors/chen">Chen Wei</a>')
    assert _source(html) == "markup"


def test_itemprop_author_passes():
    html = _wrap('<span itemprop="author">Priya Nair</span>')
    assert _source(html) == "markup"


# ---------------------------------------------------------------------------
# Prose / ambiguity that MUST fail closed
# ---------------------------------------------------------------------------
def test_prose_by_two_lowercase_words_does_not_pass():
    """The literal shape the old regex matched: 'by <word> <word>' in prose."""
    html = _wrap("<article><p>The estimate is backed by a public poll of 4,000 buyers.</p></article>")
    assert _source(html) is None


def test_prose_name_drop_does_not_pass():
    """A capitalized name mentioned mid-sentence is not a byline."""
    html = _wrap(
        "<article><p>This framework was popularized by Rand Fishkin in 2015 and "
        "has been refined by practitioners ever since.</p></article>"
    )
    assert _source(html) is None


def test_possessive_prose_does_not_pass():
    html = _wrap(
        "<article><p>By Jane Smith's estimate, revenue tripled last year across "
        "every single region worldwide again.</p></article>"
    )
    assert _source(html) is None


def test_possessive_with_apostrophe_name_does_not_pass():
    html = _wrap(
        "<article><p>By Jane O'Brien's report, the numbers climbed sharply over "
        "the last four quarters here.</p></article>"
    )
    assert _source(html) is None


def test_by_the_time_prose_does_not_pass():
    html = _wrap("<p>By the time you read this, the market will have shifted again for buyers.</p>")
    assert _source(html) is None


def test_title_case_heading_does_not_pass():
    """A Title-Case heading that starts with 'By' is not a byline."""
    for heading in ("<h1>By Popular Demand We Are Back</h1>", "<h2>By December Analysts Expect Cuts</h2>"):
        assert _source(_wrap(heading)) is None, heading


def test_authority_class_is_not_author():
    """'authority' contains 'author' but is not an author element."""
    html = _wrap('<div class="authority-links">Backed By Public Data Sources</div>')
    assert _source(html) is None


def test_ui_bigram_in_author_markup_does_not_pass():
    """A rel=author link reading 'Read More' names no one — fail closed."""
    assert _source(_wrap('<a rel="author">Read More</a>')) is None
    assert _source(_wrap('<div class="author">View All Posts</div>')) is None


def test_empty_byline_element_does_not_pass():
    assert _source(_wrap('<span class="byline"></span>')) is None


# ---------------------------------------------------------------------------
# Weight and honesty of the SignalResult
# ---------------------------------------------------------------------------
def test_weight_unchanged_pass_and_fail():
    passing = _signal(_wrap('<p class="byline">By Jane Smith</p>'))
    failing = _signal(ROI_BODY)
    assert passing.weight == 5 and passing.points == 5 and passing.passed is True
    assert failing.weight == 5 and failing.points == 0 and failing.passed is False
    assert passing.name == failing.name == "Named author / byline"
    assert passing.bucket == failing.bucket == "authority"


def test_fail_detail_is_honest():
    """The failed detail must state no author was found, not claim one exists."""
    sig = _signal(ROI_BODY)
    detail = sig.detail.lower()
    assert "no named author" in detail
    assert "author named" not in detail  # never claims an author on a miss
    assert sig.fix is not None


def test_pass_detail_names_the_source():
    assert "byline" in _signal(_wrap("<article><p>By Jane Smith</p><p>Body.</p></article>")).detail.lower()
    meta_html = _wrap("<p>b</p>").replace(
        "<title>t</title>", '<title>t</title><meta name="author" content="Jane Smith">'
    )
    assert "meta" in _signal(meta_html).detail.lower()
