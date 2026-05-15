"""Tests for RouterChatModel routing logic — no real API calls."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from deep_devops.router.model import (
    RouterChatModel,
    _human_text,
    _is_public,
    _messages_to_text,
    _redact_messages,
)
from deep_devops.router.pii_scanner import scan
from deep_devops.router.redaction import redact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_router(**kwargs: object) -> RouterChatModel:
    with patch("deep_devops.router.model.build_tier1_client") as mock_build:
        mock_build.return_value = MagicMock()
        router = RouterChatModel(**kwargs)
    return router


def _fake_result(content: str = "ok") -> ChatResult:
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


# ---------------------------------------------------------------------------
# _human_text / _messages_to_text — only HumanMessages scanned
# ---------------------------------------------------------------------------

def test_human_text_ignores_system_prompt() -> None:
    msgs = [
        SystemMessage(content="You are an assistant. Read .env files with read_file."),
        HumanMessage(content="hello"),
    ]
    assert _human_text(msgs) == "hello"


def test_human_text_ignores_ai_messages() -> None:
    msgs = [HumanMessage(content="hi"), AIMessage(content="there")]
    assert _human_text(msgs) == "hi"


def test_messages_to_text_is_alias() -> None:
    msgs = [HumanMessage(content="hello")]
    assert _messages_to_text(msgs) == _human_text(msgs)


# ---------------------------------------------------------------------------
# _is_public — whitelist semantics
# ---------------------------------------------------------------------------

def test_is_public_generic_question() -> None:
    assert _is_public("how do I sort a list in Python?") is True


def test_is_public_rejects_internal_tld() -> None:
    assert _is_public("connect to db.internal") is False


def test_is_public_rejects_corp_tld() -> None:
    assert _is_public("host is myserver.corp") is False


def test_is_public_rejects_env_path() -> None:
    assert _is_public("read from .env file") is False


def test_is_public_rejects_secrets_path() -> None:
    assert _is_public("see /secrets/token") is False


# ---------------------------------------------------------------------------
# _redact_messages — rebuilds only HumanMessages
# ---------------------------------------------------------------------------

def test_redact_messages_replaces_human_content() -> None:
    text = "my email is user@company.com"
    ctx = redact(text, scan(text))
    msgs = [HumanMessage(content=text)]
    out = _redact_messages(msgs, ctx)
    assert isinstance(out[0], HumanMessage)
    assert "user@company.com" not in out[0].content
    assert "{/EMAIL_1/}" in out[0].content


def test_redact_messages_keeps_system_untouched() -> None:
    sys_text = "You are an assistant. user@system.com is internal."
    text = "my email is user@company.com"
    ctx = redact(text, scan(text))
    msgs = [SystemMessage(content=sys_text), HumanMessage(content=text)]
    out = _redact_messages(msgs, ctx)
    assert out[0].content == sys_text  # system prompt unchanged
    assert "{/EMAIL_1/}" in out[1].content


def test_redact_messages_noop_when_clean() -> None:
    text = "sort a list"
    ctx = redact(text, scan(text))
    msgs = [HumanMessage(content=text)]
    out = _redact_messages(msgs, ctx)
    assert out is msgs  # same object, no copy


# ---------------------------------------------------------------------------
# RouterChatModel._route — classifies but never blocks
# ---------------------------------------------------------------------------

def test_route_system_prompt_with_env_does_not_trigger_pii(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """System prompt mentioning .env must not classify as PII."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    router = _make_router()
    msgs = [
        SystemMessage(content="You can read_file, write_file, edit .env files."),
        HumanMessage(content="hola"),
    ]
    active, meta = router._route(msgs)
    assert meta["pii_clean"] is True
    assert meta["route"] == "public"


def test_route_email_in_user_message_redacts_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    router = _make_router()
    msgs = [HumanMessage(content="my email is user@company.com")]
    active, meta = router._route(msgs)
    assert meta["pii_clean"] is False
    assert "EMAIL" in meta["classifier_reason"]
    assert meta["actual_tier"] == 1  # still routes to tier 1 after redaction
    assert "user@company.com" not in active[0].content
    assert "{/EMAIL_1/}" in active[0].content


def test_route_aws_key_redacts_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    router = _make_router()
    msgs = [HumanMessage(content="my key AKIAIOSFODNN7EXAMPLE is leaking")]
    active, meta = router._route(msgs)
    assert meta["pii_clean"] is False
    assert meta["actual_tier"] == 1
    assert "AKIAIOSFODNN7EXAMPLE" not in active[0].content


def test_route_clean_public_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    monkeypatch.delenv("DEEP_DEVOPS_DISABLE_PUBLIC_TIER", raising=False)
    router = _make_router()
    msgs = [HumanMessage(content="how do I sort a list in Python?")]
    _, meta = router._route(msgs)
    assert meta["pii_clean"] is True
    assert meta["route"] == "public"
    assert meta["actual_tier"] == 1
    assert meta["intended_tier"] == 1


def test_route_kill_switch_marks_intended_tier2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    monkeypatch.setenv("DEEP_DEVOPS_DISABLE_PUBLIC_TIER", "1")
    router = _make_router()
    msgs = [HumanMessage(content="how do I sort a list?")]
    _, meta = router._route(msgs)
    assert meta["intended_tier"] == 2
    assert meta["actual_tier"] == 1  # still goes to tier 1 for M1


# ---------------------------------------------------------------------------
# Full _generate — never raises for PII
# ---------------------------------------------------------------------------

def test_generate_with_pii_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    router = _make_router()
    router._tier1._generate = MagicMock(return_value=_fake_result("ok"))
    with patch("deep_devops.router.model._append_trace"):
        result = router._generate([HumanMessage(content="my email is user@company.com")])
    assert result.generations[0].message.content == "ok"
    router._tier1._generate.assert_called_once()


def test_generate_clean_query(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    monkeypatch.delenv("DEEP_DEVOPS_DISABLE_PUBLIC_TIER", raising=False)
    router = _make_router()
    router._tier1._generate = MagicMock(return_value=_fake_result("sorted"))
    with patch("deep_devops.router.model._append_trace"):
        result = router._generate([HumanMessage(content="how do I sort a list in Python?")])
    assert result.generations[0].message.content == "sorted"


def test_trace_pii_flagged_in_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    router = _make_router()
    router._tier1._generate = MagicMock(return_value=_fake_result())
    captured: list[dict] = []
    with patch("deep_devops.router.model._append_trace", side_effect=captured.append):
        router._generate([HumanMessage(content="contact me at user@company.com")])
    assert len(captured) == 1
    trace = captured[0]
    assert trace["pii_clean"] is False
    assert trace["tier"] == 1
    assert "EMAIL" in trace["redacted_fields"]


def test_trace_written_on_clean_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-" + "x" * 20)
    monkeypatch.delenv("DEEP_DEVOPS_DISABLE_PUBLIC_TIER", raising=False)
    router = _make_router()
    router._tier1._generate = MagicMock(return_value=_fake_result())
    captured: list[dict] = []
    with patch("deep_devops.router.model._append_trace", side_effect=captured.append):
        router._generate([HumanMessage(content="how do I sort a list in Python?")])
    assert captured[0]["pii_clean"] is True
    assert captured[0]["route_decision"] == "public"
