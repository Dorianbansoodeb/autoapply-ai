"""Policy gate: code, not prompts. Unknown/sensitive → do not auto-fill."""

from __future__ import annotations

import re

from autoapply.questions.classify import QuestionClass, classify_label

ASSESSMENT_PAGE_RE = re.compile(
    r"hackerrank|codility|hirevue|timed test|coding assessment", re.I
)


def may_auto_fill(label: str) -> bool:
    kind = classify_label(label)
    return kind not in {QuestionClass.SENSITIVE, QuestionClass.ASSESSMENT}


def page_looks_like_assessment(text: str) -> bool:
    return bool(ASSESSMENT_PAGE_RE.search(text or ""))
