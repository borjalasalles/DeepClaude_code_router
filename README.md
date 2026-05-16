# deep-devops

Open-source coding agent built on [`langchain-ai/deepagents`](https://github.com/langchain-ai/deepagents). **Three-tier routing:**

1. **DeepSeek native API** (cheapest, China-hosted) — for public, non-company queries with no PII. Gated by a PII scanner + a publicness classifier (whitelist semantics) and an env kill-switch.
2. **DeepSeek V4 via Nebius** (Amsterdam, EU/GDPR) — default for internal traffic.
3. **Claude Haiku 4.5 / Sonnet 4.6** (Anthropic direct) — confidential data and escalation when a lower tier fails.

## Status

**M2.1 complete + post-M2.1 hardening (2026-05-16).** The router is live: `deepagents --model deep-devops:router` works end-to-end. PII in your messages is redacted before reaching DeepSeek, and every call is traced to `~/.deep_devops/traces.jsonl`. Tiers 2 (Nebius) and 3 (Anthropic) are designed and logged but **not yet wired** — all traffic currently routes to tier 1 (DeepSeek, China-hosted) after redaction. See [`docs/design.md`](docs/design.md) for the architecture and [`docs/session-2026-05-16-closeout.md`](docs/session-2026-05-16-closeout.md) for the latest decisions.

On top of M1.5, **M2.1** added: a language-aware NER scanner for personal names (spaCy + wordlist supplement, ES + EN models picked per text via `langdetect`), entity aliasing for organisation names, and an output-side name scan that catches names echoed back by the model. **Post-M2.1 hardening (2026-05-16)** moved spaCy and the two language models to *core* dependencies, made the NER layer mandatory (`scan()` raises `NerUnavailableError` and fails closed if the layer cannot load at all — silent fail-open closed), and is documented honestly: see "[What `/model` does — and why you should not use it](#what-model-does--and-why-you-should-not-use-it)" below.

**Strategic note.** Until Tier 2 (Nebius, EU/GDPR) and Tier 3 (Anthropic) are approved and wired, the explicit decision is **not** to over-complexify the DeepSeek-China call. Investment is concentrated in **non-blocking security**: scan, redact, continue. Wordlists and NER logic are iterated from *observed* failures (real edge-cases that leak), not speculatively.

The project is mirrored to GitHub at [`borjalasalles/DeepClaude_code_router`](https://github.com/borjalasalles/DeepClaude_code_router). That remote is the canonical off-machine **backup** — commit and push regularly so work survives a machine loss or migration between computers.

## PII redaction — confidentiality guarantee

**Every message you type is scanned before it reaches any LLM.** Sensitive values are replaced with typed, numbered placeholders (`{/EMAIL_1/}`, `{/SECRET_KEY_1/}`, …). The model receives the sanitised text and never sees the original values. The session **never blocks** — it always continues, with or without PII detected.

> **Why this matters for Tier 1 (DeepSeek native, China-hosted):** DeepSeek's native API is the cheapest tier, but it is hosted outside the EU. The scanner is the last line of defence before your message crosses that boundary. If the scanner misses something, that value leaves your machine unredacted. That is why false negatives are treated as worse than false positives, and why the [known limitations](#known-limitations--what-the-scanner-cannot-catch) section below is not hidden.

### What the scanner catches

| Category | Examples | Placeholder |
|---|---|---|
| **Cloud / API credentials** | | |
| AWS access keys | `AKIAIOSFODNN7EXAMPLE` | `{/AWS_ACCESS_KEY_1/}` |
| Generic secret keys | `sk-ant-api03-...`, `sk-proj-...` (OpenAI, Anthropic, etc.) | `{/SECRET_KEY_1/}` |
| GitHub tokens | `ghp_...`, `ghs_...`, `ghr_...`, `ghu_...`, `github_pat_...` | `{/GITHUB_TOKEN_1/}` |
| Stripe keys | `sk_live_...`, `sk_test_...` | `{/STRIPE_KEY_1/}` |
| Slack tokens | `xoxb-...`, `xoxp-...`, `xapp-...`, `xoxr-...` | `{/SLACK_TOKEN_1/}` |
| Telegram bot tokens | `123456789:AAFabc...` | `{/TELEGRAM_TOKEN_1/}` |
| GCP API keys | `AIzaSyD...` (Google Cloud) | `{/GCP_API_KEY_1/}` |
| **Auth tokens** | | |
| JWT tokens | `eyJ...` — two or three segments, incl. `alg:none` | `{/JWT_TOKEN_1/}` |
| Bearer tokens | `Authorization: Bearer abc...` | `{/BEARER_TOKEN_1/}` |
| PEM / private keys | `-----BEGIN RSA PRIVATE KEY-----` | `{/PEM_KEY_1/}` |
| **Infra / DB** | | |
| Database URLs with credentials | `postgres://user:pass@host`, `mysql://...`, `redis://...` | `{/DATABASE_URL_1/}` |
| SWIFT / BIC codes | `CAIXESBBXXX` (only when banking keywords nearby) | `{/SWIFT_CODE_1/}` |
| Credit / debit cards | `4111 1111 1111 1111`, `4111-1111-1111-1111`, `378282246310005` — Luhn-validated | `{/CREDIT_CARD_1/}` |
| International IBANs (ISO 13616) | synthetic examples: `ES00 0000 0000 0000 0000 0000`, `GB00 ZZZZ 0000 0000 0000 00`, `DE00 0000 0000 0000 0000 00`, `CH00 0000 0000 0000 0000 0`, `BR00 0000 0000 0000 0000 0000 000Z 0`, … — ~85 countries (EU/EEA, UK, Switzerland, MENA, Latin America). Country-aware regex anchors to each country's exact length; **no mod-97 checksum gate** so typos and fictional IBANs are still redacted (denial-by-default after a real leak). | `{/IBAN_CODE_1/}` |
| Mexican CLABE | 18-digit synthetic example `000000000000000000` in Mexican-banking context (`clabe`, `banamex`, `spei`, `méxico`, …) | `{/CLABE_1/}` |
| US ABA routing | 9-digit synthetic example `000000000` in US-banking context (`aba`, `routing`, `fedwire`, `ach`, `chase`, …) | `{/ABA_ROUTING_1/}` |
| US bank account | 10-17 digit synthetic example `000000000000` in US-banking context (`chase`, `wells fargo`, `checking account`, `wire transfer`, …) | `{/US_BANK_ACCOUNT_1/}` |
| **PII** | | |
| Emails | `user@company.com` (RFC 2606 example domains excluded) | `{/EMAIL_1/}` |
| Phone numbers | `+34 612 345 678`, `612 345 678`, `415-555-1234` | `{/PHONE_1/}` |
| Password / secret fields | `password=X`, `contraseña: X`, `access_key: X`, `secret=X`, `api_key: X`, `"access_key": "X"` (JSON). JSON-Schema definitions like `"password": {"type": "string"}` are excluded. | `{/PASSWORD_FIELD_1/}` |
| Spanish DNI (NIF) | `12345678Z` — mod-23 validated | `{/ES_NIF_1/}` |
| Spanish NIE | `X1234567L` — mod-23 validated | `{/ES_NIE_1/}` |
| Spanish CIF | `B76543214`, `A28015865` — mod-10 validated, optional `-` separator | `{/ES_CIF_1/}` |
| **Network / infra markers** | | |
| Private IPs | `192.168.x.x`, `10.x.x.x`, `172.16–31.x.x` | `{/PRIVATE_IP_1/}` |
| Internal hostnames | `db.internal`, `server.corp`, `host.lan` | `{/INTERNAL_HOST_1/}` |
| Secret file paths | `.env`, `/secrets/`, `credentials.json`, `*.pem`, `*.key` | `{/SECRET_PATH_1/}` |

Checksum validators (Luhn for cards, mod-23 for NIF/NIE, mod-10 for CIF) keep precision high on identity instruments. For account-style numbers (IBAN, CLABE, US accounts) the threat model is **denial-by-default**: a checksum-invalid IBAN is almost always a typo of a real one and is redacted anyway. CLABE, ABA and US account numbers require nearby banking keywords (`chase`, `banamex`, `routing`, `wire transfer`, …) to fire, which trades a small recall hit for much lower false-positive rate on long numerals.

Scanner errors fail closed: if `scan()` raises, the call to DeepSeek is aborted and a trace with `scan_error: true` is written. The unscanned text never crosses the network.

### Example

Input:
```
hola soy fulanito, me ayudas a acceder a SAP
mi usuario es fulanito@empresa.com y mi contraseña=Abc123!
```

What DeepSeek sees:
```
hola soy fulanito, me ayudas a acceder a SAP
mi usuario es {/EMAIL_1/} y mi {/PASSWORD_FIELD_1/}
```

JSON config example — input:
```json
{ "access_key": "SecretPassword2026#", "fiscal_id": "12345678Z" }
```

What DeepSeek sees:
```json
{ {/PASSWORD_FIELD_1/}, "fiscal_id": {/ES_NIF_1/} }
```

### Known limitations — what the scanner cannot catch

The scanner is **mostly deterministic (regex + checksum)** with a contextual NER layer (M2.1) for personal names. These categories are **not protected** today:

| Gap | Example | Why undetectable | Status |
|---|---|---|---|
| Proper names in text | `"mi nombre es Juan García"` | Requires NER — no regex can distinguish names from other words | **M2.1 done** — spaCy `es_core_news_sm` + `en_core_web_sm`, language picked per text |
| Names known only as nicknames | `"me conocen como micky"` | Nicknames live outside any reliable wordlist; spaCy alone doesn't tag them in casual context | Iterated from observed leaks — not speculatively |
| Sensitive *context* (locations, org references, business situation) | `"oficina de Madrid"`, `"cliente de Banco Santander"`, `"registros médicos VIP"` | Out of scope by design — the scanner targets PII / financial instruments / credentials, not general business context | Cuando Tier 2/3 estén cableados, confidencial irá a EU/Anthropic; mientras tanto, no enviar contexto sensible al TUI |
| Passwords without a label | `"la clave es Inicial2026!"` | Arbitrary strings are indistinguishable from normal text | M2: entropy scoring |
| Non-standard field names | `"private_info: secret"`, `"x-api-token: abc"` | Scanner knows a fixed list of field names | Add field names to the pattern |
| Short / opaque tokens | `"code: 123AXX"` | Too short and generic to regex safely without massive FPs | Accept the gap |
| Sensitive values inside code blocks | Variable names, inline values in long scripts | NER skips code-fence blocks to avoid FPs on identifiers | **Done** — `_looks_like_code()` skips ```` ``` ```` blocks |

**If you handle data that cannot leave the EU under any circumstances, use the kill-switch:**
```bash
DEEP_DEVOPS_DISABLE_PUBLIC_TIER=1 deepagents --model deep-devops:router
```
This collapses Tier 1 and routes everything to Tier 2 (Nebius, Amsterdam) or Tier 3 (Anthropic). No code change required. *(Today Tier 2/3 are not yet wired — the kill-switch is plumbed end-to-end but until Nebius credentials land, setting it effectively refuses traffic rather than rerouting it.)*

### What `/model` does — and why you should not use it

Everything on this page — PII scanning, redaction, NER, tracing, fail-closed on scanner errors — lives **inside `RouterChatModel`**, a custom LangChain chat-model wired into deepagents via `class_path` in `~/.deepagents/config.toml`. The security is a property of *that object*, not of the system.

deepagents ships a `/model` slash-command (and a `--model` flag) that lets any user pick a different model at runtime. When you do `/model openai:gpt-…`, deepagents **does not create another `RouterChatModel`** — it instantiates an entirely different class (`ChatOpenAI`, `ChatAnthropic`, `ChatDeepSeek`, …) built directly by langchain. Our `_route()` is never in its call path, so **scan, redact, tier classification and trace are 100% bypassed**, silently, with no entry in `~/.deep_devops/traces.jsonl`. Our own code cannot even log it: it is not running.

> **The anti-pattern in one line:** security is currently a property of one *object*, not of the *system*. The architectural fix is to migrate the guardrail to a deepagents `AgentMiddleware` (`wrap_model_call`), which runs on every model invocation regardless of which model `/model` selected. That migration is **identified and planned, not done.** See [`docs/session-2026-05-16-closeout.md`](docs/session-2026-05-16-closeout.md) and [`docs/session-2026-05-16-guardrail-middleware.md`](docs/session-2026-05-16-guardrail-middleware.md).

**Until the middleware lands, the only mitigation is process:**

- **Launch with `--model deep-devops:router`.** Do not run `deepagents` without that flag.
- **Do not use `/model` from the TUI.** If you do, your next message goes directly to whatever provider you picked — very likely outside the EU — unscanned, unredacted, and untraced.
- If you cannot rely on a process control for your team, either (a) wait for the middleware migration, or (b) wrap the launcher in a script that hard-pins `--model deep-devops:router` and strips the `/model` slash-command from the TUI session before exposing it to users.

This is the most important honest caveat on this page. The rest of the document describes what the router protects when it is in the call path. `/model` takes it out of the call path.

### Other honest caveats (observed in real testing)

- **The model can't tell you whether you passed PII.** If you ask the model *"did I just pass you PII?"*, it answers based on what *it* saw — which is the redacted text, full of placeholders. It will say "no". The truth is the scanner caught your PII *before* the model ever saw it; the model is structurally blind to that. Trust the trace (`~/.deep_devops/traces.jsonl`), not the model's self-report.
- **The model sometimes treats redacted placeholders as filepaths.** `{/NOMBRE_COMPUESTO_1/}` looks path-like; we have seen the model try `read_file(NOMBRE_COMPUESTO_1)`. Today this is harmless (file not found, no PII inside the placeholder). System-prompt hardening and a non-path-like delimiter are queued; this remained out of scope until observed (per the project's "iterate from real failures" rule).

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

**7. Install deep-devops into the deepagents CLI environment** (so `class_path` can find it):

```bash
uv pip install -e . --python "$(uv tool dir)/deepagents-cli/bin/python"
```

**8. Add the router provider to `~/.deepagents/config.toml`:**

```toml
[models.providers.deep-devops]
models     = ["router"]
class_path = "deep_devops.router.model:RouterChatModel"
enabled    = true

[models.providers.deep-devops.params]
tier1_model       = "deepseek-chat"
tier1_temperature = 0.0
```

**9. Verify and launch:**

```bash
uv run pytest                               # expect 220/220
uv run python -m evals.qa_fase1.run         # QA-MD suite (M1 baseline; M2.1 added on top)
deepagents --model deep-devops:router       # MUST use this flag — do not use /model from inside the TUI
```

To inspect traces locally:
```bash
uv sync --group notebook                    # one-time, installs pandas/matplotlib/jupyter
uv run jupyter notebook evals/notebooks/traces_dashboard.ipynb
```

If `deepagents` is not on your `PATH`, use `"$(uv tool dir)/deepagents-cli/bin/deepagents"`.

### deepagents memory — AGENTS.md

`~/.deepagents/agent/AGENTS.md` is a **standard deepagents file** — not created by this project. deepagents manages it automatically as persistent memory between sessions: `MemoryMiddleware` injects it into the system prompt on every launch. When you share information in a conversation (e.g. your name), deepagents saves it there and recalls it in future sessions.

### Gotchas

- **Use the `deepseek:` provider, not `openai:`** — `openai:deepseek-chat` with a custom `base_url` fails silently inside the deepagents LangGraph runtime.
- **The CLI key lives in `~/.deepagents/.env`** — editing this repo's `.env` does nothing for the TUI. An `authentication error` on launch almost always means that file still holds the placeholder, or the variable name is misspelled (it is `DEEPSEEK_API_KEY`).
- **Never switch models from the TUI model switcher** — it overwrites `config.toml [models] recent` and breaks saved threads with `an internal error occurred`. Always launch with an explicit `--model` flag.

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — project skill (loaded into Claude Code sessions)
- [`docs/design.md`](docs/design.md) — architecture, decisions, citations
- [`docs/chapters_notes.md`](docs/chapters_notes.md) — condensed *AI Engineering* findings
- [`docs/qa-fase1-report.md`](docs/qa-fase1-report.md) — M1 QA baseline against the MD spec
- [`docs/session-2026-05-16-closeout.md`](docs/session-2026-05-16-closeout.md) — **latest** — non-blocking security, `/model` deferred-by-process, NER language-aware
- [`docs/session-2026-05-16.md`](docs/session-2026-05-16.md) — M2.1: NER scanner + entity aliases + output-side name scan
- [`docs/session-2026-05-15.md`](docs/session-2026-05-15.md) — M1.5: international IBAN + checksum validators
- [`deepseek_privacidad_api_20260515.md`](deepseek_privacidad_api_20260515.md) — DeepSeek privacy / regulatory research, source spec for the scanner QA suite
- `docs/<feature>.md` — one note per significant session or feature decision; drafts superseded by a later doc carry `status: superseded` in their frontmatter

## Licence

[GNU AGPL-3.0-only](LICENSE). deep-devops only *depends on* `deepagents` (MIT) — it does not bundle or redistribute it — so this project is free to adopt a copyleft licence. The AGPL's network clause means anyone who runs a modified version as a service must publish their changes.
