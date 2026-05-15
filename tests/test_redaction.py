"""Tests for deep_devops.router.redaction — reverse map (Cap 10 Fig 10-3)."""
from deep_devops.router.pii_scanner import scan
from deep_devops.router.redaction import RedactionContext, redact


# ---------------------------------------------------------------------------
# redact() — building the context
# ---------------------------------------------------------------------------

def test_clean_text_returns_unchanged() -> None:
    result = scan("how do I sort a list in Python?")
    ctx = redact("how do I sort a list in Python?", result)
    assert ctx.redacted_text == "how do I sort a list in Python?"
    assert ctx.reverse_map == {}


def test_single_secret_is_redacted() -> None:
    text = "my key is AKIAIOSFODNN7EXAMPLE thanks"
    ctx = redact(text, scan(text))
    assert "AKIAIOSFODNN7EXAMPLE" not in ctx.redacted_text
    assert "{/AWS_ACCESS_KEY_1/}" in ctx.redacted_text


def test_single_email_is_redacted() -> None:
    text = "contact me at user@company.com please"
    ctx = redact(text, scan(text))
    assert "user@company.com" not in ctx.redacted_text
    assert "{/EMAIL_1/}" in ctx.redacted_text


def test_multiple_same_type_get_unique_placeholders() -> None:
    text = "from alice@corp.com to bob@corp.com"
    ctx = redact(text, scan(text))
    assert "{/EMAIL_1/}" in ctx.redacted_text
    assert "{/EMAIL_2/}" in ctx.redacted_text
    assert ctx.reverse_map["{/EMAIL_1/}"] != ctx.reverse_map["{/EMAIL_2/}"]


def test_mixed_entity_types_all_redacted() -> None:
    text = "key AKIAIOSFODNN7EXAMPLE and ip 192.168.1.1"
    ctx = redact(text, scan(text))
    assert "AKIAIOSFODNN7EXAMPLE" not in ctx.redacted_text
    assert "192.168.1.1" not in ctx.redacted_text
    assert "{/AWS_ACCESS_KEY_1/}" in ctx.redacted_text
    assert "{/PRIVATE_IP_1/}" in ctx.redacted_text


# ---------------------------------------------------------------------------
# restore() — lossless round-trip
# ---------------------------------------------------------------------------

def test_restore_single_entity() -> None:
    text = "my key is AKIAIOSFODNN7EXAMPLE thanks"
    ctx = redact(text, scan(text))
    assert ctx.restore(ctx.redacted_text) == text


def test_restore_email_round_trip() -> None:
    text = "send to user@company.com ok"
    ctx = redact(text, scan(text))
    assert ctx.restore(ctx.redacted_text) == text


def test_restore_multiple_same_type() -> None:
    text = "from alice@corp.com to bob@corp.com"
    ctx = redact(text, scan(text))
    restored = ctx.restore(ctx.redacted_text)
    assert "alice@corp.com" in restored
    assert "bob@corp.com" in restored


def test_restore_mixed_types() -> None:
    text = "key AKIAIOSFODNN7EXAMPLE ip 192.168.1.1 mail user@corp.com"
    ctx = redact(text, scan(text))
    assert ctx.restore(ctx.redacted_text) == text


def test_restore_noop_when_no_entities() -> None:
    text = "just a normal question"
    ctx = redact(text, scan(text))
    assert ctx.restore(text) == text


def test_restore_partial_text() -> None:
    """restore() works on any string, not just redacted_text."""
    text = "key AKIAIOSFODNN7EXAMPLE"
    ctx = redact(text, scan(text))
    arbitrary = "found {/AWS_ACCESS_KEY_1/} in logs"
    restored = ctx.restore(arbitrary)
    assert "AKIAIOSFODNN7EXAMPLE" in restored
    assert "{/AWS_ACCESS_KEY_1/}" not in restored


def test_redacted_text_preserves_surrounding_content() -> None:
    text = "before AKIAIOSFODNN7EXAMPLE after"
    ctx = redact(text, scan(text))
    assert ctx.redacted_text.startswith("before ")
    assert ctx.redacted_text.endswith(" after")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_string() -> None:
    ctx = redact("", scan(""))
    assert ctx.redacted_text == ""
    assert ctx.restore("") == ""


def test_entity_at_start() -> None:
    text = "AKIAIOSFODNN7EXAMPLE is my key"
    ctx = redact(text, scan(text))
    assert ctx.redacted_text.startswith("{/AWS_ACCESS_KEY_1/}")
    assert ctx.restore(ctx.redacted_text) == text


def test_entity_at_end() -> None:
    text = "my key is AKIAIOSFODNN7EXAMPLE"
    ctx = redact(text, scan(text))
    assert ctx.redacted_text.endswith("{/AWS_ACCESS_KEY_1/}")
    assert ctx.restore(ctx.redacted_text) == text
