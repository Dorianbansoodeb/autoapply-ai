"""Drop any extracted claim that cannot be traced to the resume text.

The LLM is untrusted. Code decides what is allowed to enter the profile.
"""

from __future__ import annotations

import re

from autoapply.profile.models import Fact

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def appears_in(needle: str, haystack: str) -> bool:
    if not needle or not needle.strip():
        return True
    return normalize(needle) in normalize(haystack)


def numbers_in(text: str) -> set[str]:
    return {match.replace(",", "") for match in _NUMBER_RE.findall(text or "")}


def validate_fact(fact: Fact, source_text: str) -> list[str]:
    """Return reasons the fact cannot be kept. Empty list means keep."""
    reasons: list[str] = []
    source_numbers = numbers_in(source_text)
    source_norm = normalize(source_text)

    if fact.employer and not appears_in(fact.employer, source_text):
        reasons.append(f"employer {fact.employer!r} not in resume")
    if fact.title and not appears_in(fact.title, source_text):
        reasons.append(f"title {fact.title!r} not in resume")
    for tech in fact.technologies:
        if tech and not appears_in(tech, source_text):
            reasons.append(f"technology {tech!r} not in resume")
    for metric in fact.metrics:
        extra = numbers_in(metric) - source_numbers
        if extra or (metric and normalize(metric) not in source_norm and not numbers_in(metric)):
            if extra:
                reasons.append(f"metric {metric!r} not in resume")
            elif metric and not appears_in(metric, source_text):
                reasons.append(f"metric {metric!r} not in resume")

    extra_numbers = numbers_in(fact.text) - source_numbers
    extra_numbers = {
        n for n in extra_numbers if not _is_plausible_date_fragment(n, fact, source_text)
    }
    if extra_numbers:
        reasons.append(f"numbers {sorted(extra_numbers)} not in resume")

    for stamp in (fact.start, fact.end):
        if stamp and not _date_supported(stamp, source_text):
            reasons.append(f"date {stamp!r} not in resume")
    return reasons


def _is_plausible_date_fragment(number: str, fact: Fact, source_text: str) -> bool:
    if number in {"01", "02", "03", "04", "05", "06", "07", "08", "09"} or (
        number.isdigit() and 1 <= int(number) <= 12
    ):
        return any(
            _date_supported(stamp, source_text) for stamp in (fact.start, fact.end) if stamp
        )
    return False


def _date_supported(stamp: str, source_text: str) -> bool:
    if appears_in(stamp, source_text):
        return True
    years = re.findall(r"\b(?:19|20)\d{2}\b", stamp)
    if not years:
        return False
    return all(year in source_text for year in years)


def filter_facts(facts: list[Fact], source_text: str) -> tuple[list[Fact], list[tuple[Fact, list[str]]]]:
    kept: list[Fact] = []
    rejected: list[tuple[Fact, list[str]]] = []
    for fact in facts:
        reasons = validate_fact(fact, source_text)
        if reasons:
            rejected.append((fact, reasons))
        else:
            kept.append(fact)
    return kept, rejected
