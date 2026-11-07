#!/usr/bin/env python3
"""Run 50 prompts against a local model and report schema-validity rate.

    AUTOAPPLY_MODEL=phi3.5:3.8b uv run python scripts/eval_schema.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from autoapply.llm.client import OpenAICompatClient, SchemaValidationError
from autoapply.llm.schemas import FreeTextDraft
from tests.fixtures.prompts import SCHEMA_PROMPTS


async def run(model: str) -> dict:
    client = OpenAICompatClient(model=model)
    ok = 0
    failures: list[dict] = []
    started = time.perf_counter()
    try:
        for i, question in enumerate(SCHEMA_PROMPTS, start=1):
            t0 = time.perf_counter()
            try:
                draft = await client.complete(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Return JSON only with keys answer (string), "
                                "cited_fact_ids (array of strings), unsupported (boolean). "
                                "Use only this fact: id=exp_001 Ada wrote the first "
                                "machine algorithm at Analytical Engine Co."
                            ),
                        },
                        {"role": "user", "content": question},
                    ],
                    FreeTextDraft,
                )
                ok += 1
                status = "ok"
                detail = draft.answer[:80]
            except (SchemaValidationError, Exception) as exc:  # noqa: BLE001
                status = "fail"
                detail = str(exc)[:200]
                failures.append({"n": i, "question": question, "error": detail})
            print(
                f"{i:02d}/{len(SCHEMA_PROMPTS)} {status} {(time.perf_counter() - t0):.1f}s {detail}",
                flush=True,
            )
    finally:
        await client.aclose()
    return {
        "model": model,
        "n": len(SCHEMA_PROMPTS),
        "valid": ok,
        "valid_rate": ok / len(SCHEMA_PROMPTS),
        "seconds": round(time.perf_counter() - started, 1),
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        default=os.environ.get("AUTOAPPLY_MODEL", "phi3.5:3.8b"),
    )
    args = parser.parse_args()
    summary = asyncio.run(run(args.model))
    print(json.dumps({k: v for k, v in summary.items() if k != "failures"}, indent=2))
    if summary["failures"]:
        print("failures:")
        print(json.dumps(summary["failures"], indent=2))
    raise SystemExit(0 if summary["valid"] == summary["n"] else 1)


if __name__ == "__main__":
    main()
