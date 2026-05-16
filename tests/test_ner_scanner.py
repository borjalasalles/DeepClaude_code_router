"""Tests for ner_scanner — personal name detection."""
from __future__ import annotations

import pytest

from deep_devops.router.ner_scanner import (
    _dedup,
    _looks_like_code,
    _merge_compound_names,
    _norm,
    _wordlist_scan,
    scan,
)
from deep_devops.router.pii_scanner import DetectedEntity


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

class TestNorm:
    def test_lowercase(self):
        assert _norm("MIGUEL") == "miguel"

    def test_strip_accent(self):
        assert _norm("Ángel") == "angel"
        assert _norm("José") == "jose"
        assert _norm("García") == "garcia"

    def test_compound_with_tilde(self):
        assert _norm("Adrián") == "adrian"

    def test_already_plain(self):
        assert _norm("miguel") == "miguel"


# ---------------------------------------------------------------------------
# Code detection
# ---------------------------------------------------------------------------

class TestCodeDetection:
    def test_code_fence_detected(self):
        assert _looks_like_code("```python\ndef foo(): pass\n```")

    def test_plain_text_not_code(self):
        assert not _looks_like_code("me llamo Carlos García")


# ---------------------------------------------------------------------------
# Wordlist scan — case / tilde / diminutivo / compound
# ---------------------------------------------------------------------------

class TestWordlistScan:
    def test_lowercase_name_with_context(self):
        entities = _wordlist_scan("hola me llamo miguel, como me llamo?")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types

    def test_uppercase_name_with_context(self):
        entities = _wordlist_scan("HOLA ME LLAMO MIGUEL")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types

    def test_tilde_variant(self):
        # "Angel" without tilde == "Ángel"
        entities = _wordlist_scan("me llamo Angel")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types

    def test_no_context_no_detection(self):
        entities = _wordlist_scan("Carlos es un nombre.")
        assert entities == []

    def test_diminutivo_dani(self):
        entities = _wordlist_scan("me llamo dani")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types

    def test_diminutivo_javi(self):
        entities = _wordlist_scan("mi colega javi trabaja aqui")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types

    def test_diminutivo_paco(self):
        entities = _wordlist_scan("hable con paco ayer")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types

    def test_surname_with_context(self):
        entities = _wordlist_scan("mi jefe se llama Garcia")
        types = [e.entity_type for e in entities]
        assert any(t in types for t in ("APELLIDO", "NOMBRE_PROPIO", "NOMBRE_COMPUESTO"))

    def test_english_context(self):
        entities = _wordlist_scan("my name is Sarah")
        types = [e.entity_type for e in entities]
        assert "NOMBRE_PROPIO" in types or "NOMBRE_COMPUESTO" in types


# ---------------------------------------------------------------------------
# Compound name merging
# ---------------------------------------------------------------------------

def _make_entity(typ, value, start):
    return DetectedEntity(
        entity_type=typ, value=value,
        start=start, end=start + len(value),
        placeholder=f"[{typ}]",
    )


class TestMergeCompoundNames:
    def test_space_separator(self):
        text = "Miguel Angel"
        e1 = _make_entity("NOMBRE_PROPIO", "Miguel", 0)
        e2 = _make_entity("NOMBRE_PROPIO", "Angel", 7)
        result = _merge_compound_names([e1, e2], text)
        assert len(result) == 1
        assert result[0].entity_type == "NOMBRE_COMPUESTO"
        assert result[0].value == "Miguel Angel"

    def test_hyphen_separator(self):
        text = "Juan-Carlos"
        e1 = _make_entity("NOMBRE_PROPIO", "Juan", 0)
        e2 = _make_entity("NOMBRE_PROPIO", "Carlos", 5)
        result = _merge_compound_names([e1, e2], text)
        assert len(result) == 1
        assert result[0].entity_type == "NOMBRE_COMPUESTO"

    def test_spaced_hyphen(self):
        text = "Juan - Carlos"
        e1 = _make_entity("NOMBRE_PROPIO", "Juan", 0)
        e2 = _make_entity("NOMBRE_PROPIO", "Carlos", 7)
        result = _merge_compound_names([e1, e2], text)
        assert len(result) == 1
        assert result[0].entity_type == "NOMBRE_COMPUESTO"

    def test_three_parts(self):
        text = "Maria Jose Garcia"
        e1 = _make_entity("NOMBRE_PROPIO", "Maria", 0)
        e2 = _make_entity("NOMBRE_PROPIO", "Jose", 6)
        e3 = _make_entity("APELLIDO", "Garcia", 11)
        result = _merge_compound_names([e1, e2, e3], text)
        assert len(result) == 1
        assert result[0].value == "Maria Jose Garcia"

    def test_non_adjacent_not_merged(self):
        text = "Miguel trabaja con Carlos"
        e1 = _make_entity("NOMBRE_PROPIO", "Miguel", 0)
        e2 = _make_entity("NOMBRE_PROPIO", "Carlos", 19)
        result = _merge_compound_names([e1, e2], text)
        assert len(result) == 2

    def test_single_entity_unchanged(self):
        text = "Miguel"
        e = _make_entity("NOMBRE_PROPIO", "Miguel", 0)
        result = _merge_compound_names([e], text)
        assert len(result) == 1
        assert result[0].entity_type == "NOMBRE_PROPIO"


# ---------------------------------------------------------------------------
# scan() — integration
# ---------------------------------------------------------------------------

class TestScan:
    def test_skips_code_fence(self):
        result = scan("```python\nCarlos = 'me llamo Carlos'\n```")
        assert not result.detected

    def test_lowercase_input(self):
        result = scan("hola me llamo miguel, como me llamo?")
        assert result.detected

    def test_miguel_angel_compound(self):
        result = scan("mi jefe se llama Miguel Angel")
        assert result.detected
        types = [e.entity_type for e in result.entities]
        assert "NOMBRE_COMPUESTO" in types

    def test_miguel_angel_tilde(self):
        result = scan("me llamo Miguel Ángel")
        assert result.detected

    def test_diminutivo_scan(self):
        result = scan("mi colega se llama dani")
        assert result.detected

    def test_require_context_false(self):
        # Without context gate: should still detect Miguel in output context
        result = scan("Hola Miguel. Te llamas Miguel.", require_context=False)
        assert result.detected

    def test_no_context_blocked_by_default(self):
        result = scan("Miguel es un nombre bonito.")
        from deep_devops.router.ner_scanner import _load_nlp
        if _load_nlp() is None:
            # Wordlist path requires context
            assert not result.detected

    def test_dedup_no_overlap(self):
        result = scan("me llamo Laura y Laura es ingeniera.")
        spans = [(e.start, e.end) for e in result.entities]
        for i, (s1, e1) in enumerate(spans):
            for j, (s2, e2) in enumerate(spans):
                if i != j:
                    assert e1 <= s2 or e2 <= s1

    def test_empty_text(self):
        assert not scan("").detected

    def test_returns_scan_result_type(self):
        from deep_devops.router.pii_scanner import ScanResult
        assert isinstance(scan("texto neutro"), ScanResult)
