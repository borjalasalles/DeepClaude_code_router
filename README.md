# deep-devops

Open-source coding agent built on [`langchain-ai/deepagents`](https://github.com/langchain-ai/deepagents). **Three-tier routing:**

1. **DeepSeek native API** (cheapest, China-hosted) — for public, non-company queries with no PII. Gated by a PII scanner + a publicness classifier (whitelist semantics) and an env kill-switch.
2. **DeepSeek V4 via Nebius** (Amsterdam, EU/GDPR) — default for internal traffic.
3. **Claude Haiku 4.5 / Sonnet 4.6** (Anthropic direct) — confidential data and escalation when a lower tier fails.

## Status

**Design v0.2 complete, implementation not started.** See [`docs/design.md`](docs/design.md) for the full architecture, security model, evaluation system, and observability — all anchored to *AI Engineering* by Chip Huyen.

## Why

- **Cheaper than Claude Code at scale.** The three-tier split routes public traffic to the cheapest available source, internal traffic to an EU specialist (~3–5× cheaper than AWS Bedrock or Azure AI Foundry for the same DeepSeek class), and only the confidential slice to Anthropic. Estimated workload cost is ~$2.50/month for 5M+1M tokens vs ~$8 always-Haiku and ~$12 always-Bedrock.
- **GDPR / EU residency for everything that matters.** Internal or confidential data never leaves the EU unless it goes to Anthropic. Tier 1 is gated by a whitelist classifier and an env kill-switch.
- **Skills, not fine-tunes.** Repeated failures are crystallised into deterministic Python tools, versioned in git.

## Tech stack

- `deepagents` upstream CLI (TUI + agent loop)
- `uv` for project management
- Python ≥3.11
- Nebius Token Factory (primary inference, EU)
- Anthropic API (escalation)

## Quickstart (M0 — not yet implemented)

```bash
# install deepagents CLI (upstream)
curl -LsSf https://langch.in/gh-da-cli | bash

# clone + install
git clone <this repo>
cd deep-devops
cp .env.example .env   # fill NEBIUS_API_KEY and ANTHROPIC_API_KEY
uv sync

# run
uv run dd
```

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — project skill (loaded into Claude Code sessions)
- [`docs/design.md`](docs/design.md) — architecture, decisions, citations
- [`docs/chapters_notes.md`](docs/chapters_notes.md) — condensed *AI Engineering* findings
- `docs/<feature>.md` — one note per significant session or feature

## Licence

MIT (to be added at M5).
