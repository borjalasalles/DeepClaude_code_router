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
    ES_CIF          = "ES_CIF"           # Spanish corporate tax ID
    CLABE           = "CLABE"            # Mexican bank account standard (18 digits)
    ABA_ROUTING     = "ABA_ROUTING"      # US Fedwire/ACH routing number (9 digits)
    US_BANK_ACCOUNT = "US_BANK_ACCOUNT"  # US bank account number (variable length)
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


_IBAN_SEPARATOR_RE = re.compile(r"[\s\-]")

# ISO 13616 IBAN registry — official total length per country code.
# Source: SWIFT IBAN registry (https://www.swift.com/standards/data-standards/iban),
# coverage includes EU/EEA, UK, Switzerland, Latin America, Middle East, North Africa
# and others. The US/Canada are intentionally absent — they use ABA / transit codes.
_IBAN_LENGTHS: dict[str, int] = {
    "AD": 24, "AE": 23, "AL": 28, "AT": 20, "AZ": 28,
    "BA": 20, "BE": 16, "BG": 22, "BH": 22, "BI": 27, "BR": 29, "BY": 28,
    "CH": 21, "CR": 22, "CY": 28, "CZ": 24,
    "DE": 22, "DJ": 27, "DK": 18, "DO": 28,
    "EE": 20, "EG": 29, "ES": 24,
    "FI": 18, "FO": 18, "FR": 27,
    "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27, "GT": 28,
    "HR": 21, "HU": 28,
    "IE": 22, "IL": 23, "IQ": 23, "IR": 26, "IS": 26, "IT": 27,
    "JO": 30,
    "KW": 30, "KZ": 20,
    "LB": 28, "LC": 32, "LI": 21, "LT": 20, "LU": 20, "LV": 21, "LY": 25,
    "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MR": 27, "MT": 31, "MU": 30,
    "NI": 28, "NL": 18, "NO": 15,
    "OM": 23,
    "PK": 24, "PL": 28, "PS": 29, "PT": 25,
    "QA": 29,
    "RO": 24, "RS": 22, "RU": 33,
    "SA": 24, "SC": 31, "SD": 18, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
    "SO": 23, "ST": 25, "SV": 28,
    "TL": 23, "TN": 24, "TR": 26,
    "UA": 29,
    "VA": 22, "VG": 24,
    "XK": 20,
    "YE": 30,
}


def _iban_country_length(value: str) -> bool:
    """Validate IBAN by country-code + total-length (no mod-97 checksum).

    Redundant given the country-aware regex below, but kept as a defensive
    invariant so that any future regex relaxation does not silently widen FPs.

    Design choice (M1.5, after a real leak with a mod-97-invalid IBAN reaching
    DeepSeek): the bank/corp threat model treats any string of the form
    *CC + 2 digits + BBAN* as IBAN-intent — real, mistyped or fictional — and
    redacts it. Dropping the checksum widens recall; the country whitelist +
    exact length keeps precision high enough that random alphanumerics don't
    trip the detector.
    """
    s = _IBAN_SEPARATOR_RE.sub("", value).upper()
    if len(s) < 4:
        return False
    return _IBAN_LENGTHS.get(s[:2]) == len(s)


def _build_iban_regex() -> re.Pattern:
    """Country-aware IBAN regex, one alternation per ISO 13616 country.

    Anchoring the BBAN length per country prevents greedy over-extension into
    surrounding text (e.g. the regex stopping at 'ayer' in '...1234567890 ayer'
    because [A-Z0-9] would otherwise keep consuming letters).
    """
    parts = [
        f"{cc}\\d{{2}}(?:[\\s\\-]*[A-Z0-9]){{{length - 4}}}"
        for cc, length in _IBAN_LENGTHS.items()
    ]
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


_IBAN_REGEX = _build_iban_regex()


