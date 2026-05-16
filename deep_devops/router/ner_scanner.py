"""
NER scanner — detects personal names not covered by regex patterns.

Detection layers:
  1. spaCy, language-aware (MANDATORY, lazy-loaded): es_core_news_sm for
     Spanish, en_core_web_sm for English, picked per-text by langdetect.
     A Spanish model over English code questions mislabels ordinary words
     ("list") as people — language routing keeps spaCy an *aid* to redaction
     instead of mangling English (approach 2, 2026-05-16).
  2. Wordlist supplement: INE + international + diminutivos, with
     normalization (accent/case/misspelling resistant).

spaCy AIDS redaction — it never blocks the turn. Detected names are redacted
to placeholders and routed onward (the caller decides routing). NER is a
tier-1 security control: if the spaCy layer cannot load at all, ``scan()``
raises ``NerUnavailableError`` instead of silently degrading to wordlist-only
— a guardrail that disappears without a signal is not a guardrail (Hard Rule
#8, leak target = 0). That is layer-absence, not a per-query block. The
wordlist is a *supplement* to spaCy, never a fallback for it. We iterate
detection logic / wordlists from observed edge-case failures, not
speculatively. See docs/session-2026-05-16-ner-edgecases.md (P0a/P0b) and
docs/session-2026-05-16-guardrail-middleware.md.

Both layers:
  - Skip code-fence blocks (``` markers) to avoid FPs on identifiers.
  - Merge adjacent single-name matches into compound names
    (Miguel Ángel, José María, Juan-Carlos, Juan Carlos, etc.).
  - Treat diminutivos (dani, paco, javi…) as first-name matches.

Normalization pipeline: lowercase → strip diacritics (NFD→ASCII).
This makes matching resistant to:
  - Case:    MIGUEL == miguel == Miguel
  - Tildes:  Ángel == Angel, José == Jose, García == Garcia
  - Common misspellings caused by missing/wrong accent.

Compound-name separators accepted between two adjacent name tokens:
  " " | "-" | " -" | "- " | " - "  (1–3 chars total).

scan(text, require_context=True) is the standard hot-path call.
scan(text, require_context=False) is used for output-side scanning
  where we want to catch any name the model echoed back.
"""
from __future__ import annotations

import re
import unicodedata

from deep_devops.data.names import (
    ALL_FIRST_NAMES_LOWER,
    ALL_SURNAMES_LOWER,
    DIMINUTIVOS,
)
from deep_devops.router.pii_scanner import DetectedEntity, ScanResult


