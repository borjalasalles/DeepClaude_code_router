# deep-devops — Design

**Status:** v0.2 design, pre-implementation.
**Date:** 2026-05-13 (v0.2 added three-tier routing).
**Ground truth:** Chip Huyen, *AI Engineering* — chapters 3, 4, 9, 10. All non-trivial decisions cite a page or section. Condensed chapter notes in `chapters_notes.md`.

---

## 1. Vision

A self-hostable, open-source coding agent. Upstream `langchain-ai/deepagents` provides the TUI and agent loop; we add a **three-tier routing layer**:

1. **Tier 1 — DeepSeek native API** (China-hosted, cheapest). For queries about *public, non-company* information with no PII: open-source library docs, generic algorithm/SQL syntax, third-party schema design questions, public technical references. Reachable only when the PII/secret scanner **and** the publicness classifier both clear the query.
2. **Tier 2 — DeepSeek V4 via Nebius** (Amsterdam, EU/GDPR). Default for internal-but-non-confidential traffic — company code, internal schema/metadata discussions, anything where data must stay in the EU.
3. **Tier 3 — Claude Haiku 4.5 / Sonnet 4.6** (Anthropic direct). Confidential data (PII, secrets, customer data) and escalation when a lower tier demonstrably fails.

Failures observed in production feed a **skill factory** that crystallises high-quality outputs as deterministic Python tools, shifting future tasks off the LLM entirely.

Target: workflow cost an order of magnitude below Claude Code without losing quality on hard tasks. The tier-1 split is the most aggressive cost saving but the only failure mode that matters is **misclassification leaking internal data to a non-EU provider** — gated by strict guardrails (§3.5, §4.2) and an env kill-switch.

---

## 2. Architecture

```
+-- deepagents CLI (TUI + agent loop, upstream) -----------------------------+
|   filesystem - todos - sub-agents - tool calling                           |
+-------------------------------+--------------------------------------------+
                                |
            +-------------------v-------------------+
            |  Router (rules)                       |
            |   - input guardrails (PII/secrets)    |  <-- Cap 10 Guardrails
            |   - publicness classifier             |      Fig 10-3 (PII reverse map)
            |   - escalation on validated failure   |      Cap 3 Functional Correctness
            +-+----------------+--------------------+-+
              | tier 1         | tier 2               | tier 3
              | public + clean | internal (EU)        | confidential / escalation
              v                v                      v
       +----------------+ +-------------------+ +----------------------+
       | DeepSeek native| | Nebius             | | Anthropic            |
       | API (CN)       | | DeepSeek V4 Flash  | | Haiku 4.5 / Sonnet   |
       | $0.14 / $0.28  | | (Amsterdam, EU)    | | 4.6                  |
       +-------+--------+ +---------+----------+ +---------+------------+
               |                    |                      |
               +-------------+------+-----+----------------+
                             v
                 +------------------------+
                 | Observability bus      |  <-- Cap 9 Inference Metrics
                 | TTFT/TPOT/cost/judge   |      Cap 10 Monitoring
                 +-----------+------------+
                             v
                 +------------------------+
                 | Skill factory (offline)|  <-- Cap 10 p.478
                 | failure cluster -> PR  |      Cap 3 p.146
                 | Sonnet generates tool  |
                 +------------------------+
```

---

## 3. Cloud provider strategy (three tiers)

### 3.1 Prioritisation framework — per query, not per provider (Cap 4 §Hard vs soft attributes, p.179-180)

Cap 4 distinguishes **hard** attributes (must-pass filter — privacy, licence, on-device) from **soft** (rank-by-fit). v0.1 of this design applied the framework at the **provider** level and chose Nebius. v0.2 applies it at the **query** level: a query's privacy class determines which providers are eligible, then we pick the cheapest eligible provider for that class.

