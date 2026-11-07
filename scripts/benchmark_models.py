#!/usr/bin/env python3
"""Measure tokens/sec and RAM for local Ollama models.

Does not download models. Run after you have pulled the approved weights:

    ollama pull phi3.5:3.8b          # MIT, ~2.2 GB
    ollama pull qwen2.5:7b-instruct  # Apache-2.0, ~4.7 GB

    uv run python scripts/benchmark_models.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
DEFAULT_MODELS = ["phi3.5:3.8b", "qwen2.5:7b-instruct"]
PROMPT = (
    "Reply with JSON only matching "
    '{"answer": string, "cited_fact_ids": [string], "unsupported": boolean}. '
    "Why do you want this internship? Use only this fact: "
    "id=exp_001 Ada wrote the first machine algorithm at Analytical Engine Co."
)


def ollama_json(path: str, payload: dict | None = None, timeout: int = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def rss_mb(pid: int) -> float:
    out = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True)
    return int(out.strip()) / 1024.0


def ollama_pids() -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", "ollama"], text=True)
    except subprocess.CalledProcessError:
        return []
    return [int(line) for line in out.splitlines() if line.strip().isdigit()]


def benchmark(model: str) -> dict:
    started = time.perf_counter()
    body = ollama_json(
        "/api/chat",
        {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "cited_fact_ids": {"type": "array", "items": {"type": "string"}},
                    "unsupported": {"type": "boolean"},
                },
                "required": ["answer", "cited_fact_ids", "unsupported"],
            },
        },
    )
    wall_s = time.perf_counter() - started
    eval_count = int(body.get("eval_count") or 0)
    eval_ns = int(body.get("eval_duration") or 0)
    prompt_count = int(body.get("prompt_eval_count") or 0)
    prompt_ns = int(body.get("prompt_eval_duration") or 0)
    gen_tps = (eval_count / (eval_ns / 1e9)) if eval_ns else None
    prompt_tps = (prompt_count / (prompt_ns / 1e9)) if prompt_ns else None
    pids = ollama_pids()
    ram = sum(rss_mb(pid) for pid in pids) if pids else None
    content = body.get("message", {}).get("content", "")
    schema_ok = False
    try:
        parsed = json.loads(content)
        schema_ok = (
            isinstance(parsed, dict)
            and isinstance(parsed.get("answer"), str)
            and isinstance(parsed.get("cited_fact_ids"), list)
            and isinstance(parsed.get("unsupported"), bool)
        )
    except json.JSONDecodeError:
        schema_ok = False
    return {
        "model": model,
        "wall_seconds": round(wall_s, 2),
        "prompt_tokens": prompt_count,
        "eval_tokens": eval_count,
        "prompt_tokens_per_sec": round(prompt_tps, 2) if prompt_tps else None,
        "eval_tokens_per_sec": round(gen_tps, 2) if gen_tps else None,
        "ollama_rss_mb": round(ram, 1) if ram is not None else None,
        "schema_valid": schema_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--out", type=Path, default=Path("docs/benchmarks-m0.json"))
    args = parser.parse_args()
    try:
        ollama_json("/api/tags")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Ollama is not reachable at {OLLAMA}. Start it with `ollama serve`. ({exc})"
        ) from exc

    rows = []
    for model in args.models:
        print(f"benchmarking {model} ...")
        row = benchmark(model)
        print(json.dumps(row, indent=2))
        rows.append(row)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
