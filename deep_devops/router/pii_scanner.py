"""
PII and secret scanner — deterministic, regex-based, zero LLM calls.

Cap 10 p.451-452: input guardrails run before the model sees any data.
Cap 10 Fig 10-3: detected entities become placeholders; redacted text can be
sent to a lower tier than the raw text would allow.

Design constraints (from design.md §4.2):
- Rules only. No LLM-as-judge here (Cap 10 p.457 + Cap 3 p.144).
- Must be synchronous and fast — called in the hot path of _generate().
- False negatives (missed leak) are worse than false positives (extra redaction).

Architecture:
  _Pattern has two optional post-filters applied after a regex match:
  - validator(value) -> bool   : checksum check (Luhn, mod-97, NIF mod-23)
  - context_words              : require ≥1 keyword within ±100 chars of the match
  Both default to None (no extra filtering).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, NamedTuple


# ---------------------------------------------------------------------------
# Entity types
# ---------------------------------------------------------------------------

class EntityType:
    # Cloud / API credentials
    AWS_ACCESS_KEY  = "AWS_ACCESS_KEY"
    SECRET_KEY      = "SECRET_KEY"       # sk-* — OpenAI, Anthropic, generic
    GITHUB_TOKEN    = "GITHUB_TOKEN"
    STRIPE_KEY      = "STRIPE_KEY"
    SLACK_TOKEN     = "SLACK_TOKEN"
    TELEGRAM_TOKEN  = "TELEGRAM_TOKEN"
    GCP_API_KEY     = "GCP_API_KEY"
    # Auth tokens
    JWT_TOKEN       = "JWT_TOKEN"
    BEARER_TOKEN    = "BEARER_TOKEN"
    PEM_KEY         = "PEM_KEY"
    # Infra / DB
    DATABASE_URL    = "DATABASE_URL"
    SWIFT_CODE      = "SWIFT_CODE"
    CREDIT_CARD     = "CREDIT_CARD"
    IBAN_CODE       = "IBAN_CODE"
    # PII
    EMAIL           = "EMAIL"
    PHONE           = "PHONE"
    PASSWORD_FIELD  = "PASSWORD_FIELD"
    ES_NIF          = "ES_NIF"           # Spanish DNI
    ES_NIE          = "ES_NIE"           # Spanish NIE (foreigner ID)
    # Network / infra markers
    PRIVATE_IP      = "PRIVATE_IP"
    INTERNAL_HOST   = "INTERNAL_HOST"
    SECRET_PATH     = "SECRET_PATH"


# ---------------------------------------------------------------------------
# Validators (pure Python, no external deps)
# ---------------------------------------------------------------------------

def _luhn_check(value: str) -> bool:
    """Luhn algorithm — returns True if the digit string passes (credit cards)."""
    digits = [int(c) for c in value if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iban_mod97(value: str) -> bool:
    """ISO 13616 IBAN mod-97 check."""
    s = value.strip().replace(" ", "").upper()
    if len(s) < 5:
        return False
    rearranged = s[4:] + s[:4]
    number_str = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    try:
        return int(number_str) % 97 == 1
    except ValueError:
        return False


_NIF_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"


def _nif_check(value: str) -> bool:
    """Spanish NIF/DNI mod-23 checksum. Also handles NIE (X/Y/Z prefix)."""
    value = value.upper().strip()
    if len(value) != 9:
        return False
    letter = value[-1]
    digits_part = value[:-1]
    if digits_part[0] in "XYZ":
        digits_part = str("XYZ".index(digits_part[0])) + digits_part[1:]
    try:
        return _NIF_LETTERS[int(digits_part) % 23] == letter
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# Pattern registry
# ---------------------------------------------------------------------------

class _Pattern(NamedTuple):
    entity_type: str
    pattern: re.Pattern
    placeholder: str
    validator: Callable[[str], bool] | None = None
    context_words: frozenset[str] | None = None


_PATTERNS: list[_Pattern] = [

    # ── Cloud credentials ────────────────────────────────────────────────────

    _Pattern(
        EntityType.AWS_ACCESS_KEY,
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[AWS_ACCESS_KEY]",
    ),

    # sk-* keys: OpenAI (sk-..., sk-proj-...), Anthropic (sk-ant-...), generic.
    # Requires 20+ chars after "sk-" (hyphens allowed for multi-segment formats).
    _Pattern(
        EntityType.SECRET_KEY,
        re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9\-]{19,}\b"),
        "[SECRET_KEY]",
    ),

    # GitHub tokens: ghp_ user, ghs_ server, gho_ OAuth, ghr_ refresh,
    # ghu_ user-to-server, ghb_ business — plus long-form github_pat_.
    # FIX A1: added 'r' (refresh) and 'b' (business) to the prefix group.
    _Pattern(
        EntityType.GITHUB_TOKEN,
        re.compile(r"\b(?:gh[psomurb]|github_pat)_[A-Za-z0-9_]{36,}\b"),
        "[GITHUB_TOKEN]",
    ),

    # Stripe live and test secret keys (publishable pk_* keys are not flagged).
    _Pattern(
        EntityType.STRIPE_KEY,
        re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b"),
        "[STRIPE_KEY]",
    ),

    # Slack: xoxb- bot, xoxa- legacy, xoxp- user, xoxs- app, xoxr- refresh.
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

    # Google Cloud Platform API key: AIza + 35 alphanumeric/dash/underscore chars.
    _Pattern(
        EntityType.GCP_API_KEY,
        re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
        "[GCP_API_KEY]",
    ),

    # ── Auth tokens / keys ───────────────────────────────────────────────────

    # JWTs always start with eyJ (base64url of '{"').
    # FIX A2: third segment allows +/= (standard base64 in signature),
    # and is optional to catch alg:none JWTs (no signature).
    _Pattern(
        EntityType.JWT_TOKEN,
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]+"
            r"\.[A-Za-z0-9_\-]+"
            r"(?:\.[A-Za-z0-9_\-+/=]*)?"
        ),
        "[JWT_TOKEN]",
    ),

    # Bearer token: "Bearer " followed by 20+ chars.
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

    # ── Infra / DB ───────────────────────────────────────────────────────────

    # DB URLs with embedded passwords: proto://user:pass@host.
    _Pattern(
        EntityType.DATABASE_URL,
        re.compile(
            r"(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)"
            r":\/\/[^:\s]+:[^@\s]+@"
        ),
        "[DATABASE_URL]",
    ),

    # SWIFT / BIC code: 8 or 11 alphanumeric chars (BANK + CC + LOC + [branch]).
    # Context required — the pattern alone is too broad (any 8-char uppercase string).
    _Pattern(
        EntityType.SWIFT_CODE,
        re.compile(r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b"),
        "[SWIFT_CODE]",
        context_words=frozenset({
            "swift", "bic", "iban", "wire", "transfer", "transferencia",
            "banco", "bank", "payment", "pago", "cuenta",
        }),
    ),

    # Credit card: Visa (13/16), Mastercard (16), Amex (15), Diners (14),
    # Discover (16). Luhn post-filter eliminates virtually all false positives.
    _Pattern(
        EntityType.CREDIT_CARD,
        re.compile(
            r"\b(?:"
            r"4[0-9]{12}(?:[0-9]{3})?"                   # Visa 13 or 16
            r"|[25][0-9]{14}"                             # Mastercard / Maestro 16
            r"|3[47][0-9]{13}"                            # Amex 15
            r"|3(?:0[0-5]|[68][0-9])[0-9]{11}"           # Diners 14
            r"|6(?:011|5[0-9]{2})[0-9]{12}"              # Discover 16
            r")\b"
        ),
        "[CREDIT_CARD]",
        validator=_luhn_check,
    ),

    # Spanish IBAN: ES + 2 check digits + 20 digits (bank+branch+control+account).
    # mod-97 post-filter; pattern is already specific enough without context_words.
    _Pattern(
        EntityType.IBAN_CODE,
        re.compile(r"\bES\d{22}\b"),
        "[IBAN_CODE]",
        validator=_iban_mod97,
    ),

    # ── PII ──────────────────────────────────────────────────────────────────

    # Emails: exclude RFC 2606 reserved domains (example.com/org/net).
    _Pattern(
        EntityType.EMAIL,
        re.compile(
            r"\b[a-zA-Z0-9._%+\-]+@"
            r"(?!example\.(?:com|org|net)\b)"
            r"[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"
        ),
        "[EMAIL]",
    ),

    # Phone numbers — three sub-patterns:
    # 1. International prefix (+XX …): requires digits after prefix to look phone-like.
    # 2. Formatted 3+3+4 (US/ES): e.g. 612-345-678 or 415.555.1234.
    # 3. Bare 9 digits (Spanish mobile): lookahead/lookbehind prevents matching
    #    inside longer digit strings, dates (20230115) and slashed paths.
    # FIX A3: added negative lookarounds to bare-9-digit branch.
    _Pattern(
        EntityType.PHONE,
        re.compile(
            r"(?:"
            r"\+\d{1,3}[\s\-.]?\(?\d{2,4}\)?[\s\-.]?\d{2,4}[\s\-.]?\d{2,6}"
            r"|\b\d{3}[\s\-.]\d{3}[\s\-.]\d{4}\b"
            r"|(?<![0-9/\-])\b\d{9}\b(?![0-9/\-])"
            r")"
        ),
        "[PHONE]",
    ),

    # Password field assignments (label required — raw passwords are undetectable).
    _Pattern(
        EntityType.PASSWORD_FIELD,
        re.compile(
            r"(?:password|contraseña|passwd|pwd|pass)\s*[=:]\s*\S+",
            re.IGNORECASE,
        ),
        "[PASSWORD_FIELD]",
    ),

    # Spanish DNI — 8 digits + checksum letter. mod-23 validator rejects FPs.
    _Pattern(
        EntityType.ES_NIF,
        re.compile(r"\b\d{8}[TRWAGMYFPDXBNJZSQVHLCKE]\b"),
        "[ES_NIF]",
        validator=_nif_check,
    ),

    # Spanish NIE — X/Y/Z + 7 digits + checksum letter.
    _Pattern(
        EntityType.ES_NIE,
        re.compile(r"\b[XYZ]\d{7}[TRWAGMYFPDXBNJZSQVHLCKE]\b"),
        "[ES_NIE]",
        validator=_nif_check,
    ),

    # ── Internal / infra markers (tier-1 blockers) ───────────────────────────

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

    _Pattern(
        EntityType.INTERNAL_HOST,
        re.compile(r"\b\w[\w\-]*\.(?:internal|corp|lan)\b", re.IGNORECASE),
        "[INTERNAL_HOST]",
    ),

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
        """Return text with entities replaced by their type placeholders.

        Applied right-to-left so earlier offsets stay valid.
        For numbered/typed placeholders use redaction.redact() instead.
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

    For each pattern:
    1. Find all regex matches in O(n) time.
    2. If the pattern has a validator, discard matches that fail the checksum.
    3. If the pattern has context_words, discard matches where none of those
       words appear within ±100 characters.

    Returns a ScanResult with every surviving entity and its byte offset, so
    the caller (redaction.py) can substitute placeholders in place.
    """
    entities: list[DetectedEntity] = []
    text_lower = text.lower()

    for p in _PATTERNS:
        for m in p.pattern.finditer(text):
            value = m.group()

            # Checksum post-filter
            if p.validator is not None and not p.validator(value):
                continue

            # Context-keyword gate (±100 chars)
            if p.context_words is not None:
                win_start = max(0, m.start() - 100)
                win_end = min(len(text), m.end() + 100)
                window = text_lower[win_start:win_end]
                if not any(kw in window for kw in p.context_words):
                    continue

            entities.append(DetectedEntity(
                entity_type=p.entity_type,
                value=value,
                start=m.start(),
                end=m.end(),
                placeholder=p.placeholder,
            ))

    entities.sort(key=lambda e: e.start)
    return ScanResult(detected=bool(entities), entities=entities)