class NerUnavailableError(RuntimeError):
    """The NER security layer (spaCy + es_core_news_sm) failed to load.

    Raised by ``scan()`` instead of silently falling back to wordlist-only.
    Callers route this through the existing fail-closed path (no upstream
    call; trace records ``scan_error``).
    """

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Lowercase + strip diacritics → ASCII-safe form for fuzzy lookup."""
    return (
        unicodedata.normalize("NFD", s.lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


# Pre-normalised lookup sets (built once at import)
_FIRST_NORM: frozenset[str] = frozenset(_norm(n) for n in ALL_FIRST_NAMES_LOWER)
_SURN_NORM: frozenset[str] = frozenset(_norm(n) for n in ALL_SURNAMES_LOWER)
_DIMI_NORM: frozenset[str] = frozenset(_norm(d) for d in DIMINUTIVOS)

# Combined first-name set includes diminutivos
_ALL_FIRST_NORM: frozenset[str] = _FIRST_NORM | _DIMI_NORM


# ---------------------------------------------------------------------------
# spaCy — language-aware lazy singletons
# ---------------------------------------------------------------------------
#
# A Spanish model run over English code questions tags ordinary words
# ("list") as PER. Approach 2 (2026-05-16): pick the model by detected
# language so spaCy *aids* redaction instead of mangling English. Deliberately
# lean — language detection is a single seeded call; we iterate the logic from
# observed edge-case failures, not speculatively.

_SPACY_MODELS: dict[str, str] = {"es": "es_core_news_sm", "en": "en_core_web_sm"}

_NLP: dict[str, object] = {}
_NLP_LOADED = False
_NLP_ERROR: str | None = None


def _load_nlp() -> dict[str, object] | None:
    """Lazy singleton. Returns ``{lang: pipeline}``, or None on failure.

    Both models are core deps, so both must load — a simple invariant (no
    fallback branching). Does NOT raise (so ``is_available()`` can probe
    safely); the failure reason is captured in ``_NLP_ERROR`` for the
    message ``scan()`` raises.
    """
    global _NLP_LOADED, _NLP_ERROR
    if _NLP_LOADED:
        return _NLP or None
    _NLP_LOADED = True
    try:
        import spacy  # type: ignore[import]
        for lang, model in _SPACY_MODELS.items():
            _NLP[lang] = spacy.load(model)
    except Exception as exc:
        _NLP.clear()
        _NLP_ERROR = f"{type(exc).__name__}: {exc}"
    return _NLP or None


def _detect_lang(text: str) -> str:
    """Best-effort guess → 'es' or 'en'.

    Defaults to 'es' (the security-critical language for this EU tool) when
    text is too short or detection is uncertain: with redaction (not
    blocking) the cost of over-detection is only over-redaction, while
    missing a Spanish name is a real leak. langdetect is deterministic with a
    fixed seed (Cap 3 — deterministic signals, no LLM-judge).
    """
    stripped = text.strip()
    if len(stripped) < 12:
        return "es"
    try:
        from langdetect import DetectorFactory, detect  # type: ignore[import]
        DetectorFactory.seed = 0
        return "en" if detect(stripped) == "en" else "es"
    except Exception:
        return "es"


# ---------------------------------------------------------------------------
# Code-detection — skip NER to avoid FPs on identifiers
# ---------------------------------------------------------------------------

_CODE_FENCE = re.compile(r"```")


def _looks_like_code(text: str) -> bool:
    return bool(_CODE_FENCE.search(text))


# ---------------------------------------------------------------------------
# Compound-name separator
# ---------------------------------------------------------------------------

# Separators accepted between two adjacent name tokens.
# Covers: " " "  " "-" " -" "- " " - " and Unicode dashes.
_COMPOUND_SEP = re.compile(r"[ \t]*[\-–—][ \t]*|[ \t]+")


def _merge_compound_names(
    entities: list[DetectedEntity], text: str
) -> list[DetectedEntity]:
    """Merge runs of adjacent name entities (any separator ≤ 3 chars).

    Examples:
      [Miguel][Ángel]           → [NOMBRE_COMPUESTO: "Miguel Ángel"]
      [José][María][García]     → [NOMBRE_COMPUESTO: "José María García"]
      [Juan][-][Carlos]         → but "-" alone is not a name; gaps are
                                   checked in the *text between spans*.
    """
    if len(entities) < 2:
        return entities

    groups: list[list[DetectedEntity]] = []
    current: list[DetectedEntity] = [entities[0]]

    for e2 in entities[1:]:
        e1 = current[-1]
        gap = text[e1.end: e2.start]
        if len(gap) <= 3 and _COMPOUND_SEP.fullmatch(gap):
            current.append(e2)
        else:
            groups.append(current)
            current = [e2]
    groups.append(current)

    result: list[DetectedEntity] = []
    for group in groups:
        if len(group) == 1:
            result.append(group[0])
        else:
            result.append(DetectedEntity(
                entity_type="NOMBRE_COMPUESTO",
                value=text[group[0].start: group[-1].end],
                start=group[0].start,
                end=group[-1].end,
                placeholder="[NOMBRE_COMPUESTO]",
            ))
    return result


# ---------------------------------------------------------------------------
# Context-word gate (wordlist path only)
# ---------------------------------------------------------------------------

_NAME_CONTEXT: frozenset[str] = frozenset({
    "me llamo", "mi nombre", "llamame", "llamado", "llamada",
    "llaman", "me dicen",
    "trabaja", "jefe", "jefa", "colega", "companero", "companera",
    "cliente", "contacto", "usuario", "empleado", "empleada",
    "director", "directora", "gerente", "responsable", "encargado",
    "hable con", "reunion con", "email de", "correo de",
    "de parte de", "enviado por", "firmado por",
    "my name", "i'm called", "i am", "contact", "manager", "colleague",
    "sent by", "signed by", "on behalf of",
    "mon nom", "je m'appelle", "mein name", "ich bin",
})


def _has_name_context(text_norm: str) -> bool:
    return any(kw in text_norm for kw in _NAME_CONTEXT)


# ---------------------------------------------------------------------------
# Token regex — matches any word ≥ 2 chars (case-insensitive via _norm lookup)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"\b[A-Za-zÀ-ɏḀ-ỿ]{2,}\b"
)


# ---------------------------------------------------------------------------
# Wordlist layer
# ---------------------------------------------------------------------------

def _wordlist_scan(text: str, require_context: bool = True) -> list[DetectedEntity]:
    text_norm = _norm(text)

    if require_context and not _has_name_context(text_norm):
        return []

    entities: list[DetectedEntity] = []
    for m in _TOKEN_RE.finditer(text):
        w = _norm(m.group())
        if w in _ALL_FIRST_NORM:
            entities.append(DetectedEntity(
                entity_type="NOMBRE_PROPIO",
                value=m.group(),
                start=m.start(),
                end=m.end(),
                placeholder="[NOMBRE_PROPIO]",
            ))
        elif w in _SURN_NORM:
            entities.append(DetectedEntity(
                entity_type="APELLIDO",
                value=m.group(),
                start=m.start(),
                end=m.end(),
                placeholder="[APELLIDO]",
            ))

    return _merge_compound_names(entities, text)


# ---------------------------------------------------------------------------
# spaCy layer
# ---------------------------------------------------------------------------

# es_core_news_sm labels people "PER"; en_core_web_sm labels them "PERSON".
# Both must map to NOMBRE_PROPIO — missing "PERSON" would silently leak every
# English-detected name.
_PERSON_LABELS = frozenset({"PER", "PERSON"})


def _spacy_scan(text: str, nlp: object) -> list[DetectedEntity]:
    doc = nlp(text)  # type: ignore[operator]
    entities: list[DetectedEntity] = []
    for ent in doc.ents:
        if ent.label_ in _PERSON_LABELS:
            # spaCy returns a multi-token name ("Miguel Angel", "John Smith")
            # as ONE span — _merge_compound_names only merges *separate*
            # adjacent entities, so a single span would never become
            # NOMBRE_COMPUESTO. Relabel here by token count: ≥2 name tokens
            # → NOMBRE_COMPUESTO, else NOMBRE_PROPIO. Redaction is identical
            # either way; this only makes the label match the structure.
            kind = (
                "NOMBRE_COMPUESTO"
                if len(_TOKEN_RE.findall(ent.text)) >= 2
                else "NOMBRE_PROPIO"
            )
            entities.append(DetectedEntity(
                entity_type=kind,
                value=ent.text,
                start=ent.start_char,
                end=ent.end_char,
                placeholder=f"[{kind}]",
            ))
    return entities


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _dedup(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Remove overlapping spans — sort by start, keep non-overlapping."""
    entities.sort(key=lambda e: e.start)
    out: list[DetectedEntity] = []
    last_end = -1
    for e in entities:
        if e.start >= last_end:
            out.append(e)
            last_end = e.end
    return out


