"""Every number in generated text must appear in the cited source fact.

Fail validation → caller falls back to the original unmodified bullet.
"""

from __future__ import annotations

from autoapply.profile.models import Fact
from autoapply.profile.validate import numbers_in


def source_blob(fact: Fact) -> str:
    return " ".join(
        part
        for part in [
            fact.text,
            fact.employer or "",
            fact.title or "",
            fact.start or "",
            fact.end or "",
            " ".join(fact.technologies),
            " ".join(fact.metrics),
        ]
        if part
    )


def unsupported_bits(text: str, source: Fact) -> list[str]:
    reasons: list[str] = []
    blob = source_blob(source)
    extra = numbers_in(text) - numbers_in(blob)
    if extra:
        reasons.append(f"numbers {sorted(extra)} not in source {source.id}")
    lowered = text.lower()
    if any(token in lowered for token in ("[insert", "todo", "tbd", "lorem ipsum")):
        reasons.append("placeholder text")
    return reasons


def coerce_bullet(proposed: str, source: Fact) -> str:
    if not proposed.strip() or unsupported_bits(proposed, source):
        return source.text
    return proposed.strip()
