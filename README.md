# deep-devops

Open-source coding agent built on [`langchain-ai/deepagents`](https://github.com/langchain-ai/deepagents). **Three-tier routing:**

1. **DeepSeek native API** (cheapest, China-hosted) — for public, non-company queries with no PII. Gated by a PII scanner + a publicness classifier (whitelist semantics) and an env kill-switch.
2. **DeepSeek V4 via Nebius** (Amsterdam, EU/GDPR) — default for internal traffic.
3. **Claude Haiku 4.5 / Sonnet 4.6** (Anthropic direct) — confidential data and escalation when a lower tier fails.

## Status

**Design v0.2 complete; M1 in progress.** The deterministic PII/secret scanner is done (`deep_devops/router/pii_scanner.py`, 57/57 tests). Next: the redaction map, the three-tier gateway, and the `RouterChatModel` that wires routing into the deepagents CLI. See [`docs/design.md`](docs/design.md) for the full architecture, security model, evaluation system, and observability — all anchored to *AI Engineering* by Chip Huyen.

The project is mirrored to GitHub at [`borjalasalles/DeepClaude_code_router`](https://github.com/borjalasalles/DeepClaude_code_router). That remote is the canonical off-machine **backup** — commit and push regularly so work survives a machine loss or migration between computers.

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

## Setup

Tested on Ubuntu 24.04. Run these in a normal terminal.

**1. Install `uv`** (skip if already present):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and install project dependencies:**

```bash
git clone https://github.com/borjalasalles/DeepClaude_code_router.git
cd DeepClaude_code_router
uv sync
```

**3. Create your `.env`** — it is git-ignored and never committed:

```bash
cp .env.example .env
```

Fill in `DEEPSEEK_API_KEY` (and `NEBIUS_API_KEY` / `ANTHROPIC_API_KEY` once those tiers are wired). This `.env` is consumed by the deep-devops code — see step 6 for the key the CLI itself reads.

**4. Install the upstream deepagents CLI** (separate from this repo):

```bash
curl -LsSf https://langch.in/gh-da-cli | bash
```

**5. Add `langchain-deepseek` to the CLI's environment** — it is not bundled, and without it the `deepseek:` provider fails silently:

```bash
uv pip install langchain-deepseek --python "$(uv tool dir)/deepagents-cli/bin/python"
```

**6. Configure `~/.deepagents/`** — the CLI reads its API key from `~/.deepagents/.env`, **not** from this repo's `.env`:

```bash
mkdir -p ~/.deepagents
printf '[models]\ndefault = "deepseek:deepseek-chat"\nrecent = "deepseek:deepseek-chat"\n' > ~/.deepagents/config.toml
printf 'DEEPSEEK_API_KEY=sk-your-real-key\n' > ~/.deepagents/.env   # edit with your actual key
```

**7. Verify and launch:**

```bash
uv run pytest                               # expect 57/57
deepagents --model deepseek:deepseek-chat
```

If `deepagents` is not on your `PATH`, use `"$(uv tool dir)/deepagents-cli/bin/deepagents"`.

### Gotchas

- **Use the `deepseek:` provider, not `openai:`** — `openai:deepseek-chat` with a custom `base_url` fails silently inside the deepagents LangGraph runtime.
- **The CLI key lives in `~/.deepagents/.env`** — editing this repo's `.env` does nothing for the TUI. An `authentication error` on launch almost always means that file still holds the placeholder, or the variable name is misspelled (it is `DEEPSEEK_API_KEY`).
- **Never switch models from the TUI model switcher** — it overwrites `config.toml [models] recent` and breaks saved threads with `an internal error occurred`. Always launch with an explicit `--model` flag.

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — project skill (loaded into Claude Code sessions)
- [`docs/design.md`](docs/design.md) — architecture, decisions, citations
- [`docs/chapters_notes.md`](docs/chapters_notes.md) — condensed *AI Engineering* findings
- `docs/<feature>.md` — one note per significant session or feature

## Licence

[GNU AGPL-3.0-only](LICENSE). deep-devops only *depends on* `deepagents` (MIT) — it does not bundle or redistribute it — so this project is free to adopt a copyleft licence. The AGPL's network clause means anyone who runs a modified version as a service must publish their changes.
