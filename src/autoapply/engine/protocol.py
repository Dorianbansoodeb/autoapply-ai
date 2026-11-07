"""JSON-lines engine protocol. UI process talks to this; Playwright stays here."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from autoapply.docs import build_documents
from autoapply.fill import fill_application
from autoapply.jobs.eligibility import check_eligibility
from autoapply.jobs.models import load_job
from autoapply.llm.client import OpenAICompatClient
from autoapply.paths import DEFAULT_DB_PATH, DEFAULT_JSON_PATH, ensure_data_dirs
from autoapply.profile import dump_profile, load_profile, verify_facts
from autoapply.profile.import_resume import import_resume
from autoapply.profile.models import today_iso
from autoapply.storage import PolicyStore, ProfileStore, Tracker

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Engine:
    def __init__(self) -> None:
        ensure_data_dirs()
        self.db = DEFAULT_DB_PATH
        self.profiles = ProfileStore(self.db)
        self.tracker = Tracker(self.db, engine=self.profiles.engine)
        self.policies = PolicyStore(self.db, engine=self.profiles.engine)

    async def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        cmd = message.get("cmd")
        try:
            if cmd == "ping":
                return {"ok": True, "cmd": cmd}
            if cmd == "recover":
                flipped = self.tracker.recover()
                return {"ok": True, "cmd": cmd, "uncertain_runs": flipped}
            if cmd == "profile.import":
                return await self._import(message)
            if cmd == "profile.verify":
                profile = self.profiles.load()
                if profile is None:
                    return {"ok": False, "error": "no profile"}
                profile = verify_facts(profile, None, today_iso())
                self.profiles.save(profile)
                dump_profile(profile, DEFAULT_JSON_PATH)
                return {"ok": True, "verified": len(profile.verified_facts())}
            if cmd == "docs.build":
                return await self._docs(message)
            if cmd == "fill":
                return await self._fill(message)
            if cmd == "applications":
                rows = self.tracker.applications()
                return {
                    "ok": True,
                    "items": [
                        {
                            "id": r.id,
                            "company": r.company,
                            "title": r.title,
                            "state": r.state,
                            "url": r.url,
                        }
                        for r in rows
                    ],
                }
            return {"ok": False, "error": f"unknown cmd {cmd}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "cmd": cmd, "error": str(exc)}

    async def _import(self, message: dict[str, Any]) -> dict[str, Any]:
        llm = OpenAICompatClient()
        try:
            result = await import_resume(Path(message["path"]), llm)
        finally:
            await llm.aclose()
        self.profiles.save(result.profile)
        dump_profile(result.profile, DEFAULT_JSON_PATH)
        return {
            "ok": True,
            "full_name": result.profile.full_name,
            "kept": result.kept,
            "rejected": len(result.rejected),
        }

    async def _docs(self, message: dict[str, Any]) -> dict[str, Any]:
        profile = load_profile(Path(message["profile"])) if message.get("profile") else self.profiles.load()
        if profile is None:
            return {"ok": False, "error": "no profile"}
        job = load_job(Path(message["job"]))
        elig = check_eligibility(job, profile)
        llm = OpenAICompatClient()
        try:
            built = await build_documents(profile, job, llm, out_dir=Path(message["out"]) if message.get("out") else None)
        finally:
            await llm.aclose()
        return {"ok": True, **built.model_dump(), "eligibility": elig.model_dump()}

    async def _fill(self, message: dict[str, Any]) -> dict[str, Any]:
        from autoapply.browser.manager import BrowserManager
        from autoapply.llm.client import OpenAICompatClient as Client
        from autoapply.policy.autonomy import can_auto_submit

        url = message["url"]
        profile = (
            load_profile(Path(message["profile"]))
            if message.get("profile")
            else self.profiles.load()
        )
        if profile is None:
            return {"ok": False, "error": "no profile"}
        policy = self.policies.for_url(url)
        gate = can_auto_submit(
            policy,
            all_required_from_verified=True,
            has_unreviewed_free_text=True,
            has_sensitive_without_saved=False,
            documents_valid=True,
            is_duplicate=False,
            captcha_or_wall=False,
            daily_count=0,
        )
        run_id = self.tracker.start_run(url)
        llm = Client()
        headed = bool(message.get("headed", True))
        async with BrowserManager(headed=headed) as browser:
            try:
                result = await fill_application(
                    profile=profile,
                    url=url,
                    llm=llm,
                    browser=browser,
                    resume_path=Path(message["resume"]) if message.get("resume") else None,
                )
            finally:
                await llm.aclose()
        self.tracker.set_run_state(
            run_id,
            "ready_for_review" if result.status == "ready_for_review" else result.status,
            notes="\n".join(result.notes),
        )
        if result.submit_clicked:
            self.tracker.set_run_state(run_id, "uncertain", "submit clicked; never auto-retry")
        return {
            "ok": True,
            "run_id": run_id,
            "auto_submit_allowed": gate.allowed,
            "auto_submit_reasons": gate.reasons,
            **result.model_dump(),
        }


async def handle_line(engine: Engine, line: str) -> str:
    message = json.loads(line)
    result = await engine.handle(message)
    return json.dumps(result)
