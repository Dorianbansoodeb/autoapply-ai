"""CLI commands beyond fill/profile/docs: jobs, tracker, kill switch, credentials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from autoapply.hardware import detect_hardware
from autoapply.jobs.ats import fetch_posting
from autoapply.jobs.eligibility import check_eligibility
from autoapply.jobs.models import JobPosting, load_job
from autoapply.paths import DEFAULT_DB_PATH
from autoapply.secrets_store import export_credentials, list_credential_domains
from autoapply.storage import AnswerBank, JobStore, PolicyStore, PreferenceStore, Tracker
from autoapply.storage.settings import kill_switch_on, set_kill_switch


def register(sub: argparse._SubParsersAction) -> None:
    sub.add_parser("doctor", help="Show OS, RAM tier, and local-only reminders")

    job = sub.add_parser("job", help="Save a job from a file or a public ATS URL")
    job_sub = job.add_subparsers(dest="job_command", required=True)
    add = job_sub.add_parser("add", help="Add a job from a JSON or text file")
    add.add_argument("file", type=Path)
    add.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    fetch = job_sub.add_parser("fetch", help="Fetch a Greenhouse, Lever, or Ashby posting")
    fetch.add_argument("url")
    fetch.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    listing = job_sub.add_parser("list", help="List saved jobs")
    listing.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    record = sub.add_parser("record", help="Record an application after you click Submit")
    record.add_argument("--company", required=True)
    record.add_argument("--title", required=True)
    record.add_argument("--url", required=True)
    record.add_argument("--reference", default="")
    record.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    apps = sub.add_parser("applications", help="List recorded applications")
    apps.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    kill = sub.add_parser("kill", help="Turn the auto-submit kill switch on or off")
    kill.add_argument("switch", choices=["on", "off", "status"])
    kill.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    answers = sub.add_parser("answers", help="Save an approved answer for reuse")
    answers_sub = answers.add_subparsers(dest="answers_command", required=True)
    put = answers_sub.add_parser("add")
    put.add_argument("--question", required=True)
    put.add_argument("--answer", required=True)
    put.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    pref = sub.add_parser("pref", help="Save a preference so the agent can reuse it")
    pref_sub = pref.add_subparsers(dest="pref_command", required=True)
    set_pref = pref_sub.add_parser("set")
    set_pref.add_argument("--key", required=True)
    set_pref.add_argument("--value", required=True)
    set_pref.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    policy = sub.add_parser("policy", help="Show or review a site policy")
    policy_sub = policy.add_subparsers(dest="policy_command", required=True)
    show = policy_sub.add_parser("show")
    show.add_argument("url")
    show.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    review = policy_sub.add_parser("review", help="Allowlist a non-Workday site for later promotion")
    review.add_argument("url")
    review.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    creds = sub.add_parser("credentials", help="Export tenant passwords you stored in the OS keychain")
    creds_sub = creds.add_subparsers(dest="credentials_command", required=True)
    creds_sub.add_parser("list")
    export = creds_sub.add_parser("export")
    export.add_argument("--out", type=Path, required=True)


def dispatch(args: argparse.Namespace) -> int | None:
    command = args.command
    if command == "doctor":
        report = detect_hardware()
        print(
            json.dumps(
                {
                    "os": report.os,
                    "arch": report.arch,
                    "ram_gb": None if report.ram_gb is None else round(report.ram_gb, 1),
                    "tier": report.tier,
                    "message": report.message,
                    "llm": "localhost only",
                    "submit": "you click Submit",
                },
                indent=2,
            )
        )
        return 0
    if command == "job":
        return _job(args)
    if command == "record":
        tracker = Tracker(args.db)
        if tracker.is_duplicate(args.url):
            print(json.dumps({"duplicate": True, "url": args.url}))
            return 0
        app_id = tracker.record_application(
            company=args.company,
            title=args.title,
            url=args.url,
            reference=args.reference or None,
        )
        print(json.dumps({"id": app_id, "state": "submitted_by_user"}))
        return 0
    if command == "applications":
        rows = Tracker(args.db).applications()
        print(
            json.dumps(
                [
                    {"id": row.id, "company": row.company, "title": row.title, "state": row.state, "url": row.url}
                    for row in rows
                ],
                indent=2,
            )
        )
        return 0
    if command == "kill":
        if args.switch == "status":
            print(json.dumps({"kill_switch": "on" if kill_switch_on(args.db) else "off"}))
            return 0
        on = args.switch == "on"
        set_kill_switch(args.db, on)
        print(json.dumps({"kill_switch": "on" if on else "off"}))
        return 0
    if command == "answers":
        AnswerBank(args.db).put(args.question, args.answer)
        print(json.dumps({"saved": args.question}))
        return 0
    if command == "pref":
        PreferenceStore(args.db).set(args.key, args.value)
        print(json.dumps({"saved": args.key}))
        return 0
    if command == "policy":
        store = PolicyStore(args.db)
        row = store.mark_reviewed(args.url) if args.policy_command == "review" else store.for_url(args.url)
        print(
            json.dumps(
                {
                    "host": row.host,
                    "mode": row.mode,
                    "allow_auto_submit": row.allow_auto_submit,
                    "clean_runs": row.clean_runs,
                    "notes": row.notes,
                },
                indent=2,
            )
        )
        return 0
    if command == "credentials":
        if args.credentials_command == "list":
            print(json.dumps({"domains": list_credential_domains()}, indent=2))
            return 0
        rows = export_credentials()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "wrote": str(args.out),
                    "count": len(rows),
                    "warning": "This file contains passwords. Delete it when you are done.",
                }
            )
        )
        return 0
    return None


def _job(args: argparse.Namespace) -> int:
    store = JobStore(args.db)
    if args.job_command == "list":
        print(
            json.dumps(
                [
                    {
                        "id": row.id,
                        "company": row.company,
                        "title": row.title,
                        "state": row.state,
                        "url": row.application_url,
                    }
                    for row in store.list_jobs()
                ],
                indent=2,
            )
        )
        return 0
    if args.job_command == "add":
        job = load_job(args.file)
    else:
        job = fetch_posting(args.url)
    return _save_job(store, job)


def _save_job(store: JobStore, job: JobPosting) -> int:
    row, created = store.add(job)
    if not created:
        print(json.dumps({"duplicate": True, "id": row.id, "state": row.state}))
        return 0
    print(json.dumps({"id": row.id, "company": row.company, "title": row.title, "state": row.state}))
    return 0


def eligibility_for(job: JobPosting, profile) -> dict:
    result = check_eligibility(job, profile)
    return result.model_dump()
