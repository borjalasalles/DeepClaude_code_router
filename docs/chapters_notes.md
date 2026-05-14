# Chapter notes — Chip Huyen, *AI Engineering*

Condensed reading of chapters 3, 4, 9, 10 against this project's needs. Every section in `docs/design.md` cites back here. Page numbers refer to the book's print pagination (the PDFs in `ai_engineering/` are page-shifted; use the print pages).

---

## Cap 3 — Evaluation Methodology

### Detecting "DeepSeek failed" without paying for an LLM-judge (Functional Correctness, p.126-127; Exact Evaluation)

- Code outputs: **execution accuracy / pass@k** over auto-generated unit tests (HumanEval/MBPP use this exactly). Applied here: every code edit → run tests; fail = escalation trigger.
- Tool calls: **structural validation** — JSON schema valid, tool name exists, args typed correctly. Chen et al. 2021 (cited p.131) shows BLEU/lexical similarity does **not** correlate with correctness.
- Free text: **logprobs / perplexity** of the model's own output as a confidence proxy (p.123). If Nebius exposes logprobs, this is a free signal.
- **Deterministic heuristics** (regex, parsers, linters, AST validity) cover most coding failures without any LLM. Most cost-effective.

### When NOT to use LLM-as-judge (Limitations of AI as a Judge, p.141-145)

- Inconsistency: same judge gives different scores on the same input (p.142).
- Cost/latency: doubles each request (p.144). Unviable in hot path.
- Biases: **self-bias** GPT-4 +10%, Claude-v1 +25% (p.144); position bias; verbosity bias (favours ~100-word over 50-word at equal quality).
- No standardisation across frameworks (Table 3-4: MLflow 1-5, Ragas 0/1, LlamaIndex YES/NO).
- **Author's recommendation (p.144):** AI-judge as **spot-check on 1% of traffic**, exact metrics on 100%.

### When LLM-judge IS worth it

- Open-ended tasks without ground truth (p.137).
- Subjective criteria (coherence, helpfulness) as last-resort fallback.
- **Specialised reward models / small judges** (p.146-147, "Cappy" 360M params) are more reliable and cheaper than GPT-4 general-purpose.

---

## Cap 4 — Evaluate AI Systems

### Model-selection workflow (Figure 4-5, p.180), 4 iterative steps

1. Filter by **hard attributes** (privacy, licence, on-device) → reduces the pool drastically.
2. Public benchmarks → shortlist.
3. **Private prompts / metrics** on your real tasks.
4. **Online monitoring** + feedback to iterate.

### Criteria to fix BEFORE choosing DeepSeek vs Haiku (Evaluation Criteria, p.160-178)

Four buckets:
- **Domain-specific capability** (can the model do coding/tool-use?): pass@1 / functional correctness.
- **Generation capability**: factual consistency, fluency.
- **Instruction-following**: use **IFEval** (Table 4-2, p.173) — automatable tests like "include keyword X", "answer in JSON", "max N words". Critical for an agent.
- **Cost & latency** (Table 4-3, p.178): formalise with **hard requirement + ideal** per criterion. Columns: cost/1M tokens, TPM, P90 TTFT, P90 time/query, code pass@1, factual consistency. **This is the routing table; populate per task type.**

### Hard vs soft attributes (p.179-180)

Privacy is HARD (rule, eliminates options). Latency is SOFT (rank-by-fit if optimisable).

### Designing the evaluation pipeline (Design Your Evaluation Pipeline, p.200-207)

- **Step 1:** evaluate each component independently — **turn-based + task-based** (p.201). For an agent: per-turn correctness + per-task completion.
- **Step 2:** explicit rubrics with examples (p.202-203). "Correct ≠ good response" (cited from LinkedIn).
- **Step 3:** mix cheap-on-100% + expensive-on-1% (p.204). Logprobs where available.
- **Eval-set size** (Table 4-7, p.207): ~100 detects 10% diff, ~1000 → 3%, ~10000 → 1%. Bootstrap for reproducibility.
- **Tie eval metrics to business metrics** (p.203): e.g., "factual consistency 80% → automate 30% of support". For us: "DeepSeek pass@1 > 0.85 on task type X → do not escalate".
- **Data contamination** (p.197-199): public scores are unreliable; run a private hold-out.

---

## Cap 9 — Inference Optimization

### Client-side techniques (we are not hosting the model)

