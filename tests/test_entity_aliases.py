"""Tests for entity_aliases — company name pseudonymisation."""
from __future__ import annotations

import pytest

from deep_devops.router.entity_aliases import apply


class TestBasicSubstitution:
    def test_mapfre(self):
        ctx = apply("Trabajo en Mapfre con el equipo de datos.")
        assert "aseguradora M" in ctx.aliased_text
        assert "Mapfre" not in ctx.aliased_text

    def test_mapfre_tech_longest_match(self):
        ctx = apply("El proyecto es de Mapfre Tech, no de Mapfre directamente.")
        assert "aseguradora M tech" in ctx.aliased_text
        # "aseguradora M" (without tech) must also appear for the second occurrence
        assert ctx.aliased_text.count("aseguradora M") >= 2

    def test_el_corte_ingles(self):
        ctx = apply("El cliente es El Corte Inglés.")
        assert "grupo retailer" in ctx.aliased_text
        assert "Corte Inglés" not in ctx.aliased_text

    def test_el_corte_ingles_no_accent(self):
        ctx = apply("Reunión con el corte ingles mañana.")
        assert "grupo retailer" in ctx.aliased_text

    def test_acciona(self):
        ctx = apply("Acciona gestiona la obra.")
        assert "conglomerado infraestructura" in ctx.aliased_text
        assert "Acciona" not in ctx.aliased_text

    def test_ecovidrio(self):
        ctx = apply("Contacta con Ecovidrio para el reciclaje.")
        assert "gestión de residuos" in ctx.aliased_text
        assert "Ecovidrio" not in ctx.aliased_text

    def test_case_insensitive(self):
        assert "aseguradora M" in apply("MAPFRE").aliased_text
        assert "aseguradora M" in apply("mapfre").aliased_text
        assert "aseguradora M" in apply("Mapfre").aliased_text

    def test_no_match_unchanged(self):
        text = "Hola, ¿cómo estás?"
        ctx = apply(text)
        assert ctx.aliased_text == text
        assert not ctx.reverse_map

    def test_multiple_companies(self):
        text = "Mapfre y Acciona colaboran."
        ctx = apply(text)
        assert "aseguradora M" in ctx.aliased_text
        assert "conglomerado infraestructura" in ctx.aliased_text
        assert "Mapfre" not in ctx.aliased_text
        assert "Acciona" not in ctx.aliased_text


class TestRestoration:
    def test_restore_mapfre(self):
        ctx = apply("Mapfre Tech está interesado.")
        model_response = "aseguradora M tech está interesado."
        restored = ctx.restore(model_response)
        assert "Mapfre Tech" in restored
        assert "aseguradora M tech" not in restored.lower()

    def test_restore_multiple(self):
        ctx = apply("Mapfre y Acciona trabajan juntos.")
        model_response = "aseguradora M y conglomerado infraestructura trabajan juntos."
        restored = ctx.restore(model_response)
        assert "Mapfre" in restored
        assert "Acciona" in restored

    def test_restore_longest_first(self):
        # Both "aseguradora M tech" and "aseguradora M" in response
        ctx = apply("Mapfre Tech y Mapfre son distintos.")
        model_response = "aseguradora M tech y aseguradora M son distintos."
        restored = ctx.restore(model_response)
        # Should not produce "Mapfre Tech Tech" or "Mapfre M"
        assert "aseguradora" not in restored

    def test_restore_noop_when_no_alias(self):
        ctx = apply("texto sin empresas")
        assert ctx.restore("texto sin empresas") == "texto sin empresas"

    def test_aliased_text_in_context(self):
        ctx = apply("Acciona tiene 1000 empleados.")
        assert ctx.aliased_text == "conglomerado infraestructura tiene 1000 empleados."
        assert ctx.reverse_map["conglomerado infraestructura"] == "Acciona"
