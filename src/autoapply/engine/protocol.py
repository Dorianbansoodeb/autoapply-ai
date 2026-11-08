"""JSON-lines engine protocol. UI process talks to this; Playwright stays here."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from autoapply.docs import build_documents
from autoapply.fill import fill_application
from autoapply.hardware import detect_hardware
from autoapply.jobs.eligibility import check_eligibility
from autoapply.jobs.fit import explain_fit
from autoapply.jobs.models import load_job
from autoapply.llm.client import OpenAICompatClient
from autoapply.paths import DEFAULT_DB_PATH, DEFAULT_JSON_PATH, ensure_data_dirs
from autoapply.profile import dump_profile, load_profile, verify_facts
from autoapply.profile.import_resume import import_resume
from autoapply.profile.models import today_iso
from autoapply.secrets_store import list_credential_domains
from autoapply.storage import AnswerBank, JobStore, PolicyStore, PreferenceStore, ProfileStore, Tracker
from autoapply.storage.settings import kill_switch_on, set_kill_switch

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class Engine:
    def __init__(self) -> None:
        ensure_data_dirs()
        self.db = DEFAULT_DB_PATH
        self.profiles = ProfileStore(self.db)
        self.tracker = Tracker(self.db, engine=self.profiles.engine)
        self.policies = PolicyStore(self.db, engine=self.profiles.engine)
        self.jobs = JobStore(self.db, engine=self.profiles.engine)
        self.answers = AnswerBank(self.db, engine=self.profiles.engine)
        self.prefs = PreferenceStore(self.db, engine=self.profiles.engine)

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
            if cmd == "doctor":
                report = detect_hardware()
                return {
                    "ok": True,
                    "os": report.os,
                    "arch": report.arch,
                    "ram_gb": None if report.ram_gb is None else round(report.ram_gb, 1),
                    "tier": report.tier,
                    "message": report.message,
                    "kill_switch": "on" if kill_switch_on(self.db, engine=self.profiles.engine) else "off",
                }
            if cmd == "kill":
                on = bool(message.get("on"))
                set_kill_switch(self.db, on, engine=self.profiles.engine)
                return {"ok": True, "kill_switch": "on" if on else "off"}
            if cmd == "job.add":
                job = load_job(Path(message["path"]))
                row, created = self.jobs.add(job)
                return {
                    "ok": True,
                    "id": row.id,
                    "duplicate": not created,
                    "company": row.company,
                    "title": row.title,
                    "state": row.state,
                }
            if cmd == "applications.record":
                url = message["url"]
                if self.tracker.is_duplicate(url):
                    return {"ok": True, "duplicate": True, "url": url}
                app_id = self.tracker.record_application(
                    company=message.get("company", ""),
                    title=message.get("title", ""),
                    url=url,
                    reference=message.get("reference") or None,
                )
                return {"ok": True, "id": app_id, "state": "submitted_by_user"}
            if cmd == "answers.add":
                self.answers.put(message["question"], message["answer"])
                return {"ok": True}
            if cmd == "credentials.list":
                return {"ok": True, "domains": list_credential_domains()}
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
            fit = await explain_fit(job, profile, elig, llm)
        finally:
            await llm.aclose()
        return {
            "ok": True,
            **built.model_dump(),
            "eligibility": elig.model_dump(),
            "fit": fit.model_dump(),
        }

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
                    saved_prefs=self.prefs.as_dict(),
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
        if result.status == "needs_input":
            self.tracker.note_intervention(run_id, "\n".join(result.notes))
        gate = can_auto_submit(
            policy,
            all_required_from_verified=True,
            has_unreviewed_free_text=bool(result.pending_review) or result.draft is not None,
            has_sensitive_without_saved=False,
            documents_valid=True,
            is_duplicate=self.tracker.is_duplicate(url),
            captcha_or_wall=result.status == "needs_input",
            daily_count=self.tracker.count_today(),
            kill_switch=kill_switch_on(self.db, engine=self.profiles.engine),
        )
        return {
            "ok": True,
            "run_id": run_id,
            "auto_submit_allowed": gate.allowed,
            "auto_submit_reasons": gate.reasons,
            "you_click_submit": True,
            **result.model_dump(),
        }


async def handle_line(engine: Engine, line: str) -> str:
    message = json.loads(line)
    result = await engine.handle(message)
    return json.dumps(result)
