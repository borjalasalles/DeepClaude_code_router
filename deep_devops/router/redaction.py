"""
Redaction layer — Cap 10 Fig 10-3 reverse map.

Pattern: scan → replace with typed placeholders → call model → restore.

The reverse map lets us send the *non-confidential remainder* of a query to
a lower tier after masking the sensitive fields.  If the only confidential
content was a hostname we redact it, route tier-2, and restore the original
hostname in the response before handing back to the user.

Design constraints (design.md §4.2):
- Stateless: RedactionContext is a plain dataclass, not a singleton.
- Fast: only string operations, no copies of large text until needed.
- Reversible: restore() guarantees a lossless round-trip for every detected entity.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from deep_devops.router.pii_scanner import ScanResult


@dataclass
class RedactionContext:
    """Carries the placeholder → original mapping for a single request."""

    redacted_text: str
    reverse_map: dict[str, str] = field(default_factory=dict)

    def restore(self, text: str) -> str:
        """Replace every placeholder back with its original value.

        Applied in insertion order (Python 3.7+ dict).  If the model echoes
        a placeholder verbatim the substitution is transparent to the user.
        """
        for placeholder, original in self.reverse_map.items():
            text = text.replace(placeholder, original)
        return text


def redact(text: str, result: ScanResult) -> RedactionContext:
    """Build a RedactionContext from a completed ScanResult.

    Each detected entity is replaced by a *unique* numbered placeholder so
    that multiple occurrences of the same value get individual entries in the
    reverse map and restore() works correctly even when the model reorders them.

    Example
    -------
    text    = "token AKIAIOSFODNN7EXAMPLE in prod"
    result  = scan(text)
    ctx     = redact(text, result)
    ctx.redacted_text  -> "token [AWS_ACCESS_KEY_1] in prod"
    ctx.restore("here is [AWS_ACCESS_KEY_1]") -> "here is AKIAIOSFODNN7EXAMPLE"
    """
    if not result.entities:
        return RedactionContext(redacted_text=text)

    counters: dict[str, int] = {}
    reverse_map: dict[str, str] = {}
    segments: list[str] = []
    cursor = 0

    for entity in result.entities:
        entity_name = entity.placeholder.strip("[]")  # e.g. "EMAIL", "AWS_ACCESS_KEY"
        counters[entity_name] = counters.get(entity_name, 0) + 1
        unique_placeholder = f"{{/{entity_name}_{counters[entity_name]}/}}"  # {/EMAIL_1/}

        segments.append(text[cursor : entity.start])
        segments.append(unique_placeholder)
        reverse_map[unique_placeholder] = entity.value
        cursor = entity.end

    segments.append(text[cursor:])
    return RedactionContext(
        redacted_text="".join(segments),
        reverse_map=reverse_map,
    )
