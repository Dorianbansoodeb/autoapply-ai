"""Optional live check against a local Ollama server. Not run in default CI."""

from __future__ import annotations

import os

import pytest

from autoapply.llm.client import OpenAICompatClient
from autoapply.llm.schemas import FreeTextDraft
from tests.fixtures.prompts import SCHEMA_PROMPTS

pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_schema_sample() -> None:
    if os.environ.get("AUTOAPPLY_LIVE") != "1":
        pytest.skip("set AUTOAPPLY_LIVE=1 to hit local Ollama")
    model = os.environ.get("AUTOAPPLY_MODEL", "phi3.5:3.8b")
    client = OpenAICompatClient(model=model)
    valid = 0
    try:
        for question in SCHEMA_PROMPTS[:5]:
            draft = await client.complete(
                [
                    {
                        "role": "system",
                        "content": (
                            "Return JSON only. answer is a short sentence. "
                            "cited_fact_ids is a list of strings. unsupported is boolean."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
                FreeTextDraft,
            )
            assert isinstance(draft.answer, str)
            valid += 1
    finally:
        await client.aclose()
    assert valid == 5
