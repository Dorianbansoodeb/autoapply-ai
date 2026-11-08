"""Question classes from the spec. Sensitive and assessments are decided in code."""

from __future__ import annotations

import re
from enum import StrEnum


class QuestionClass(StrEnum):
    FACTUAL = "A"
    EXPERIENCE = "B"
    BEHAVIORAL = "C"
    PREFERENCE = "D"
    SENSITIVE = "E"
    ASSESSMENT = "F"


_SENSITIVE = re.compile(
    r"disability|veteran|gender|race|hispanic|ethnicity|sexual orientation|"
    r"criminal|conviction|immigration|citizenship|ssn|social.?security|"
    r"national origin|religion",
    re.I,
)
_ASSESSMENT = re.compile(
    r"hackerrank|codility|hirevue|timed test|coding assessment|complete this assessment",
    re.I,
)
_BEHAVIORAL = re.compile(r"tell us about a time|why do you want|cover letter", re.I)
_PREFERENCE = re.compile(r"salary|start date|willing to relocate|remote", re.I)
_EXPERIENCE = re.compile(r"experience|describe a project|resume", re.I)


_AMBIGUOUS = re.compile(r"\b(it depends|unclear|ambiguous|not sure how)\b", re.I)


def is_ambiguous(label: str) -> bool:
    return bool(_AMBIGUOUS.search(label or ""))


def classify_label(label: str) -> QuestionClass:
    if _SENSITIVE.search(label):
        return QuestionClass.SENSITIVE
    if _ASSESSMENT.search(label):
        return QuestionClass.ASSESSMENT
    if _BEHAVIORAL.search(label):
        return QuestionClass.BEHAVIORAL
    if _PREFERENCE.search(label):
        return QuestionClass.PREFERENCE
    if _EXPERIENCE.search(label):
        return QuestionClass.EXPERIENCE
    return QuestionClass.FACTUAL