| Query class | Hard requirement | Eligible providers |
|---|---|---|
| **Public** — no PII, no company data, references only third-party/public content | None — any reachable provider | All; pick cheapest = DeepSeek native |
| **Internal** — company code/schemas/metadata, but no PII | EU residency, GDPR | Nebius (chosen), Scaleway (when V4), Bedrock-EU, Foundry-EU |
| **Confidential** — PII, secrets, customer data, regulated content | Anthropic-only by policy | Anthropic direct |

This is how we **reclaim DeepSeek native as a legitimate tier** instead of disqualifying it wholesale — it is the cheapest provider for the slice of traffic where its hosting location is irrelevant.

### 3.2 Candidates per tier

**Tier 1 (Public)** — cheapest available; jurisdiction does not matter:

| Provider | Price ($/M in / out) | Latency from ES | Notes |
|---|---|---|---|
| **DeepSeek native API** (China) | **$0.14 / $0.28** (V4 Flash); $0.435 / $0.87 (V4 Pro, promo until 2026-05-31) | ~250 ms | Cheapest. Default tier-1. |
| Nebius (tier-2 also serves tier-1 if killswitch on) | tier-2 price | ~30 ms | Used as tier-1 fallback when kill-switch enabled |

**Tier 2 (Internal / EU)** — hard requirement: EU residency + GDPR:

| Provider | EU host | DeepSeek V4 today | Pricing tier ($/M in / out) | Latency from ES |
|---|---|---|---|---|
| **Nebius Token Factory** (Amsterdam) | yes | V4 Pro confirmed; V4 Flash via Token Factory | specialist EU tier, ~$0.30–1.00 / ~$0.90–2.50 (exact at signup) | ~30 ms |
| Scaleway Generative APIs (Paris/Ams) | yes | V3 confirmed; V4 not yet listed | ~$0.85 / ~$2.50 (V3 era) | ~25 ms |
| EUrouter (gateway, multi-upstream) | yes (routing) | V4 Flash | upstream + margin | variable |
| AWS Bedrock DeepSeek-R1 (eu-* regions) | partial (verify residency) | R1 yes; V4 emerging | **$1.35 / $5.40** (list, AWS docs) | varies |
| Azure AI Foundry DeepSeek | partial (region-dependent) | R1 yes | hyperscaler tier (~Bedrock-class) | varies |

**Tier 3 (Confidential / escalation)** — Anthropic direct only by policy:

| Model | Use |
|---|---|
| `claude-haiku-4-5` | default escalation; cheap; coding & tool calls |
| `claude-sonnet-4-6` | reserved for skill-factory generation and tasks Haiku fails on |

### 3.3 Decisions

- **Tier 1 → DeepSeek native API.** Cheapest globally for V4 Flash. Acceptable because tier-1 traffic by definition contains no company-internal or PII content. The kill-switch (env `DEEP_DEVOPS_DISABLE_PUBLIC_TIER=1`) collapses tier 1 into tier 2 — single line in production to neutralise the risk while we calibrate the classifier.
- **Tier 2 → Nebius Token Factory.** Passes HARD filters (EU + GDPR), serves V4 today, **3–5× cheaper than AWS Bedrock and Azure AI Foundry** for DeepSeek-class workloads. Bedrock DeepSeek-R1 list price is **$1.35 / $5.40** per M tokens (confirmed AWS docs); Foundry is in the same hyperscaler band. Reassess at M2: if Scaleway adds V4, swap (lower latency from ES, equal cost). The gateway abstraction (M1) makes the swap mechanical.
- **Tier 3 → Anthropic direct.** Haiku 4.5 as the working escalation model; Sonnet 4.6 reserved for offline skill-factory synthesis.
- **Why not just Nebius for everything (v0.1 design):** correct, EU-safe, and 3× cheaper than hyperscalers — but DeepSeek native at $0.14/$0.28 is another ~3× below Nebius for the half of traffic that has no privacy requirement (public docs, library questions, generic patterns). Splitting tier-1 captures that compounding saving.
- **Why not hyperscalers anywhere:** Bedrock + Foundry add 3–5× cost over a specialist for the same DeepSeek model and add nothing we need at this scale (no VPC/IAM integration requirement). They remain a credible tier-2 fallback if Nebius availability becomes a concern.

