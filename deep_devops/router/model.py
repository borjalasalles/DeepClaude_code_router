"""
RouterChatModel — entry point wired via class_path in ~/.deepagents/config.toml.

M1 routing (single tier active):
  - Scan only user-authored (HumanMessage) content for PII/secrets.
  - If PII found: redact in place with {/TYPE/} placeholders, continue to tier 1.
  - Session never blocks due to PII — redaction is the mitigation.
  - Tier classification is logged for future routing (tier 2/3 wired in M2).
  - System prompt and AI messages are not scanned (trusted/already processed).
  - Fail-closed: if the scanner itself raises, the request is aborted before any
    upstream call — the trace records ``scan_error: true`` and the exception is
    re-raised so the caller (deepagents) surfaces the error instead of sending
    unscanned text to the model (QA-D05).
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence, Union

from dotenv import load_dotenv
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool

from deep_devops.gateway.tier1 import build_tier1_client
from deep_devops.router.pii_scanner import scan
from deep_devops.router.redaction import RedactionContext, redact

load_dotenv()

_TRACE_PATH = Path.home() / ".deep_devops" / "traces.jsonl"
_KILL_SWITCH_ENV = "DEEP_DEVOPS_DISABLE_PUBLIC_TIER"


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------

def _human_text(messages: list[BaseMessage]) -> str:
    """Extract only HumanMessage content for PII scanning.

    System prompts (injected by deepagents) and AI messages are excluded —
    they are trusted/already-processed content that must not trigger false positives.
    """
    parts: list[str] = []
    for m in messages:
        if not isinstance(m, HumanMessage):
            continue
        if isinstance(m.content, str):
            parts.append(m.content)
        elif isinstance(m.content, list):
            for block in m.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block["text"])
    return "\n".join(parts)


# Keep the old name for tests that import it
_messages_to_text = _human_text



def _redact_messages(
    messages: list[BaseMessage], ctx: RedactionContext
) -> list[BaseMessage]:
    """Return a new messages list with PII placeholders substituted into HumanMessages."""
    if not ctx.reverse_map:
        return messages
    out: list[BaseMessage] = []
    for m in messages:
        if isinstance(m, HumanMessage) and isinstance(m.content, str):
            redacted = m.content
            for placeholder, original in ctx.reverse_map.items():
                redacted = redacted.replace(original, placeholder)
            out.append(HumanMessage(content=redacted))
        else:
            out.append(m)
    return out


def _is_public(text: str) -> bool:
    """Minimal publicness pre-check — whitelist semantics (design.md §4.2)."""
    internal_markers = [".internal", ".corp", ".lan", "/secrets/", ".env"]
    lower = text.lower()
    return not any(marker in lower for marker in internal_markers)


def _append_trace(record: dict[str, Any]) -> None:
    _TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _TRACE_PATH.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# RouterChatModel
# ---------------------------------------------------------------------------

class RouterChatModel(BaseChatModel):
    """Three-tier routing model wired into deepagents via class_path."""

    tier1_model: str = "deepseek-chat"
    tier1_temperature: float = 0.0

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "_tier1", build_tier1_client(
            model=self.tier1_model,
            temperature=self.tier1_temperature,
        ))

    @property
    def _llm_type(self) -> str:
        return "deep-devops-router"

    # ------------------------------------------------------------------
    # bind_tools — required by deepagents
    # ------------------------------------------------------------------

    def bind_tools(
        self,
        tools: Sequence[Union[BaseTool, dict[str, Any]]],
        *,
        tool_choice: Optional[Union[str, dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> Runnable:
        formatted: list[dict[str, Any]] = [convert_to_openai_tool(t) for t in tools]
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
        return super().bind(tools=formatted, **kwargs)

    # ------------------------------------------------------------------
    # Core routing — returns (redacted_messages, trace_meta)
    # ------------------------------------------------------------------

    def _route(self, messages: list[BaseMessage]) -> tuple[list[BaseMessage], dict[str, Any]]:
        """Scan HumanMessages, redact PII, classify intended tier for logging.

        Raises on scanner failure. Callers (``_generate``/``_stream``/``_agenerate``)
        wrap this in a fail-closed try/except that records a ``scan_error`` trace
        and aborts the upstream call (QA-D05).
        """
        user_text = _human_text(messages)
        scan_result = scan(user_text)
        ctx = redact(user_text, scan_result)

        pii_clean = not scan_result.detected
        redacted_fields = scan_result.entity_types() if scan_result.detected else []

        # Build redacted message list (no-op when no PII)
        active_messages = _redact_messages(messages, ctx) if scan_result.detected else messages

        # Classify intended tier for the trace log (tier 2/3 not wired yet)
        kill_switch = os.environ.get(_KILL_SWITCH_ENV, "").strip() == "1"
        if scan_result.detected:
            intended_tier = 2  # would go to EU after redaction
            route = "internal_redacted"
            classifier_reason = f"pii_redacted:{','.join(set(redacted_fields))}"
        elif kill_switch or not _is_public(user_text):
            intended_tier = 2
            route = "internal"
            classifier_reason = "kill_switch" if kill_switch else "not_public"
        else:
            intended_tier = 1
            route = "public"
            classifier_reason = "public_markers_present"

        # Trace-side fingerprints — hash and length are zero-PII summaries
        # of the *redacted* text, so they never expose original values.
        redacted_text = ctx.redacted_text if scan_result.detected else user_text
        prompt_hash = hashlib.sha256(redacted_text.encode("utf-8")).hexdigest()[:16]
        prompt_chars = len(user_text)

        meta = {
            "intended_tier": intended_tier,
            "actual_tier": 1,  # M1: always tier 1 after redaction
            "route": route,
            "pii_clean": pii_clean,
            "redacted_fields": redacted_fields,
            "redacted_fields_count": len(redacted_fields),
            "classifier_reason": classifier_reason,
            "prompt_hash": prompt_hash,
            "prompt_chars": prompt_chars,
            "scan_error": False,
            # Original values from the input PII — used by the output-side scan
            # to distinguish a legitimate placeholder restoration from a real
            # output leak. The model itself only ever sees the redacted form,
            # so in practice this set is mostly defensive.
            "input_pii_values": frozenset(ctx.reverse_map.values()),
        }
        return active_messages, meta

    # ------------------------------------------------------------------
    # Output-side PII scan (2026-05-15 edge-case hardening)
    # ------------------------------------------------------------------

    def _scan_output(
        self, text: str, allowed_values: frozenset[str]
    ) -> tuple[str, list[str]]:
        """Redact PII detected in *model output*.

        The model only ever sees redacted input, so any IBAN/CLABE/account-
        shaped string in its output is one of:
          1. A placeholder token like ``{/IBAN_CODE_1/}`` — never matches a PII
             pattern (the regex needs a real country code + length), so
             ignored automatically.
          2. A value the model hallucinated or recalled from training data —
             treat as a leak, redact and log.
          3. (Defensive) An echo of an original PII value that somehow round-
             tripped — ``allowed_values`` exempts these from the leak count
             but still redacts them in the output so the user can't read them.

        Returns ``(cleaned_text, leak_types)`` where ``leak_types`` lists
        entity types of *real* leaks (case 2). Case 3 redacts silently.
        """
        result = scan(text)
        if not result.detected:
            return text, []
        leaks: list[str] = []
        cleaned = text
        for entity in sorted(result.entities, key=lambda e: e.start, reverse=True):
            redaction_token = f"[OUTPUT_REDACTED_{entity.entity_type}]"
            cleaned = cleaned[: entity.start] + redaction_token + cleaned[entity.end :]
            if entity.value not in allowed_values:
                leaks.append(entity.entity_type)
        return cleaned, leaks

    def _apply_output_scan(
        self, result: ChatResult, allowed_values: frozenset[str]
    ) -> list[str]:
        """Mutate every generation's text content in ``result`` and return
        the aggregated leak-type list (empty when clean).
        """
        all_leaks: list[str] = []
        for gen in result.generations:
            msg = getattr(gen, "message", None)
            if msg is None or not isinstance(msg.content, str):
                continue
            cleaned, leaks = self._scan_output(msg.content, allowed_values)
            if leaks or cleaned != msg.content:
                msg.content = cleaned
                gen.text = cleaned
            all_leaks.extend(leaks)
        return all_leaks

    def _scan_error_meta(self, exc: BaseException, user_text: str) -> dict[str, Any]:
        """Trace metadata for a scanner failure — used by fail-closed paths.

        ``actual_tier`` is ``None`` because no upstream call is made: the request
        is aborted before any text leaves this process. The trace remains the only
        record that the request happened, which is why the field is mandatory.
        """
        return {
            "intended_tier": 2,
            "actual_tier": None,
            "route": "scan_error",
            "pii_clean": False,
            "redacted_fields": [],
            "redacted_fields_count": 0,
            "classifier_reason": f"scan_error:{type(exc).__name__}",
            "prompt_hash": "",
            "prompt_chars": len(user_text),
            "scan_error": True,
        }

    # ------------------------------------------------------------------
    # _generate
    # ------------------------------------------------------------------

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        ts_start = datetime.now(timezone.utc).isoformat()

        try:
            active_messages, meta = self._route(messages)
        except Exception as exc:
            err_meta = self._scan_error_meta(exc, _human_text(messages))
            self._write_trace(trace_id, span_id, ts_start, err_meta)
            raise

        import time
        t0 = time.perf_counter()
        result: ChatResult = self._tier1._generate(
            active_messages, stop=stop, run_manager=run_manager, **kwargs
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        output_leaks = self._apply_output_scan(result, meta["input_pii_values"])

        usage = result.llm_output or {}
        self._write_trace(trace_id, span_id, ts_start, meta,
                          total_latency_ms=round(elapsed_ms, 1),
                          input_tokens=usage.get("input_tokens", 0),
                          output_tokens=usage.get("output_tokens", 0),
                          output_leaks=output_leaks)
        return result

    # ------------------------------------------------------------------
    # _stream
    # ------------------------------------------------------------------

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        ts_start = datetime.now(timezone.utc).isoformat()

        try:
            active_messages, meta = self._route(messages)
        except Exception as exc:
            err_meta = self._scan_error_meta(exc, _human_text(messages))
            self._write_trace(trace_id, span_id, ts_start, err_meta)
            raise

        import time
        t0 = time.perf_counter()
        # Streaming output cannot be rewritten after the fact (chunks have
        # already been forwarded to the user), so the leak detection here is
        # post-mortem logging only. The trace flags ``output_leaks`` so
        # operations can investigate; no in-flight mitigation.
        buffer_parts: list[str] = []
        for chunk in self._tier1._stream(active_messages, stop=stop, run_manager=run_manager, **kwargs):
            content = getattr(chunk.message, "content", None) if getattr(chunk, "message", None) else None
            if isinstance(content, str):
                buffer_parts.append(content)
            yield chunk
        elapsed_ms = (time.perf_counter() - t0) * 1000

        _, output_leaks = self._scan_output("".join(buffer_parts), meta["input_pii_values"])
        self._write_trace(trace_id, span_id, ts_start, meta,
                          total_latency_ms=round(elapsed_ms, 1),
                          output_leaks=output_leaks)

    # ------------------------------------------------------------------
    # _agenerate
    # ------------------------------------------------------------------

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        ts_start = datetime.now(timezone.utc).isoformat()

        try:
            active_messages, meta = self._route(messages)
        except Exception as exc:
            err_meta = self._scan_error_meta(exc, _human_text(messages))
            self._write_trace(trace_id, span_id, ts_start, err_meta)
            raise

        import time
        t0 = time.perf_counter()
        result: ChatResult = await self._tier1._agenerate(
            active_messages, stop=stop, run_manager=run_manager, **kwargs
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        output_leaks = self._apply_output_scan(result, meta["input_pii_values"])

        usage = result.llm_output or {}
        self._write_trace(trace_id, span_id, ts_start, meta,
                          total_latency_ms=round(elapsed_ms, 1),
                          input_tokens=usage.get("input_tokens", 0),
                          output_tokens=usage.get("output_tokens", 0),
                          output_leaks=output_leaks)
        return result

    # ------------------------------------------------------------------
    # Trace
    # ------------------------------------------------------------------

    def _write_trace(
        self,
        trace_id: str,
        span_id: str,
        ts_start: str,
        meta: dict[str, Any],
        *,
        total_latency_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        output_leaks: Optional[list[str]] = None,
    ) -> None:
        output_leaks = output_leaks or []
        _append_trace({
            "trace_id": trace_id,
            "span_id": span_id,
            "ts_start": ts_start,
            "model_id": self.tier1_model,
            "provider": "deepseek_native",
            "tier": meta["actual_tier"],
            "intended_tier": meta["intended_tier"],
            "route_decision": meta["route"],
            "escalated_from": None,
            "classifier_reason": meta["classifier_reason"],
            "pii_clean": meta["pii_clean"],
            "redacted_fields": meta["redacted_fields"],
            "redacted_fields_count": meta["redacted_fields_count"],
            "scan_error": meta.get("scan_error", False),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": 0,
            "ttft_ms": 0,
            "tpot_ms": 0,
            "total_latency_ms": total_latency_ms,
            "cost_usd": 0.0,
            "prompt_hash": meta["prompt_hash"],
            "prompt_chars": meta["prompt_chars"],
            "tool_calls": [],
            "escalation_signal": None,
            "output_leak": bool(output_leaks),
            "output_leak_types": output_leaks,
        })
