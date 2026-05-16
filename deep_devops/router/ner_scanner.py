"""
NER scanner — detects personal names not covered by regex patterns.

Detection layers (tried in order):
  1. spaCy es_core_news_sm (optional, lazy-loaded): contextual PER detection.
  2. Wordlist fallback (always available): INE + international + diminutivos,
     with normalization (accent/case/misspelling resistant).

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
# spaCy — lazy singleton
# ---------------------------------------------------------------------------

_NLP: object | None = None
_NLP_LOADED = False


def _load_nlp() -> object | None:
    global _NLP, _NLP_LOADED
    if _NLP_LOADED:
        return _NLP
    _NLP_LOADED = True
    try:
        import spacy  # type: ignore[import]
        _NLP = spacy.load("es_core_news_sm")
    except Exception:
        _NLP = None
    return _NLP


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

def _spacy_scan(text: str) -> list[DetectedEntity]:
    nlp = _load_nlp()
    if nlp is None:
        return []

    doc = nlp(text)  # type: ignore[operator]
    entities: list[DetectedEntity] = []
    for ent in doc.ents:
        if ent.label_ == "PER":
            entities.append(DetectedEntity(
                entity_type="NOMBRE_PROPIO",
                value=ent.text,
                start=ent.start_char,
                end=ent.end_char,
                placeholder="[NOMBRE_PROPIO]",
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
    if not text or _looks_like_code(text):
        return ScanResult(detected=False)

    nlp = _load_nlp()
    if nlp is not None:
        raw = _spacy_scan(text)
        # spaCy may miss lowercase / diminutivo tokens — supplement with wordlist
        wordlist = _wordlist_scan(text, require_context=require_context)
        # Combine: spaCy spans take priority; add wordlist only where no overlap
        spacy_spans = {(e.start, e.end) for e in raw}
        for e in wordlist:
            if (e.start, e.end) not in spacy_spans:
                raw.append(e)
    else:
        raw = _wordlist_scan(text, require_context=require_context)

    deduped = _dedup(raw)
    # Final compound merge across both sources
    deduped = _merge_compound_names(deduped, text)

    return ScanResult(detected=bool(deduped), entities=deduped)


def is_available() -> bool:
    """True if spaCy and es_core_news_sm are installed."""
    return _load_nlp() is not None