### 3.4 Cost sanity check (illustrative, 50/40/10 mix)

Workload: 5M input + 1M output tokens / month. Assumed routing mix once classifier is stable: 50% public, 40% internal, 10% confidential.

| Tier | Volume (in / out) | Approx monthly $ |
|---|---|---|
| DeepSeek native (public, V4 Flash) | 2.5M / 0.5M | ~0.35 + 0.14 ≈ **$0.50** |
| Nebius (internal, V4 Flash est.) | 2M / 0.4M | ~0.60 + 0.60 ≈ **$1.20** |
| Anthropic Haiku (confidential + escalation) | 0.5M / 0.1M | ~0.40 + 0.40 ≈ **$0.80** |
| **Total** | | **~$2.50** |

Reference baselines on the same workload: Nebius-only ≈ $3; Bedrock-only ≈ $12; Foundry-only ≈ $10–14; Haiku-only ≈ $8 (over Pro included quota).

The 3-tier strategy saves another ~20% over Nebius-only **by offloading the half of traffic that doesn't need EU hosting to the cheapest source possible**, with the kill-switch as insurance.

Numbers will be replaced by **cost per completed request** measurements once Nebius is live (Cap 9 p.415 — the right comparable, not cost per token).

### 3.5 Why this works only with strict guardrails

The 50/40/10 saving exists **only** if the publicness classifier is right. A single leak of internal data to DeepSeek-CN is a worse outcome than the cost saving justifies. Mitigations baked into the design:

- **Two-of-two rule.** A query reaches tier 1 only when *both* checks pass: (a) the rules-based PII/secret scanner is clean **and** (b) the publicness classifier returns "public". Either fails → tier 2 or higher.
- **Allowlist of public-tier triggers.** Known-public domains (`docs.python.org`, `postgresql.org`, etc.), generic technical vocabulary, queries without file/path references. Negative allowlist of internal markers (internal hostnames, package prefixes) loaded from `.deep-devops/internal-markers.txt`.
- **Audit log.** Every tier-1 routing decision is logged with the inputs the classifier saw and the reason it qualified. Reviewed on a cadence.
- **Kill-switch.** `DEEP_DEVOPS_DISABLE_PUBLIC_TIER=1` collapses tier 1 to tier 2. No code change required; single env var to neutralise the risk.
- **Conservative default.** When in doubt, classifier returns "not public" → tier 2. The publicness classifier is a *whitelist*, not a *blacklist*: a query must affirmatively satisfy public markers, not merely fail to match internal markers.

---

## 4. Security model

> *Ground truth: Cap 10 §"Step 2. Put in Guardrails" (p.451–455); Cap 4 §Hard attributes (p.179-180).*

### 4.1 Hard rule

Internal and confidential data **never leave the EU** without an explicit policy decision. The hard attribute (Cap 4 p.179-180) is enforced as an **input** guardrail, not as an output check — by the time the output exists the data has already been sent.

Three classes, three destinations:
- Confidential (PII / secrets / customer data) → Anthropic direct only.
- Internal (company code/schemas, no PII) → Nebius (EU) only.
- Public (no company content) → DeepSeek native is allowed.

Misclassification of internal-as-public is the failure mode of record; §3.5 covers the mitigations.

### 4.2 Input guardrails (Cap 10 §Input Guardrails, p.451–452)

Two risk classes per the chapter: **leakage of private info** to external APIs, and **prompt injection / model manipulation**. Both apply to a coding agent that reads from arbitrary files.

**PII / secret redaction with reverse map — Figure 10-3, p.453.**
Pattern: detect entities, replace with placeholders (`[ACCESS_TOKEN]`, `[CUSTOMER_NAME]`, `[INTERNAL_HOST]`), call the model, de-redact the response.
Implementation surface: `deep_devops/router/redaction.py`.
The book's nuance we keep: redaction enables sending the *non-confidential remainder* to a lower tier. If the only confidential content was a hostname, we redact it and stay in tier 2.

