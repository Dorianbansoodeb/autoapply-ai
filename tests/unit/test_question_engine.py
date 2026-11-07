from __future__ import annotations

import json
from pathlib import Path

import pytest

from autoapply.llm.client import MockLLMClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.profile import load_profile
from autoapply.questions.engine import answer_question
from autoapply.storage.answers import AnswerBank


EVAL = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures" / "eval_set.json").read_text()
)


@pytest.mark.asyncio
async def test_eval_set_escalates_sensitive_and_assessments(
    fixtures_dir: Path, tmp_path: Path
) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    llm = MockLLMClient(
        FreeTextDraft(
            answer="I wrote the first algorithm at Analytical Engine Co.",
            cited_fact_ids=["exp_001"],
            unsupported=False,
        )
    )
    bank = AnswerBank(tmp_path / "db.sqlite")
    missed_escalation = 0
    unsupported = 0
    for item in EVAL:
        decision = await answer_question(item["question"], profile, llm, bank)
        if item["expect"] in {"skip", "stop", "ask"} and decision.action != item["expect"]:
            missed_escalation += 1
        if decision.unsupported:
            unsupported += 1
    assert missed_escalation == 0
    assert unsupported == 0


@pytest.mark.asyncio
async def test_answer_bank_reuses_approved(fixtures_dir: Path, tmp_path: Path) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    bank = AnswerBank(tmp_path / "db.sqlite")
    bank.put("Why do you want this role?", "Because of the Analytical Engine.", kind="C")
    llm = MockLLMClient(
        FreeTextDraft(answer="SHOULD NOT BE USED", cited_fact_ids=[], unsupported=False)
    )
    decision = await answer_question("Why do you want this role?", profile, llm, bank)
    assert decision.action == "reuse"
    assert "Analytical Engine" in decision.answer
    assert llm.calls == []
