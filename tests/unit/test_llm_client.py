from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from autoapply.cancel import CancelToken
from autoapply.llm.client import LLMCancelled, OpenAICompatClient
from autoapply.llm.schemas import FreeTextDraft
from autoapply.urls import UrlNotAllowed


class HangingTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(30)
        return httpx.Response(200, content=b"{}")


@pytest.mark.asyncio
async def test_cancel_closes_in_flight_stream() -> None:
    client = OpenAICompatClient(
        base_url="http://127.0.0.1:11434/v1",
        transport=HangingTransport(),
        timeout_s=30,
    )
    token = CancelToken()

    async def run() -> None:
        await client.complete(
            [{"role": "user", "content": "hello"}],
            FreeTextDraft,
            cancel=token,
        )

    task = asyncio.create_task(run())
    await asyncio.sleep(0.05)
    token.cancel()
    with pytest.raises(LLMCancelled):
        await task
    await client.aclose()


@pytest.mark.asyncio
async def test_timeout() -> None:
    client = OpenAICompatClient(
        base_url="http://127.0.0.1:11434/v1",
        transport=HangingTransport(),
        timeout_s=0.05,
    )
    with pytest.raises(Exception):
        await client.complete(
            [{"role": "user", "content": "hello"}],
            FreeTextDraft,
        )
    await client.aclose()


def test_rejects_remote_openai_endpoint() -> None:
    with pytest.raises(UrlNotAllowed):
        OpenAICompatClient(base_url="https://api.openai.com/v1")


@pytest.mark.asyncio
async def test_non_stream_json_body() -> None:
    draft = {
        "answer": "Used mathematics at Analytical Engine Co.",
        "cited_fact_ids": ["skill_001"],
        "unsupported": False,
    }
    body = json.dumps({"choices": [{"message": {"content": json.dumps(draft)}}]})

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode())

    client = OpenAICompatClient(
        base_url="http://127.0.0.1:11434/v1",
        transport=httpx.MockTransport(handler),
    )
    result = await client.complete([{"role": "user", "content": "q"}], FreeTextDraft)
    assert result.cited_fact_ids == ["skill_001"]
    await client.aclose()