**Confidentiality classifier — rules first.**
Regex for known secret formats: `AKIA[0-9A-Z]{16}` (AWS), `sk-[A-Za-z0-9]{20,}` (OpenAI-style), `BEGIN [A-Z ]+PRIVATE KEY` (PEM), Bearer-token regex, internal-domain allowlist. Plus path-based allowlist (`/secrets`, `.env*`, `**/credentials.*`).
Anything that triggers and **cannot be safely redacted** forces tier 3 (Anthropic). This honours Cap 10 p.457's "fast and cheap router" principle in the security plane.

**Publicness classifier — rules + allowlist (tier-1 gate, NEW in v0.2).**
Runs *after* the PII/secret scan is clean. A query qualifies as "public" only when *all* of the following hold:
- PII/secret scan returned clean (preconditions).
- No reference to internal hostnames, internal package names, or company-specific identifiers (negative allowlist loaded from `.deep-devops/internal-markers.txt`).
- File contents attached, if any, come from an allowlisted "public" directory (`.deep-devops/public-paths`) — or no file contents are attached at all.
- Query text contains "public-coded" markers (asking about a public library, generic algorithm, standard SQL/syntax, third-party documentation) **or** the query has no path/file/identifier references at all.

If all conditions hold → tier 1. Otherwise → tier 2. **The classifier is a whitelist:** it must affirmatively conclude "public", not merely fail to find evidence of "internal". This is the conservative direction; the cost of a false positive (data leak) dwarfs the cost of a false negative (slight cost overage on a tier-2 routed query).

**Why rules, not LLM-judge here.** Cap 10 p.457 ("fast and cheap"); Cap 3 p.144 (LLM-judge unreliable). For a one-way error like a privacy leak, determinism beats accuracy.

**Scanner coverage (M1):** emails, phone numbers (intl + 9-digit ES/US), password fields (`password=`, `contraseña=`, `pwd=`, `passwd:`), AWS/OpenAI/Anthropic/GitHub/Stripe/Slack/Telegram keys, JWTs, Bearer tokens, PEM keys, DB URLs with embedded passwords, RFC-1918 private IPs, internal hostnames (`.internal`, `.corp`, `.lan`), secret file paths (`.env`, `/secrets/`, `*.pem`, `*.key`, `credentials.*`). 100/100 tests.

**NER gap (M2 candidate):** the regex scanner cannot detect proper names ("García López"), organisations, or arbitrary short passwords without a label. Adding a lightweight NER model (spaCy `es_core_news_sm`, ~12 MB) would add `NOMBRE_PROPIO`, `APELLIDO`, `ORGANIZACION` detection with zero LLM cost and sub-millisecond latency — consistent with the "fast and cheap" principle (Cap 10 p.457). Gated on M2 because it adds a native dependency and requires an eval set for Spanish NER precision/recall.

**Prompt-injection defence.** Cap 10 calls for treating tool outputs (file reads, web fetches) as untrusted input. MVP has no online retrieval, so the surface is file content; we **log** suspicious patterns (jailbreak phrases, role-reversal, system-prompt extraction probes) rather than block. Block-mode arrives when eval coverage distinguishes false positives.

### 4.3 Output guardrails (Cap 10 §Output Guardrails, p.453–455)

Failure types from the chapter, scored for our context:

| Failure | Relevance | Mechanism |
|---|---|---|
| Malformed structured output | high | JSON schema validation (pydantic) on every tool call |
| Factual inconsistency | low (no RAG in MVP) | deferred |
| **Remote tool / code execution risk** | **critical** | Cap 10 p.464 "write actions = capability + risk". File writes, shell exec, git ops require explicit accept in TUI |
| Toxicity / brand risk | very low | not addressed in MVP |