def _cif_check(value: str) -> bool:
    """Spanish CIF (corporate tax ID) checksum.

    Format: L NNNNNNN C
      L = entity-class letter ∈ {A,B,C,D,E,F,G,H,J,N,P,Q,R,S,U,V,W}
      N = 7 inner digits
      C = control character (digit, letter, or either, depending on L)

    Algorithm:
      - Sum digits at even positions (2,4,6) as-is.
      - Sum digits at odd positions (1,3,5,7) after doubling and summing digits
        of each product.
      - control_digit = (10 - total mod 10) mod 10.
      - For L ∈ {A,B,E,H} the control must be the digit string.
      - For L ∈ {K,P,Q,R,N,W} the control must be 'JABCDEFGHI'[control_digit].
      - For the rest, either form is accepted.
    """
    v = _IBAN_SEPARATOR_RE.sub("", value).upper()
    if len(v) != 9:
        return False
    letter, digits, control = v[0], v[1:8], v[8]
    if not digits.isdigit():
        return False
    odd_sum = 0
    for d in (int(digits[i]) for i in (0, 2, 4, 6)):
        doubled = d * 2
        odd_sum += doubled // 10 + doubled % 10
    even_sum = sum(int(digits[i]) for i in (1, 3, 5))
    control_digit = (10 - (odd_sum + even_sum) % 10) % 10
    control_letter = "JABCDEFGHI"[control_digit]
    if letter in "ABEH":
        return control == str(control_digit)
    if letter in "KPQRNW":
        return control == control_letter
    return control == str(control_digit) or control == control_letter


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
    # Discover (16). Each variant accepts optional space or dash separators between
    # digit groups (e.g. "4111 1111 1111 1111" and "4111-1111-1111-1111").
    # Luhn post-filter eliminates virtually all false positives.
    # FIX B1: Mastercard was [25][0-9]{14} (15 digits) → now 16 digits.
    # FIX B2: formatted numbers with spaces/dashes now matched.
    _Pattern(
        EntityType.CREDIT_CARD,
        re.compile(
            r"\b(?:"
            r"4\d{3}[ \-]?\d{4}[ \-]?\d{4}[ \-]?\d{4}"        # Visa 16 (plain or grouped)
            r"|4\d{12}"                                           # Visa 13
            r"|[25]\d{3}[ \-]?\d{4}[ \-]?\d{4}[ \-]?\d{4}"     # Mastercard/Maestro 16
            r"|3[47]\d{2}[ \-]?\d{6}[ \-]?\d{5}"                # Amex 15 (4-6-5)
            r"|3(?:0[0-5]|[68]\d)\d[ \-]?\d{6}[ \-]?\d{4}"     # Diners 14 (4-6-4)
            r"|6(?:011|5\d{2})[ \-]?\d{4}[ \-]?\d{4}[ \-]?\d{4}" # Discover 16
            r")\b"
        ),
        "[CREDIT_CARD]",
        validator=_luhn_check,
    ),

    # IBAN (ISO 13616, international): country code + 2 check digits + BBAN.
    # BBAN may contain letters (UK, IE, MT, ...) so the body is [A-Z0-9].
    # FIX M1.5 (post real-world leak):
    #   - Multi-country: any country in the ISO 13616 registry, not just ES.
    #   - Country-aware length: regex anchors BBAN to the exact length per
    #     country so it doesn't over-extend into surrounding letters.
    #   - Irregular grouping: separators allowed between any two BBAN chars
    #     ('ES21 1465 0100 92 1234567890' was the leaking case).
    #   - No mod-97: bank/corp threat model treats even checksum-invalid
    #     IBAN-shaped strings as IBAN-intent (typo of a real IBAN).
    _Pattern(
        EntityType.IBAN_CODE,
        _IBAN_REGEX,
        "[IBAN_CODE]",
        validator=_iban_country_length,
    ),

    # Mexican CLABE (Clave Bancaria Estandarizada): 18 digits, no country prefix.
    # Added in M1.5 after a real leak — a CLABE reached DeepSeek because nothing
    # in the original M1 patterns matched 18-digit raw strings. Context-gated to
    # keep precision: an 18-digit string in an unrelated context (timestamp, ID)
    # is unlikely to also have Mexican-banking keywords nearby.
    _Pattern(
        EntityType.CLABE,
        re.compile(r"\b\d{18}\b"),
        "[CLABE]",
        context_words=frozenset({
            "clabe", "banamex", "banorte", "bbva", "santander",
            "hsbc", "spei", "mexico", "méxico", "mx",
        }),
    ),

    # US ABA routing number: 9 digits identifying a US bank for ACH/Fedwire.
    # The bare-9-digit PHONE pattern catches these by accident; this entry makes
    # the category explicit so traces show what was actually redacted. Both patterns
    # fire on the same span — the redactor emits both placeholders, which is harmless
    # (real value is gone either way).
    _Pattern(
        EntityType.ABA_ROUTING,
        re.compile(r"\b\d{9}\b"),
        "[ABA_ROUTING]",
        context_words=frozenset({
            "aba", "routing", "fedwire", "ach", "us bank", "wire transfer",
            "chase", "wells fargo", "bank of america", "citibank",
        }),
    ),

    # US bank account number: 10-17 digits with strong banking context.
    # Range starts at 10 to avoid double-matching with ABA_ROUTING (9 digits).
    # No structural marker (unlike IBAN's country code), so we rely entirely on
    # nearby keywords. Threat model is bank/corp denial-by-default — accept some
    # false positives on long numerals near banking words.
    _Pattern(
        EntityType.US_BANK_ACCOUNT,
        re.compile(r"\b\d{10,17}\b"),
        "[US_BANK_ACCOUNT]",
        context_words=frozenset({
            "chase", "wells fargo", "bank of america", "citibank", "citi",
            "checking account", "savings account", "account number",
            "account is", "fedwire", "ach", "wire transfer", "wire to",
            "deposit", "routing",
        }),
    ),

    # Spanish CIF: 1 entity-class letter + 7 digits + 1 control char.
    # Optional dash between letter and digits ('B-12345678') is the common
    # visual form. Validator implements the mod-10 algorithm + per-letter
    # rule for whether the control is digit / letter / either.
    _Pattern(
        EntityType.ES_CIF,
        re.compile(r"\b[ABCDEFGHJNPQRSUVW]-?\d{7}[0-9A-J]\b"),
        "[ES_CIF]",
        validator=_cif_check,
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

    # Password / secret field assignments.
    # Covers bash/YAML/env-file (key=value, key: value) and JSON ("key": "value").
    # Optional surrounding quotes on the key handle JSON object keys.
    # Optional leading quote on the value handles JSON string values.
    # FIX B3: added access_key, secret_key, api_key, clave, secret, token.
    # FIX M1.5 (QA-B10): negative lookahead rejects JSON-Schema-style definitions
    # where the value is an object (`"password": {"type": "string"}`) instead of
    # an actual credential.
    _Pattern(
        EntityType.PASSWORD_FIELD,
        re.compile(
            r'(?:"?(?:password|contraseña|passwd|pwd|pass'
            r'|access_key|secret_key|api_key|clave|secret|token)"?)'
            r'\s*[=:]\s*(?!\{)"?\S+',
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
