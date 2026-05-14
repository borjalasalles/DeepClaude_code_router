"""
PII scanner tests — parametrized over evals/pii_scanner/fixtures.jsonl.

Each fixture asserts:
  1. detected matches expected_detected
  2. every type in expected_types appears in the scan result

Run: uv run pytest tests/test_pii_scanner.py -v
"""
import json
from pathlib import Path

import pytest

from deep_devops.router.pii_scanner import scan, ScanResult

FIXTURES_PATH = Path(__file__).parent.parent / "evals" / "pii_scanner" / "fixtures.jsonl"


def load_fixtures() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURES_PATH.read_text().splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Parametrized fixture tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", load_fixtures(), ids=lambda c: c["id"])
def test_scan_fixtures(case: dict) -> None:
    result = scan(case["input"])

    assert result.detected == case["expected_detected"], (
        f"[{case['id']}] detected={result.detected} "
        f"but expected {case['expected_detected']}.\n"
        f"  input:   {case['input'][:120]!r}\n"
        f"  found:   {result.entity_types()}\n"
        f"  notes:   {case['notes']}"
    )

    for expected_type in case.get("expected_types", []):
        assert expected_type in result.entity_types(), (
            f"[{case['id']}] expected entity type {expected_type!r} "
            f"not found in {result.entity_types()}.\n"
            f"  input: {case['input'][:120]!r}"
        )


# ---------------------------------------------------------------------------
# Redaction unit tests
# ---------------------------------------------------------------------------

def test_redact_aws_key() -> None:
    text = "My key is AKIAIOSFODNN7EXAMPLE please keep safe"
    result = scan(text)
    redacted = result.redacted(text)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[AWS_ACCESS_KEY]" in redacted


def test_redact_email() -> None:
    text = "Contact admin@company.com for support"
    result = scan(text)
    redacted = result.redacted(text)
    assert "admin@company.com" not in redacted
    assert "[EMAIL]" in redacted


def test_redact_multiple_entities() -> None:
    text = "User alice@company.com logged in from 10.0.1.50"
    result = scan(text)
    assert result.detected
    redacted = result.redacted(text)
    assert "alice@company.com" not in redacted
    assert "10.0.1.50" not in redacted


def test_redact_preserves_surrounding_text() -> None:
    text = "prefix AKIAIOSFODNN7EXAMPLE suffix"
    result = scan(text)
    redacted = result.redacted(text)
    assert redacted.startswith("prefix ")
    assert redacted.endswith(" suffix")


def test_redact_no_entities_returns_original() -> None:
    text = "How do I sort a list in Python?"
    result = scan(text)
    assert not result.detected
    assert result.redacted(text) == text


def test_redact_overlapping_offsets_stable() -> None:
    # JWT also triggers BEARER_TOKEN; both entities may overlap.
    # redacted() must not produce corrupted text.
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4eXoifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk"
    text = f"Authorization: Bearer {jwt}"
    result = scan(text)
    assert result.detected
    redacted = result.redacted(text)
    # The raw JWT value must not appear in the output.
    assert jwt not in redacted


# ---------------------------------------------------------------------------
# entity_types() helper
# ---------------------------------------------------------------------------

def test_entity_types_returns_all() -> None:
    text = "key=AKIAIOSFODNN7EXAMPLE and user@company.com from 10.0.0.1"
    result = scan(text)
    types = result.entity_types()
    assert "AWS_ACCESS_KEY" in types
    assert "EMAIL" in types
    assert "PRIVATE_IP" in types