**Policy on failure:** simple retry first (Cap 10 p.454 — "retry logic covers many failures"); on the *second* consecutive failure of the same signal, escalate **one tier up** (1→2, 2→3). Parallel-call retries (p.454) deferred until cost data justifies them.

**Streaming caveat (Cap 10 p.455):** stream free text; buffer-then-validate for tool-call payloads.

### 4.4 Why not LLM-as-judge for confidentiality

- Cap 10 p.457 — *"Routers should be fast and cheap"*.
- Cap 3 p.144 — LLM judges are slow, inconsistent, add 50–100% latency, exhibit self-bias.

Rules are auditable, deterministic, free, fast. Only if rule precision/recall is insufficient on the eval set will we consider a small classifier (Cap 10 p.457 cites GPT-2/BERT scale, not an LLM).

---

## 5. Response quality evaluation

> *Ground truth: Cap 3 §Functional Correctness; Cap 3 §AI as Judge Limitations; Cap 4 §Design Your Evaluation Pipeline.*

### 5.1 Hot-path failure detection (Cap 3 p.123, p.126–127)

**No LLM-judge online.** Cap 3 p.141–145 case against LLM-judge in the request path: inconsistency (p.142), self-bias (GPT-4 +10%, Claude-v1 +25% on own outputs, p.144), verbosity/position bias (p.144–145), doubles cost and latency (p.144), no standardisation (Table 3-4). Author's recommendation (p.144): **exact metrics on 100% of traffic, AI-judge on 1% offline.**

Four cheap deterministic signals used online (applies to *all* tiers):

| Signal | Book ref | Triggers escalation? |
|---|---|---|
| Test suite execution result on generated code | Cap 3 p.126 (pass@k) | yes on failure |
| JSON schema validation of tool calls | Cap 3 §Exact Evaluation | yes on invalid |
| Logprobs / perplexity (if provider exposes) | Cap 3 p.123 | borderline → log only |
| Regex / FITS-cluster phrases in response | Cap 10 Table 10-1, p.478 | yes on match |

**No lexical similarity (BLEU etc.) at any point.** Cap 3 p.131: BLEU does not correlate with functional correctness for code.

### 5.2 Offline evaluation pipeline (Cap 4 §Design Your Evaluation Pipeline, p.200–207)

Three-step recipe mapped:
1. **Per-component eval — turn-based + task-based (p.201).** Per-turn correctness + per-task completion.
2. **Explicit rubrics with examples (p.202–203).** Acceptance criteria per task.
3. **Cheap-on-100% + expensive-on-1% (p.204).** All §5.1 signals on every replay; Sonnet-4.6 LLM-judge on 1% for calibration.

**Eval set sizing (Cap 4 Table 4-7, p.207):** ~100 → 10% delta, ~1000 → 3%, ~10000 → 1%. **Target: 1000 examples by M3.** Bootstrap-augmented with FITS categories (Cap 10 Table 10-1).

**Per-task selection table — Cap 4 Table 4-3 (p.178)** is now **per-tier**: each row is `(task type × tier)` with cost/M, P90 TTFT, pass@1 min, factual-consistency min. The router reads from this table.

**Data contamination (Cap 4 p.197–199):** hold-out is private; never logged into any model API.

### 5.3 Drift detection (Cap 10 p.471–472)

- **Model drift** — pin model version strings; re-run eval set on observed change (Voiceflow incident, 10% drop).
- **Prompt drift** — prompts committed to git; eval runs tagged with commit SHA.
- **User-behaviour drift** — FITS-cluster distribution logged.
- **Classifier drift (NEW in v0.2)** — tier-1/tier-2 split ratio is itself a tracked metric; if it climbs unexpectedly (more public-classified queries), audit a sample.

---

## 6. Observability

> *Ground truth: Cap 9 §Inference Performance Metrics (p.412–418); Cap 10 §Monitoring (p.465–471); Cap 10 §User Feedback (p.474–488).*

### 6.1 Metrics per call (Cap 9 p.412–418)