- **Prompt caching** (p.443-444, Table 9-3). Anthropic ships up to **90% cost reduction and 75% TTFT reduction** on long stable system prompts. Tool defs + repo context + system prompt are large and constant → cache mandatory. Confirm prefix-cache support on Nebius (typically vLLM auto-prefix-cache).
- **Streaming** (p.410-411): always on for TUI UX.
- **Batch APIs** (p.410): 50% discount on Gemini/OpenAI for hours-latency jobs. Useful for offline tasks: indexing, skill synthesis, eval replays. NOT for hot path.
- **KV-cache awareness** (p.433-435): not directly addressable as a client, but **structure prompts to maximise prefix-cache hits** — stable system prompt + tool defs first, mutating conversation history last. Reordering breaks the cache.

### Metrics to log (Inference Performance Metrics, p.412-418)

- **TTFT** — prefill cost, scales with input length.
- **TPOT** — decode cost.
- **Total latency** = TTFT + TPOT × output_tokens.
- **Time to publish** (p.413): for agents with CoT/tool calls, when the *user* sees the first useful token (not first internal token). Critical for our case.
- Percentiles p50/p90/p95/p99 (p.414). Means mislead.
- **Goodput** (p.415): RPS satisfying an SLO. Better than throughput.
- **Cost per request**, not per token (p.415): comparable across tokenizers.

### Caching of responses / semantic cache

Covered in Cap 10 (p.460-462). Author calls semantic cache **"dubious"** (p.462) — depends on embedding quality + threshold, risks returning a wrong user's response (PII example, p.461). For a coding agent: **NO semantic cache**. YES exact cache for deterministic tool calls (lint, "list files in dir").

---

## Cap 10 — Architecture & User Feedback (the chapter that most directly informs our design)

### Architectural progression (Figures 10-1 to 10-10, pp.450-464)

Build incrementally:
1. Plain Model API (Fig 10-1)
2. + Context construction (RAG, tools, read-only) (Fig 10-2)
3. + Input/output guardrails (Fig 10-4)
4. + Router + Gateway (Fig 10-5, 10-7)
5. + Caches (Fig 10-8)
6. + Agent loop / write actions (Fig 10-9, 10-10)
7. Observability throughout

Our milestones (M0…M5) follow this order.

### Model router pattern (Step 3, p.456-457)

- **Intent classifier in front of the models.** *"Routers should be fast and cheap"* (p.457) → small models like GPT-2/BERT/Llama-7B, or trained-from-scratch classifiers. **Validates our rules-only choice.**
- Router as **next-action predictor** for agents (p.457): decides which tool/resource. Maps directly to our retry-on-failure escalation.
- Routing **before** retrieval (p.457) decides if a query is in-scope; routing **after** decides if escalation is needed (in our case → Claude).
- Watch **context-limit routing** (p.457): if DeepSeek 128k vs Haiku 200k, large-context tasks force the choice.

### Gateway (p.458-460)

- Unified wrapper over multiple providers (Fig 10-6). Our exact case (DeepSeek-via-Nebius + Anthropic).
- Functions: **access control, cost management, rate-limit / fallback, logging, caching, guardrails** (p.459).
- Off-the-shelf options the book lists (p.460): **Portkey, MLflow AI Gateway, Wealthsimple's LLM Gateway, TrueFoundry, Kong, Cloudflare**. Use one before writing our own.

### Guardrails (Step 2, p.451-455)

- **Input guardrails** (p.451-452): leakage to APIs + prompt injection. **PII reverse-map redaction** (Fig 10-3, p.453) — replace secrets with placeholders, call the model, de-redact on return. Directly applicable to "confidential → Claude": if PII is redactable, redact and still go EU; only the non-redactable forces Claude.
- **Output guardrails** (p.453-455): malformed JSON, factual inconsistency, toxicity, brand risk, **remote tool/code execution risks**. **Retry logic** (p.454) covers many failures. **Parallel calls** to cut retry latency, watch the cost. Streaming + output guardrails are incompatible if you need to inspect the full response (p.455).
- Trade-off **reliability vs latency** is explicit (p.455).

### Caches (p.460-462)

Place caches **before** the gateway (user-query cache, Fig 10-8) and **after** read-only actions (retrieval, web search). Semantic cache — dubious. Exact cache — fine.

### Agent patterns & orchestration (Step 5, p.463; AI Pipeline Orchestration, p.472-474)

- Write actions = capability + risk (p.464). For us: file writes, git ops, shell exec → need strong output guardrails and explicit accept.
- **Orchestrator ≠ workflow runner** (Airflow style) (p.473).
- *"You might want to start building your application without one first"* (p.473) — explicit warning against premature LangChain/LlamaIndex adoption. **deepagents already orchestrates; do not add another layer.**
- For latency: parallelise routing and PII redaction (p.473).

### Monitoring & observability (p.465-471)

