# Contributing

Bug reports, feature ideas, and PRs welcome. Keep this tool fast, free, and honest.

## Ground rules

- **No vendor lock-in.** Anything that needs a paid API key gets gated as optional, not required.
- **No telemetry.** The CLI and the web tool don't phone home. Don't add analytics.
- **One signal = one specific fix.** Vague advice is worse than no advice.
- **Cite the source.** Every new scoring signal needs a link to a published study, Google guidance, or a reproducible test.

## Dev setup

```bash
git clone https://github.com/SEOryon/oryon-score
cd oryon-score
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the CLI against the test fixtures
oryon-score https://example.com

# Run the web tool locally
vercel dev
```

## Adding a signal

1. Add the check function in `src/score.py` following the existing pattern (returns a `SignalResult`).
2. Add it to the `signals` list in `score_url()`.
3. Update the bucket weight if the total in your bucket changes.
4. Add a 1-line summary to the README's "What it actually checks" section.
5. Cite the underlying study or Google guidance in your PR description.

## Style

- Python 3.10+ syntax
- Type hints everywhere
- No dependencies beyond `httpx`, `beautifulsoup4`, `lxml`
- No silent failures — surface errors in `result.notes`

## Process

PRs go through one review. Approved PRs get squash-merged with a clear commit message.

Security issues: do not file as a public Issue. Email `security@seoryon.com`.