Logged to JSONL (M1) → Langfuse (self-hosted) / OTel (M3):

| Metric | Why (book ref) |
|---|---|
| `ttft_ms` | Cap 9 p.413 — prefill-bound |
| `tpot_ms` | Cap 9 p.413 — decode-bound |
| `total_latency_ms` | TTFT + TPOT × output |
| `time_to_publish_ms` | Cap 9 p.413 — first token *the user sees*, most honest UX metric for agents |
| `goodput_per_slo` | Cap 9 p.415 — RPS meeting an SLO |
| `cost_per_request` | Cap 9 p.415 — comparable across tokenizers |
| `input_tokens`, `output_tokens`, `cached_input_tokens` | cost + prompt-cache attribution (Cap 9 Table 9-3) |
| `model_id`, `provider`, `tier`, `route_decision`, `escalated_from` | router/tier analysis (NEW: tier label) |
| `classifier_reason` | for tier-1 audit (NEW in v0.2) |

Percentiles p50/p90/p95/p99 (Cap 9 p.414). Means are forbidden — outliers mislead.

### 6.2 System-level (Cap 10 p.466)

- **MTTD** — mean time to detect a regression
- **MTTR** — mean time to recover (rollback router config)
- **CFR** — change failure rate; high CFR on router-config = freeze and re-evaluate
- **Tier-1 leak rate (NEW)** — number of post-hoc reviews that flag a tier-1 routing as wrong. Hard target: 0. Any positive value → kill-switch ON until root-caused.

### 6.3 Traces (Cap 10 p.470, Fig 10-11)

One `trace_id` per conversation; one `span_id` per model call. Log: final prompt, intermediate outputs, tool calls, tool outputs, timings. M1 = JSONL on disk; M3 = Langfuse self-hosted (Docker + Postgres) / OTel.

**Why Langfuse over LangSmith (decided 2026-05-14).** LangSmith free tier shares telemetry; Langfuse is self-hostable (`docker compose up`) with zero third-party telemetry sharing. Native LangChain `CallbackHandler` drops in without code changes — relevant because deepagents is LangChain-based. OTel export keeps us unlocked. Langfuse also provides eval scoring on traces, feeding directly into the §7 skill-factory feedback loop.

**Local telemetry is fully feasible despite serverless API calls (Cap 10 p.469–470).** The application process (`RouterChatModel._generate()`) runs on the user's machine; the provider only handles model inference. Everything measurable from the client side — TTFT (wall-clock from request send to first streamed token), TPOT, total latency, input/output tokens from `usage` metadata, routing decision, PII scan result — is captured locally before the response is returned. Provider-internal queue time is invisible but is implicit in client-measured TTFT, which is the metric that matters for UX.

**M1 JSONL trace schema (one record per model call, appended to `~/.deep_devops/traces.jsonl`):**

```json
{
  "trace_id": "<uuid4>",
  "span_id": "<uuid4>",
  "ts_start": "<ISO8601>",
  "model_id": "deepseek-chat",
  "provider": "deepseek_native|nebius|anthropic",
  "tier": 1,
  "route_decision": "public|internal|confidential|escalated",
  "escalated_from": null,
  "classifier_reason": "public_markers_present",
  "pii_clean": true,
  "redacted_fields": [],
  "input_tokens": 123,
  "output_tokens": 45,
  "cached_input_tokens": 0,
  "ttft_ms": 234,
  "tpot_ms": 12.3,
  "total_latency_ms": 1234,
  "cost_usd": 0.000034,
  "prompt_hash": "<sha256 of final prompt>",
  "tool_calls": [],
  "escalation_signal": null
}
```

M3 upgrade: replace `jsonl.append(record)` with `langfuse.trace(**record)` — same schema, different sink.

### 6.4 User feedback — implicit signals (Cap 10 p.474–488)

Input to the skill factory. Explicit feedback (👍/👎) suffers from leniency and response bias (p.474–475); rely on implicit.

