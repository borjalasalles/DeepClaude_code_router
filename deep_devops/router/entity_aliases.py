"""
Entity alias substitution — pseudonymizes known organisation names
before text reaches tier-1 or tier-2 models.

Longest-match patterns are listed first so multi-word variants are
caught before their shorter substrings.

Substitution is reversible: apply() returns an AliasContext whose
restore() reconstructs original names in the model response.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class AliasContext:
    """Carries alias→original mapping for a single request."""

    aliased_text: str
    reverse_map: dict[str, str] = field(default_factory=dict)

    def restore(self, text: str) -> str:
        """Replace aliases back with original names.

        Longest alias first to avoid a shorter alias partially matching
        inside a longer one (e.g. 'aseguradora M' inside 'aseguradora M tech').
        """
        for alias, original in sorted(
            self.reverse_map.items(), key=lambda kv: len(kv[0]), reverse=True
        ):
            text = text.replace(alias, original)
        return text


# (regex, alias) — longest multi-word entries precede their sub-patterns.
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bmapfre\s+tech\b", re.IGNORECASE), "aseguradora M tech"),
    (re.compile(r"\bmapfre\b", re.IGNORECASE), "aseguradora M"),
    (re.compile(r"\bel\s+corte\s+ingl[eé]s\b", re.IGNORECASE), "grupo retailer"),
    (re.compile(r"\bacciona\b", re.IGNORECASE), "conglomerado infraestructura"),
    (re.compile(r"\becovidrio\b", re.IGNORECASE), "gestión de residuos"),
]


def apply(text: str) -> AliasContext:
    """Replace organisation names with sector aliases.

    First occurrence determines the canonical original stored in reverse_map
    (case-preserving). Subsequent occurrences of the same alias are not
    re-stored but are still substituted in the output text.
    """
    result = text
    reverse_map: dict[str, str] = {}

    for pattern, alias in _PATTERNS:
        def _sub(m: re.Match[str], _alias: str = alias) -> str:
            if _alias not in reverse_map:
                reverse_map[_alias] = m.group()
            return _alias

        result = pattern.sub(_sub, result)

    return AliasContext(aliased_text=result, reverse_map=reverse_map)
