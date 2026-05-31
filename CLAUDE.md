# deep-devops

Open-source coding agent built on `langchain-ai/deepagents`. **Three-tier model routing:**

1. **Tier 1 — DeepSeek native API** (China-hosted, cheapest). For public, non-company queries with no PII. Gated by both a PII/secret scanner AND a publicness classifier (whitelist semantics).
2. **Tier 2 — DeepSeek V4 via Nebius** (Amsterdam, EU/GDPR). Default for internal-but-non-confidential traffic.
3. **Tier 3 — Claude Haiku 4.5 / Sonnet 4.6** (Anthropic direct). Confidential data and escalation when a lower tier fails.

Repeated failures are crystallised as deterministic Python tools in `deep_devops/skills/` (no fine-tuning).

## Status

**Design v0.2 complete, implementation not started.** Architecture, security model, evaluation, and observability are designed with citations to *AI Engineering* (Chip Huyen) as ground truth. See `docs/design.md` (current is v0.2 — three-tier) and `docs/chapters_notes.md`.

## Ground truth

The book `ai_engineering/` (Chip Huyen, *AI Engineering*) is the **authoritative reference** for this project's design. Every non-trivial decision in `docs/design.md` cites a page or section. When proposing changes — especially to security, evaluation, or observability — keep this anchoring: cite the book or argue explicitly why we are deviating.

Chapters that matter most:
- **Cap 3** Evaluation Methodology — failure detection without LLM-judge
- **Cap 4** Evaluate AI Systems — hard/soft attributes, eval pipeline, Table 4-3 routing
- **Cap 9** Inference Optimization — TTFT/TPOT/cost metrics, prompt caching
- **Cap 10** Architecture & User Feedback — guardrails, router, gateway, feedback loops, skill factory

## Tech stack

- **CLI/TUI**: upstream `deepagents` (`curl -LsSf https://langch.in/gh-da-cli | bash`). Do NOT rebuild the TUI.
- **Project manager**: `uv` (see `pyproject.toml`).
- **Python**: ≥3.11.
- **LLM providers**:
  - Tier 1: DeepSeek native API (https://api.deepseek.com).
  - Tier 2: Nebius Token Factory (Amsterdam, EU). Scaleway is the M2 swap candidate if it adds V4.
  - Tier 3: Anthropic direct (Haiku 4.5 / Sonnet 4.6).
- **Gateway**: decision in M1 — candidates Portkey, MLflow AI Gateway, or thin custom. Must support per-tier upstream selection.

## Hard rules

1. **Internal or confidential data never leaves the EU unless it goes to Anthropic.** Tier 1 (DeepSeek native, China) is reachable only when BOTH the rule-based PII/secret scanner AND the publicness classifier clear the query. The classifier is a **whitelist** — a query must affirmatively look public, not just fail to look internal. See `docs/design.md §3.5, §4.2`.
2. **Kill-switch always available.** `DEEP_DEVOPS_DISABLE_PUBLIC_TIER=1` collapses tier 1 into tier 2. No code change.
3. **No LLM-as-judge in the hot path.** Failure signals are deterministic: test runner, JSON schema, logprobs, regex / FITS-cluster patterns (Cap 3 p.144, Cap 10 Table 10-1).
4. **No fine-tuning.** Skills are deterministic Python tools in `deep_devops/skills/` (Cap 3 p.146 + Cap 10 p.478).
5. **No orchestration layer above deepagents** (Cap 10 p.473 — "start without one first").
6. **No semantic cache.** Exact cache only — Cap 9 p.462 calls semantic cache "dubious".
7. **Pin model version strings.** Re-run the eval set when a provider rolls a silent update (Cap 10 p.472, Voiceflow incident).
8. **Tier-1 leak rate hard target: 0.** Any post-hoc audit catching internal data on tier 1 → kill-switch ON until root-caused.

## File map (intended)

```
deep_devops/
  router/      rules-based routing: PII scan, publicness classifier, escalation
  gateway/     provider abstraction (DeepSeek native + Nebius + Anthropic, caching)
  eval/        failure signals + offline harness + leak-detection eval set
  skills/      deterministic Python tools (auto-grown by skill factory)
docs/          one .md per significant session or feature decision
evals/         eval set + per-run outputs
ai_engineering/  book PDFs (reference)
```

## Documentation convention

- One `docs/<topic>.md` per significant session or feature decision.
- Use the template at `docs/_template.md` (frontmatter: `date`, `status`, `topic`, `refs`).
- Cite book pages with `Cap N p.PPP` when the decision derives from it.
- `docs/design.md` is the living architecture doc; new session notes link to it, not duplicate it.
- Session logs use the filename `docs/session-YYYY-MM-DD.md` (or `-topic` suffix when multiple sessions land same day).

## Common commands

```bash
# Primera instalación en una máquina nueva
bash setup.sh                    # instala uv, deepagents CLI, deep_devops y el comando `deep`
deep                             # lanza el agente (tras setup.sh)

# Desarrollo
uv sync                          # instala/actualiza deps
uv run pytest                    # suite de tests
uv run python -m evals.qa_fase1.run  # QA suite

# Cuando estén implementados
uv run dd                        # launch deepagents TUI with our router/skills
uv run eval                      # run eval harness over evals/tasks.jsonl
uv run skill-factory --dry-run   # offline batch: cluster failures, propose skills
```

## Workflow rules (Claude Code behaviour)

- **Never commit or push without being explicitly asked.** The user always tests before committing.

## Don'ts

- Don't wrap deepagents in LangChain/LlamaIndex orchestration.
- Don't introduce semantic cache.
- Don't write skills speculatively — skills are born from observed failure patterns.
- Don't use BLEU or any lexical similarity as a quality signal (Cap 3 p.131).
- Don't trust public benchmark scores — use the private hold-out (Cap 4 p.197-199).
- Don't escalate more than one tier per turn; one-way escalation per request.
- Don't make the publicness classifier a blacklist. Whitelist semantics only.