| Signal | Interpretation | Book ref |
|---|---|---|
| User aborts (Ctrl-C mid-stream, closes TUI) | conversation going wrong | p.476 |
| Rephrase patterns ("No,…", "I meant…", "Are you sure?") | model failed previous turn | p.477, Fig 10-12 |
| **User edits to model output** | preference pair: original=losing, edited=winning | **p.478 — the gold signal** |
| Regeneration request | retry signal | p.479 |
| Tool-call rejection in TUI | wrong tool / wrong args | p.464 |
| Refusal phrases from model | self-reported failure | p.479 |
| Conversation length × diversity | long + repetitive = stuck loop | p.480 |

**Integrated > standalone (Cap 10 p.487).** Our CLI lives inside the dev workflow — observes whether code was committed, tests passed, files edited. "Did the user really use it?" comes free.

---

## 7. Skill factory

> *Ground truth: Cap 10 p.478 + Cap 3 p.146.*

**Trigger.** A nightly offline batch job (Cap 9 p.410 — batch APIs at 50% discount) clusters failure traces by FITS category (Cap 10 Table 10-1) and prompt similarity. When ≥N similar failures accumulate (start at N=5, tune), the cluster is a candidate.

**Generation.** Sonnet 4.6 receives the cluster — failure prompts + successful escalation resolution + user-edit (losing, winning) pairs — and produces a **deterministic Python tool**: clear signature, docstring, tests. Output: a PR against `deep_devops/skills/`.

**Why a tool and not a fine-tune.** Cap 3 p.146 — specialised judges/skills (Cappy 360M is the example) outperform a general LLM at a fraction of the cost when the task is narrow. A Python tool is the limit: zero-LLM cost, zero variance, fully auditable. The model "learns" by gaining a tool, not by changing weights.

**Risks.**
- **Degenerate feedback loop (Cap 10 p.491–492):** if Sonnet only sees queries routed to Sonnet, we never test whether the lower tiers improved. Mitigation: 1% of traffic intentionally routed against policy (canary).
- **Sycophancy in distilled skills (Cap 10 p.492):** prefer skills whose tests are objective (run code, parse AST, hit a static rule) over skills whose validation is "looks right".
- **NEW v0.2 — cross-tier skill transferability:** a skill generated from a tier-2 failure may still be applicable when the model is tier 1. Skills are tier-agnostic by default; the router invokes the skill regardless of which model handles the surrounding turn.

---

## 8. Routing policy (state machine, three-tier)

```
incoming request
  +-- [PARALLEL] PII/secret scan  ||  publicness pre-check  (Cap 10 p.473 — run concurrently)
  |     Both are stateless and independent; asyncio.gather() in _generate().
  |     Combine results:
  |       confidential AND not redactable              -> tier 3 (ANTHROPIC)
  |       redactable                                   -> redact in place; continue
  |       pii_clean AND public AND kill-switch off     -> tier 1 (DEEPSEEK NATIVE)
  |       else                                         -> tier 2 (NEBIUS)
  |
  +-- context_size > current_tier_context_limit -> escalate one tier up
  |
  +-- output guardrails (schema, tests, regex/FITS)
        +-- all pass         -> return to user
        +-- transient fail   -> retry once on same tier
        +-- persistent fail  -> escalate ONE tier up (1->2, 2->3)
                                 log trace for skill factory
```

Escalation is **one tier up at a time**; no skips; no bounce back to a lower tier within a single user request.

---

## 9. Milestones (gates, not dates)

