"""
PII and secret scanner — deterministic, regex-based, zero LLM calls.

Cap 10 p.451-452: input guardrails run before the model sees any data.
Cap 10 Fig 10-3: detected entities become placeholders; redacted text can be
sent to a lower tier than the raw text would allow.

Design constraints (from design.md §4.2):
- Rules only. No LLM-as-judge here (Cap 10 p.457 + Cap 3 p.144).
- Must be synchronous and fast — called in the hot path of _generate().
- False negatives (missed leak) are worse than false positives (extra redaction).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------

class EntityType:
    AWS_ACCESS_KEY = "AWS_ACCESS_KEY"
    SECRET_KEY     = "SECRET_KEY"      # sk-* — OpenAI, Anthropic, generic
    GITHUB_TOKEN   = "GITHUB_TOKEN"
    STRIPE_KEY     = "STRIPE_KEY"
    SLACK_TOKEN    = "SLACK_TOKEN"
    TELEGRAM_TOKEN = "TELEGRAM_TOKEN"
    JWT_TOKEN      = "JWT_TOKEN"
    BEARER_TOKEN   = "BEARER_TOKEN"
    PEM_KEY        = "PEM_KEY"
    DATABASE_URL   = "DATABASE_URL"
    EMAIL          = "EMAIL"
    PRIVATE_IP     = "PRIVATE_IP"
    INTERNAL_HOST  = "INTERNAL_HOST"
    SECRET_PATH    = "SECRET_PATH"


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

class _Pattern(NamedTuple):
    entity_type: str
    pattern: re.Pattern
    placeholder: str


_PATTERNS: list[_Pattern] = [
    # -- Secrets: cloud credentials ------------------------------------------

    _Pattern(
        EntityType.AWS_ACCESS_KEY,
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[AWS_ACCESS_KEY]",
    ),

    # sk-* keys: OpenAI (sk-..., sk-proj-...), Anthropic (sk-ant-...), others.
    # Requires 20+ chars after "sk-" (hyphens allowed for multi-segment formats).
    _Pattern(
        EntityType.SECRET_KEY,
        re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9\-]{19,}\b"),
        "[SECRET_KEY]",
    ),

    _Pattern(
        EntityType.GITHUB_TOKEN,
        re.compile(r"\b(?:gh[psomu]|github_pat)_[A-Za-z0-9_]{36,}\b"),
        "[GITHUB_TOKEN]",
    ),

    # Stripe live and test secret keys (publishable pk_* keys are not flagged).
    _Pattern(
        EntityType.STRIPE_KEY,
        re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b"),
        "[STRIPE_KEY]",
    ),

    # xoxb- bot, xoxa- legacy, xoxp- user, xoxs- app, xoxr- refresh.
    # xapp- is the newer app-level token format (different prefix entirely).
    _Pattern(
        EntityType.SLACK_TOKEN,
        re.compile(r"\b(?:xox[bapsr]-|xapp-)[A-Za-z0-9\-]{10,}\b"),
        "[SLACK_TOKEN]",
    ),

    # Telegram bot token: 8-10 digit bot ID + colon + 35-char token.
    _Pattern(
        EntityType.TELEGRAM_TOKEN,
        re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b"),
        "[TELEGRAM_TOKEN]",
    ),

    # -- Secrets: tokens and keys --------------------------------------------

    # JWTs always start with eyJ (base64url of {"...).
    _Pattern(
        EntityType.JWT_TOKEN,
        re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
        "[JWT_TOKEN]",
    ),

    # Bearer token: "Bearer " followed by 20+ chars (catches both JWT and opaque).
    # Checked after JWT so JWT entities are also individually recorded.
    _Pattern(
        EntityType.BEARER_TOKEN,
        re.compile(r"[Bb]earer\s+([A-Za-z0-9\-._~+/]{20,}=*)"),
        "[BEARER_TOKEN]",
    ),

    _Pattern(
        EntityType.PEM_KEY,
        re.compile(r"-----BEGIN [A-Z ]+-----"),
        "[PEM_KEY]",
    ),

    # DB URLs with embedded passwords: proto://user:pass@host
    _Pattern(
        EntityType.DATABASE_URL,
        re.compile(
            r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)"
            r":\/\/[^:\s]+:[^@\s]+@"
        ),
        "[DATABASE_URL]",
    ),

    # -- PII -----------------------------------------------------------------

    # Emails: exclude RFC 2606 reserved example.com/org/net placeholder domains.
    _Pattern(
        EntityType.EMAIL,
        re.compile(
            r"\b[a-zA-Z0-9._%+\-]+@"
            r"(?!example\.(?:com|org|net)\b)"
            r"[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
        ),
        "[EMAIL]",
    ),

    # RFC 1918 private IP ranges only (not public IPs).
    _Pattern(
        EntityType.PRIVATE_IP,
        re.compile(
            r"\b(?:"
            r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r")\b"
        ),
        "[PRIVATE_IP]",
    ),

    # -- Internal markers (tier-1 blockers) ----------------------------------

    # Hostnames ending in reserved internal TLDs.
    _Pattern(
        EntityType.INTERNAL_HOST,
        re.compile(r"\b\w[\w\-]*\.(?:internal|corp|lan)\b", re.IGNORECASE),
        "[INTERNAL_HOST]",
    ),

    # File paths that almost always contain secrets.
    _Pattern(
        EntityType.SECRET_PATH,
        re.compile(
            r"(?:"
            r"\/secrets\/"
            r"|\.env\b"
            r"|credentials\.(?:json|yaml|yml|toml)"
            r"|[\w\-]+\.pem\b"
            r"|[\w\-]+\.key\b"
            r")",
            re.IGNORECASE,
        ),
        "[SECRET_PATH]",
    ),
]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DetectedEntity:
    entity_type: str
    value: str
    start: int
    end: int
    placeholder: str


@dataclass
class ScanResult:
    detected: bool
    entities: list[DetectedEntity] = field(default_factory=list)

    def redacted(self, text: str) -> str:
        """Return text with all entities replaced by placeholders.

        Replacements are applied right-to-left so earlier offsets stay valid.
        """
        if not self.entities:
            return text
        for entity in sorted(self.entities, key=lambda e: e.start, reverse=True):
            text = text[: entity.start] + entity.placeholder + text[entity.end :]
        return text

    def entity_types(self) -> list[str]:
        return [e.entity_type for e in self.entities]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan(text: str) -> ScanResult:
    """Scan *text* for PII and secrets.

    Runs all compiled patterns in O(n × patterns) time. No external calls.
    Returns a ScanResult with every detected entity and its offset, so the
    caller (redaction.py) can substitute placeholders in place.
    """
    entities: list[DetectedEntity] = []
    for p in _PATTERNS:
        for m in p.pattern.finditer(text):
            entities.append(
                DetectedEntity(
                    entity_type=p.entity_type,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                    placeholder=p.placeholder,
                )
            )
    # Sort by position for consistent output (redacted() sorts again in reverse).
    entities.sort(key=lambda e: e.start)
    return ScanResult(detected=bool(entities), entities=entities)
