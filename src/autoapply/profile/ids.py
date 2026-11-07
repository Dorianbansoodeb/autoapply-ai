"""Stable-enough fact IDs: type prefix plus a counter."""

from __future__ import annotations

from autoapply.profile.models import Fact

_PREFIX = {
    "experience_bullet": "exp",
    "experience_role": "exp",
    "education": "edu",
    "skill": "skill",
    "certification": "cert",
    "identity": "id",
    "preference": "pref",
}


def assign_ids(facts: list[Fact]) -> list[Fact]:
    counters: dict[str, int] = {}
    assigned: list[Fact] = []
    for fact in facts:
        prefix = _PREFIX.get(fact.type, "item")
        counters[prefix] = counters.get(prefix, 0) + 1
        assigned.append(fact.model_copy(update={"id": f"{prefix}_{counters[prefix]:03d}"}))
    return assigned
