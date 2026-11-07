"""50 prompts → schema-valid JSON, using a local mock HTTP server."""

from __future__ import annotations

import json

import httpx
import pytest

from autoapply.llm.client import OpenAICompatClient, SchemaValidationError, json_schema_for
from autoapply.llm.schemas import FreeTextDraft
from tests.fixtures.prompts import SCHEMA_PROMPTS


def _sse_completion(obj: dict) -> bytes:
    chunk = {"choices": [{"delta": {"content": json.dumps(obj)}}]}
    return f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n".encode()


@pytest.mark.asyncio
async def test_fifty_prompts_produce_valid_schema() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen.append(payload["messages"][-1]["content"])
        draft = {
            "answer": "I wrote the first algorithm at Analytical Engine Co.",
            "cited_fact_ids": ["exp_001"],
            "unsupported": False,
        }
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=_sse_completion(draft),
        )

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:11434/v1",
        transport=httpx.MockTransport(handler),
    )
    try:
        for question in SCHEMA_PROMPTS:
            messages = [
                {"role": "system", "content": "Draft JSON only from facts."},
                {"role": "user", "content": question},
            ]
            result = await client.complete(messages, FreeTextDraft)
            assert isinstance(result, FreeTextDraft)
            assert result.answer
            FreeTextDraft.model_validate(result.model_dump())
    finally:
        await client.aclose()

    assert len(seen) == 50
    assert len(SCHEMA_PROMPTS) == 50


@pytest.mark.asyncio
async def test_invalid_json_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        chunk = {"choices": [{"delta": {"content": "not-json"}}]}
        body = f"data: {json.dumps(chunk)}\n\ndata: [DONE]\n".encode()
        return httpx.Response(200, content=body)

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:9/v1",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SchemaValidationError):
        await client.complete(
            [{"role": "user", "content": "hi"}],
            FreeTextDraft,
        )
    await client.aclose()


def test_schema_forbids_extra_fields() -> None:
    schema = json_schema_for(FreeTextDraft)
    assert schema.get("additionalProperties") is False
    with pytest.raises(Exception):
        FreeTextDraft.model_validate(
            {
                "answer": "x",
                "cited_fact_ids": [],
                "unsupported": False,
                "ssn": "000-00-0000",
            }
        )
