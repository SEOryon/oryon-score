# Launch Playbook — Oryon AI Search Readiness Score

The repo is the marketing. Here's the 7-day plan to take it from 0 → 500+ stars and convert traffic into Oryon trials.

## Pre-launch checklist (day 0)

- [ ] Create GitHub org: `github.com/SEOryon` (Settings → New organization → Free tier)
- [ ] Push the repo: `SEOryon/oryon-score`
- [ ] Reserve `score.seoryon.com` subdomain in your DNS
- [ ] Deploy to Vercel: `vercel --prod` → custom domain `score.seoryon.com`
- [ ] Publish package to PyPI: `pip install build twine && python -m build && twine upload dist/*`
- [ ] Verify the live site scores a real URL end-to-end
- [ ] Take 3 screenshots (hero + result card + dark CLI) for the launch posts
- [ ] Set up a Linktree or Beacons link in @SEOryon IG bio that points to seoryon.com + score.seoryon.com

## Day 1 — Soft launch (Monday morning)

**Goal:** validate the tool with friendlies before going public.

- Post on your personal Twitter / X (not the brand account): "I shipped a free tool that scores any URL for AI search readiness. Built it because the existing tools start at €295/mo. [score.seoryon.com] Would love your worst-scoring URL ☕"
- DM 10 SEO friends, ask them to break it. Fix anything they find.
- Submit to **r/SEO** (text post, not link): "I built a free tool that scores any page for AI search readiness — here's what it checks." Be honest it's tied to Oryon at the bottom of the post.

## Day 2 — Show HN (Tuesday, 8 AM PT)

**Goal:** front page of Hacker News.

Title formula (tested): `Show HN: Free AI search readiness score for any URL (open source)`

Body template:
```
Hi HN — I built this because every AI citation tracker I evaluated starts at €295/mo. For a tool that mostly answers "is my page set up to get cited at all," that felt steep.

It's a 27-signal scoring engine across 5 buckets: schema, content format, authority, crawlability, freshness. No LLM calls — pure HTML parsing + signal heuristics inspired by Google's 2026 AI search guidance.

Live tool: https://score.seoryon.com
Source: https://github.com/SEOryon/oryon-score (MIT)
CLI: pip install oryon-score

Built by Oryon (https://seoryon.com), the SEO engine I'm working on. The free tool scores one page at a time. The paid product scores every URL on your site continuously and writes the fixes. Wanted to be upfront about that.

Happy to break this in real time if you paste your worst-scoring page below.
```

- Stay in the thread for 4 hours, reply to every comment in <30 min
- Don't auto-promote — let it stand on its merits

## Day 3 — X thread + LinkedIn

**X thread (your handle + cross-post @SEOryon):**

```
1/ I shipped a free tool that scores any URL for AI search readiness.

The existing tools start at €295/mo. For "is my page set up to get cited at all?", that's absurd.

→ score.seoryon.com (Free, no signup)

2/ It checks 27 signals across 5 buckets:
   • Schema markup (FAQPage, Article, HowTo)
   • Content format (TL;DR, lead-with-answer, lists)
   • Authority (.gov/.edu links, author byline)
   • Crawlability (llms.txt, robots, OG tags)
   • Freshness (dateModified, dated claims)

3/ Highest-correlation signal? FAQPage JSON-LD.

If you have a real FAQ section but no FAQPage schema, you're leaving the easiest extraction win on the table.

4/ Lowest-correlation? Page speed.

Counter-intuitive, but AI extractors don't rank by speed. They rank by extractability. Worry about TTFB after you've nailed the structure.

5/ The tool is MIT open source. Fork it. Deploy your own. Run it in CI.

Repo: github.com/SEOryon/oryon-score
CLI: pip install oryon-score

6/ Built by @SEOryon. The free tool scores ONE page. Oryon scores every URL on your site continuously, tracks citations across ChatGPT/Perplexity/Gemini, and writes the fixes.

3-day free trial → seoryon.com
```

**LinkedIn variant:** same content, more formal tone, longer paragraphs. Post from your personal page.

## Day 4 — Awesome-* PRs

Submit pull requests to add your repo to:
- `github.com/topics/seo`
- `github.com/topics/llm`
- `github.com/topics/ai-search`
- `awesome-seo` (curated list)
- `awesome-llm` (curated list)
- `awesome-ai-search` (if it exists)

Format: one-line entry per list, link to repo, brief description.

## Day 5 — Instagram + Facebook carousel announcement

Use Template A (Stat Shock) from your locked Claude Design system:

- Slide 1 (Hook): "I built a free AI Search Readiness Score. Here's what it checks."
- Slides 2-4: three of the 27 signals visualized as stats
- Slide 5: "How to use it" (3-step)
- Slide 6 (CTA): "Score your own URL → score.seoryon.com / GitHub link in bio"

Post to @SEOryon + cross-post to FB Page.

## Day 6 — Discord + community drops

- Drop the link in: r/SEO, r/bigseo, the Traffic Think Tank Slack, the SEO subreddit, growth.design discord, indie hackers community
- Format: "I built X to scratch my own itch. It's free + open source. Would love feedback."
- Don't drop in 5 places in one day — pace 2 per day to look organic

## Day 7 — Retro + iteration

By end of week 1 you should have:
- ✅ Show HN front page or top 3 of r/SEO
- ✅ 50–200 GitHub stars
- ✅ 500+ score.seoryon.com sessions
- ✅ 10–30 Oryon trial signups attributed to the tool

If you didn't hit those: the tool needs more signals, the README needs a better hero image, or the upsell needs to be tighter. Iterate.

## Conversion mechanics that matter

These small things drive trial signups from the free tool:

1. **The "want continuous scoring?" footer** at the bottom of every result card. Already in `index.html`.
2. **The `score.seoryon.com/?url=https://...` URL pattern** — share-friendly. People post their score, others click to compare theirs.
3. **The upsell card** at the bottom of the page with the gradient block and the bigcta button.
4. **The CLI's last line:** `→ Try Oryon free for 3 days: seoryon.com`
5. **A "Run on every page of my site"** Discord/Slack pitch in r/SEO once a week.

## Maintenance budget

- Triage Issues: 30 min/week
- Merge PRs: 1 hour/week
- Add a new signal every 2 weeks (drives release notes → tweetable content)
- Quarterly: review the scoring weights against the latest Google guidance

## After it's running

The repo becomes a content engine. Each new signal → an Instagram carousel ("New: we now check for definition lists. Here's why."). Each PR merged → a small social post. Each user who hits 90+ → a testimonial ask. Each user who hits <40 → a free Oryon audit offer.

The tool is the funnel. Treat it that way.