def scan(text: str, require_context: bool = True) -> ScanResult:
    """Scan *text* for personal names.

    Parameters
    ----------
    require_context:
        When True (default, hot-path), wordlist fires only when a
        personal-reference keyword is nearby.  Set False for output-side
        scanning where we want to catch any name the model echoed back.
        spaCy is always contextual regardless of this flag.
    """
    # NER availability is a precondition for routing AT ALL, not per-message:
    # a broken security layer is the failure, independent of this text.
    # Fail-closed (raise) instead of silently degrading to wordlist-only.
    nlp_map = _load_nlp()
    if nlp_map is None:
        raise NerUnavailableError(
            "NER security layer unavailable (spaCy models "
            f"{sorted(_SPACY_MODELS.values())} failed to load: {_NLP_ERROR}). "
            "Required tier-1 control — run `uv sync`. Refusing to route to "
            "avoid leaking PII to tier-1."
        )

    if not text or _looks_like_code(text):
        return ScanResult(detected=False)

    nlp = nlp_map.get(_detect_lang(text)) or next(iter(nlp_map.values()))
    raw = _spacy_scan(text, nlp)
    # spaCy may miss lowercase / diminutivo tokens — supplement with wordlist.
    wordlist = _wordlist_scan(text, require_context=require_context)
    # Combine: spaCy spans take priority; add wordlist only where no overlap.
    spacy_spans = {(e.start, e.end) for e in raw}
    for e in wordlist:
        if (e.start, e.end) not in spacy_spans:
            raw.append(e)

    deduped = _dedup(raw)
    # Final compound merge across both sources
    deduped = _merge_compound_names(deduped, text)

    return ScanResult(detected=bool(deduped), entities=deduped)


def is_available() -> bool:
    """True if spaCy and both language models (es + en) are installed."""
    return _load_nlp() is not None
