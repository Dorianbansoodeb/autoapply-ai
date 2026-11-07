"""Engine subprocess: JSON lines on stdin/stdout."""

from __future__ import annotations

import asyncio
import sys

from autoapply.engine.protocol import Engine, handle_line


async def run() -> None:
    engine = Engine()
    engine.tracker.recover()
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        reply = await handle_line(engine, line)
        print(reply, flush=True)


def main() -> None:
    asyncio.run(run())
