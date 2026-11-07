"""Draft or reuse answers. Approval is based on evidence, not model confidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autoapply.cancel import CancelToken
from autoapply.docs.validate import unsupported_bits
from autoapply.llm.client import LLMClient, wrap_untrusted
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile.models import CandidateProfile, Fact
from autoapply.questions.classify import QuestionClass, classify_label
from autoapply.storage.answers import AnswerBank

SYSTEM = (
    "Answer the application question using only the provided facts. "
    "Never invent employers, titles, dates, metrics, or technologies. "
    "If you cannot answer from the facts, set unsupported=true. Return JSON only."
)


class QuestionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    kind: QuestionClass
    action: Literal["fill", "reuse", "ask", "skip", "stop"]
    answer: str = ""
    cited_fact_ids: list[str] = Field(default_factory=list)
    needs_review: bool = True
    reason: str = ""
    unsupported: bool = False


def retrieve_facts(profile: CandidateProfile, question: str, limit: int = 6) -> list[Fact]:
    facts = profile.verified_facts() or profile.facts
    words = {w.lower() for w in question.split() if len(w) > 3}

    def score(fact: Fact) -> int:
        blob = f"{fact.text} {fact.employer} {fact.title} {' '.join(fact.technologies)}".lower()
        return sum(1 for w in words if w in blob)

    ranked = sorted(facts, key=score, reverse=True)
    return ranked[:limit] or facts[:limit]


async def answer_question(
    question: str,
    profile: CandidateProfile,
    llm: LLMClient,
    bank: AnswerBank | None = None,
    *,
    cancel: CancelToken | None = None,
    explicit_sensitive: dict[str, str] | None = None,
    saved_prefs: dict[str, str] | None = None,
) -> QuestionDecision:
    kind = classify_label(question)
    if kind is QuestionClass.ASSESSMENT:
        return QuestionDecision(
            question=question,
            kind=kind,
            action="stop",
            reason="assessment; hand control to the user",
        )
    if kind is QuestionClass.SENSITIVE:
        saved = (explicit_sensitive or {}).get(question) or (
            bank.get(question).answer if bank and bank.get(question) else None
        )
        if saved:
            return QuestionDecision(
                question=question,
                kind=kind,
                action="fill",
                answer=saved,
                needs_review=True,
                reason="explicit saved sensitive answer",
            )
        return QuestionDecision(
            question=question,
            kind=kind,
            action="skip",
            answer="Decline to answer",
            needs_review=True,
            reason="sensitive; no explicit saved answer; default decline",
        )
    if kind is QuestionClass.PREFERENCE:
        pref = (saved_prefs or {}).get(question)
        if bank and not pref:
            row = bank.get(question)
            pref = row.answer if row else None
        if pref:
            return QuestionDecision(
                question=question,
                kind=kind,
                action="reuse",
                answer=pref,
                needs_review=False,
                reason="saved preference",
            )
        return QuestionDecision(
            question=question,
            kind=kind,
            action="ask",
            needs_review=True,
            reason="preference not saved",
        )
    if bank:
        row = bank.get(question)
        if row and row.approved:
            return QuestionDecision(
                question=question,
                kind=kind,
                action="reuse",
                answer=row.answer,
                cited_fact_ids=[x for x in row.cited_fact_ids.split("\n") if x],
                needs_review=False,
                reason="answer bank",
            )

    facts = retrieve_facts(profile, question)
    draft = await llm.complete(
        [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": wrap_untrusted(question)
                + "\n\nFacts:\n"
                + "\n".join(
                    f"- {f.id} {f.employer} {f.title} {f.text}" for f in facts
                ),
            },
        ],
        FreeTextDraft,
        cancel=cancel,
    )
    known = {f.id: f for f in facts}
    cited = [i for i in draft.cited_fact_ids if i in known]
    source = facts[0] if facts else Fact(id="none", type="skill", text="")
    if cited:
        source = known[cited[0]]
    unsupported = draft.unsupported or bool(unsupported_bits(draft.answer, source))
    return QuestionDecision(
        question=question,
        kind=kind,
        action="fill",
        answer=draft.answer,
        cited_fact_ids=cited,
        needs_review=True,
        unsupported=unsupported,
        reason="unsupported claim" if unsupported else "new free text; needs review",
    )
