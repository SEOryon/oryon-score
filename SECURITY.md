# Security Policy

## Reporting a Vulnerability

Email `security@seoryon.com` with a description of the issue, reproduction steps, and your suggested fix if you have one.

Do **not** open a public GitHub issue for security reports.

You'll get an acknowledgment within 72 hours and a target patch date within 7 days.

## Scope

In scope:
- Remote code execution via the CLI or serverless endpoint
- SSRF via the URL fetch path
- XSS in the web UI's result rendering
- API key leakage (we don't use them, but if you find any logged)

Out of scope:
- DOS via expensive URL fetches (the tool is rate-limited by Vercel)
- Outdated dependencies without a known CVE