| M | Gate (what proves it is done) |
|---|---|
| **M0** | `uv sync` works; deepagents TUI runs against DeepSeek V4 via Nebius (tier 2); one round-trip succeeds; trace logged with TTFT/cost |
| **M1** | Gateway abstraction routes between Nebius and Anthropic; §6.1 metrics land in JSONL; gateway choice (Portkey vs custom) decided |
| **M2** | Input guardrails active: PII redaction + reverse map; confidentiality rule enforced; **publicness classifier (tier-1 gate) live behind kill-switch OFF by default**; output guardrails on tool-call schema + retry-once; observable tier mix and escalation count |
| **M3** | Eval harness with ≥1000 examples; per-`(task, tier)` router table populated; report shows cost & pass@1 by model on the eval set. **Tier-1 enable gated on classifier precision/recall on a held-out leak-detection eval set.** |
| **M4** | Skill factory: implicit signals captured in TUI; offline batch clusters failures; first auto-generated skill PR'd to `skills/` |
| **M5** | README polished, install script, MIT licence, published to GitHub for colleagues |

---

## 10. Open questions

- Does Nebius expose token-level logprobs through its OpenAI-compatible endpoint? (affects §5.1 perplexity signal)
- ~~Portkey vs MLflow AI Gateway vs thin custom gateway~~ **CLOSED (2026-05-14): thin custom.** Three LangChain clients (one per tier) wired via `RouterChatModel(BaseChatModel)`. No external gateway needed.
- Tool definitions stable enough across sessions for Anthropic prompt-cache to pay off, given dynamic `skills/`? Probably yes if skill registration is versioned; verify at M2.
- TUI hook for "user edited the output" — does deepagents expose this event, or do we need a fork/PR? Investigate at M4.
- Confirm Azure AI Foundry DeepSeek exact prices once a comparable Bedrock figure is in production; treated as same-tier as Bedrock based on hyperscaler pricing norms.
- **NEW v0.2: how to build the leak-detection eval set for the publicness classifier?** Synthetic mix of (a) clearly-public queries (open-source docs Q&A), (b) clearly-internal queries (company-coded examples), (c) adversarial near-miss queries that look public but reference internal markers. Target metrics: leak rate (internal → tier 1) hard zero on validation, false-negative rate (public → tier 2) tolerable up to 30% (lose some savings, never leak).
- **NEW v0.2: legal / policy review** of sending public technical content to DeepSeek native (China). Even if no company data is involved, an enterprise policy might still forbid all China-hosted inference. Confirm before enabling tier 1 in production.

## 11. Integration with deepagents CLI (decided 2026-05-14)

> **⚠ Amendment 2026-05-16 — premise invalid w.r.t. `/model`.** The claim below
> that `RouterChatModel` is "the single entry point" is **false** as soon as
> the user issues `/model …` (or launches with `--model <other>`): deepagents
> instantiates a *different* model class entirely (`ChatOpenAI`,
> `ChatAnthropic`, `ChatDeepSeek`, …), and our `_route()` is never in its
> call path → scan/redact/tier-routing are silently bypassed. Currently
> mitigated **by deployment process** ("launch with `--model
> deep-devops:router`; do not use `/model`"), not technically. The
> architectural fix — migrate the guardrail to an `AgentMiddleware`
> (`wrap_model_call`) so it runs for every model invocation regardless of
> `/model` — is **identified and planned**, not done. See
> [`session-2026-05-16-closeout.md`](session-2026-05-16-closeout.md) and the
> README's "What `/model` does" section.

The router plugs into the deepagents CLI via the official `class_path` mechanism in `~/.deepagents/config.toml` — no fork, no sidecar, no extra process.

```toml
[models.providers.deep-devops]
models     = ["router"]
class_path = "deep_devops.router.model:RouterChatModel"
enabled    = true
```

`RouterChatModel(BaseChatModel)` in `deep_devops/router/model.py` is the single entry point. Its `_generate()` method runs: `asyncio.gather(pii_scan, publicness_check)` → combine results → tier dispatch → JSONL log. The two scans are stateless and independent, so they run concurrently (Cap 10 p.473). The three tier clients (tier1: DeepSeek native, tier2: Nebius, tier3: Anthropic) live in `deep_devops/gateway/` and are constructed once at agent init from `.env`.

Launch: `deepagents --model deep-devops:router`

Source: `docs.langchain.com/oss/python/deepagents/cli/configuration`