- DevOps metrics: **MTTD, MTTR, CFR** (p.466). High CFR on router-config deploys → freeze and re-evaluate.
- Log everything: configs, final prompts, intermediate outputs, tool calls, tool outputs, timings (p.470). Traces with correlated IDs (Fig 10-11, LangSmith-style).
- **Drift detection** (p.471-472): system-prompt drift, user-behaviour drift, **underlying model drift** (cites Voiceflow's 10% drop on silent update). Pin model versions; re-eval on change.

### User feedback (p.474-488) — the heart of our "skill factory"

- Feedback is **proprietary data = competitive advantage** (p.474). A data flywheel.
- **Explicit** (thumbs/star): clear but scarce, leniency bias, response bias (the unhappy over-report).
- **Implicit** (p.475-479): more abundant, noisier.

  Captured signals usable in CLI/TUI:
  - **Early termination** — user aborts (Ctrl-C, closes TUI mid-stream) → conversation went wrong (p.476).
  - **Error correction / rephrase** — "No,…", "I meant…", "Are you sure?" (p.477). Fig 10-12 shows the pattern.
  - **User edits to model output** (p.478): the edited version = winning, the original = losing. **The gold signal.**
  - **Complaints clustering** (Table 10-1, p.478, FITS dataset): 8 canonical groups — "clarify demand", "irrelevant info", "factually wrong", "not specific enough", "low confidence", "repetition", etc.
  - **Refusal rate** (p.479): "I can't…" → failure signal.
  - **Regeneration** (p.479): retry signal, stronger with usage-billed pricing.
  - **Organisation**: delete = bad, rename = good (p.479).
  - **Length × diversity** (p.480): long + repetitive = stuck loop.

### Feedback design (p.481-488)

- **When to ask**: at start (calibration), when something looks wrong, when the model is uncertain (show two options side-by-side, p.483, Fig 10-15).
- **How**: non-intrusive, easy to ignore, **integrated into the workflow**. **GitHub Copilot's Tab-to-accept (Fig 10-19) is the gold standard**: accept/reject is the action itself, not an extra widget. Maps to our TUI diff accept/reject.
- **Standalone vs integrated** (p.487): generic chatbots can't tell if their output was used. **Our CLI is in the dev's workflow** — file edits, test runs, commits → real usage signal **for free**. Structural advantage.

### Feedback limitations (p.490-492)

- Biases: leniency, randomness, position, recency, verbosity.
- **Degenerate feedback loop** (p.491-492): if the router trains only on queries already routed to Claude, the pattern is reinforced. Sample counter-intuitively (occasionally route an "obvious-for-Claude" query to DeepSeek to test improvement).
- **Sycophancy** (p.492, Sharma et al. 2023): RLHF-trained models tend to confirm the user. Beware when distilling skills from Claude — skills may be "agreeable" rather than correct. Prefer skills whose tests are objective.

---

## 10 implications for this project

1. **No LLM-judge in router hot path.** Detect DeepSeek failure via (a) test runner, (b) JSON-schema validation, (c) logprobs if exposed, (d) regex / FITS-cluster phrases. AI-judge only as 1% offline spot-check (Cap 3 p.144).
2. **Build Table 4-3 per task type** (coding/refactor/git-op/explain/test-gen). Each row: cost/M, P90 TTFT, pass@1 min, factual-consistency min. The router *is* that table.
3. **Adopt a gateway off the shelf** (Portkey or MLflow AI Gateway, p.460). Fallback, rate-limit, logging, caching — free.
4. **PII reverse-map redaction** as the input guardrail (Fig 10-3). "Confidential → Claude" becomes finer: redactable → still EU; non-redactable → Claude. Saves money, keeps the hard rule.
5. **Pin model versions and monitor drift** (p.472). Each release of V4 or Haiku may move the eval baseline. CFR-style rollback.
6. **Log Cap 9 metrics** per model and task: TTFT/TPOT p50/p90, goodput vs SLO, cost-per-completed-request.
7. **Prompt caching mandatory on Anthropic** (90% / 75%). System prompt + tool defs first, history last. Confirm prefix-cache on Nebius.
8. **Skill factory = edit-based preference data** (p.478). When the dev edits the agent's output, log (output_v1, edited). When Claude solves what DeepSeek failed + tests pass → skill candidate. **Crystallise as deterministic Python tool in git, do not fine-tune** (Cap 3 p.146).
9. **Capture implicit signals in TUI**: early termination, Ctrl-C, rephrase, deletion, tool rejection. These are the signals on pp.476-479; integration into the dev workflow makes them all accessible (p.487).
10. **Eval set ≥1000** with real workflow tasks (Table 4-7) + IFEval-style auto-checks for structured tool calls (Table 4-2) + pass@1 on a coding corpus. Validate every router change against the eval before merge. **No orchestrator on top of deepagents** (p.473).
