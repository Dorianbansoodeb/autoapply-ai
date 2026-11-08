"""CLI. GUI comes later."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from autoapply import __version__
from autoapply.browser.manager import DEFAULT_BROWSER_PROFILE, BrowserManager
from autoapply.cancel import CancelledError, CancelToken
from autoapply.fill import fill_application
from autoapply.llm.client import DEFAULT_LLM_BASE_URL, DEFAULT_MODEL, OpenAICompatClient
from autoapply.paths import DEFAULT_DB_PATH, DEFAULT_JSON_PATH, ensure_data_dirs
from autoapply.docs import build_documents
from autoapply.jobs.models import load_job
from autoapply.profile import dump_profile, load_profile, verify_facts
from autoapply.profile.import_resume import import_resume
from autoapply.profile.models import today_iso
from autoapply.storage import ProfileStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoapply",
        description="Prepare and assist with job applications. Never auto-submits.",
    )
    parser.add_argument("--version", action="version", version=f"autoapply {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    fill = sub.add_parser(
        "fill",
        help="Fill an application form and stop before Submit",
    )
    fill.add_argument("--profile", type=Path, default=None, help="Path to profile JSON")
    fill.add_argument("--url", required=True, help="Application URL (you click Submit)")
    fill.add_argument("--resume", type=Path, default=None, help="File to upload")
    _add_llm_args(fill)
    fill.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser headless (tests). Default is headed.",
    )
    fill.add_argument(
        "--browser-profile",
        type=Path,
        default=DEFAULT_BROWSER_PROFILE,
        help="Persistent Playwright profile directory",
    )
    fill.add_argument(
        "--keep-open",
        action="store_true",
        help="Leave the headed browser open so you can click Submit yourself",
    )
    fill.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)

    profile = sub.add_parser("profile", help="Import and review the atomic profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)

    imp = profile_sub.add_parser("import", help="Import a resume into unverified facts")
    imp.add_argument("resume", type=Path)
    _add_llm_args(imp)
    imp.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    imp.add_argument("--json", type=Path, default=DEFAULT_JSON_PATH)

    show = profile_sub.add_parser("show", help="List stored facts")
    show.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    show.add_argument("--json", type=Path, default=None)

    ver = profile_sub.add_parser("verify", help="Mark facts as verified after you review them")
    ver.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    ver.add_argument("--json", type=Path, default=DEFAULT_JSON_PATH)
    ver.add_argument("--all", action="store_true")
    ver.add_argument("--id", action="append", dest="ids", default=None)

    docs = sub.add_parser("docs", help="Build a tailored resume and cover letter")
    docs_sub = docs.add_subparsers(dest="docs_command", required=True)
    build = docs_sub.add_parser("build", help="Select facts, validate, write PDF and DOCX")
    build.add_argument("--job", required=True, type=Path, help="Job JSON or text file")
    build.add_argument("--profile", type=Path, default=None)
    build.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    build.add_argument("--out", type=Path, default=None)
    _add_llm_args(build)

    sub.add_parser("engine", help="JSON-lines engine process for the GUI")
    sub.add_parser("gui", help="Open the desktop UI (PySide6)")
    rec = sub.add_parser("recover", help="Mark crashed submitting runs as uncertain")
    rec.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    from autoapply.product_cli import register

    register(sub)

    return parser


def _add_llm_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Local model name")
    parser.add_argument(
        "--llm-url",
        default=DEFAULT_LLM_BASE_URL,
        help="OpenAI-compatible local endpoint (localhost only)",
    )


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "fill":
        raise SystemExit(asyncio.run(_cmd_fill(args)))
    if args.command == "profile":
        if args.profile_command == "import":
            raise SystemExit(asyncio.run(_cmd_profile_import(args)))
        if args.profile_command == "show":
            raise SystemExit(_cmd_profile_show(args))
        if args.profile_command == "verify":
            raise SystemExit(_cmd_profile_verify(args))
    if args.command == "docs":
        if args.docs_command == "build":
            raise SystemExit(asyncio.run(_cmd_docs_build(args)))
    if args.command == "engine":
        from autoapply.engine.server import main as engine_main

        engine_main()
        return
    if args.command == "gui":
        from autoapply.ui.app import main as gui_main

        gui_main()
        return
    if args.command == "recover":
        from autoapply.storage import Tracker

        flipped = Tracker(args.db).recover()
        print(json.dumps({"uncertain_runs": flipped}))
        return
    from autoapply.product_cli import dispatch

    handled = dispatch(args)
    if handled is not None:
        raise SystemExit(handled)
    parser.error(f"unknown command {args.command}")


def _load_profile_from_args(args: argparse.Namespace):
    if getattr(args, "profile", None):
        return load_profile(args.profile)
    store = ProfileStore(args.db)
    profile = store.load()
    if profile is None:
        raise FileNotFoundError(
            "no profile found; run `autoapply profile import RESUME` or pass --profile"
        )
    return profile


async def _cmd_fill(args: argparse.Namespace) -> int:
    try:
        profile = _load_profile_from_args(args)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1
    llm = OpenAICompatClient(base_url=args.llm_url, model=args.model)
    token = CancelToken()
    headed = not args.headless
    keep_open = args.keep_open or headed
    async with BrowserManager(profile_dir=args.browser_profile, headed=headed) as browser:
        try:
            result = await fill_application(
                profile=profile,
                url=args.url,
                llm=llm,
                browser=browser,
                resume_path=args.resume,
                cancel=token,
            )
        except CancelledError:
            print("Fill cancelled. Submit was not clicked.", file=sys.stderr)
            return 130
        except Exception as exc:  # noqa: BLE001
            print(f"Fill failed: {exc}", file=sys.stderr)
            return 1
        finally:
            await llm.aclose()

        print(json.dumps(result.model_dump(), indent=2))
        if result.submit_clicked:
            print("ERROR: Submit was clicked. This is a bug.", file=sys.stderr)
            return 2
        if keep_open and headed:
            print(
                "\nBrowser is still open. Review the form, click Submit yourself if you "
                "want, then press Enter to close the browser.",
                file=sys.stderr,
            )
            await asyncio.to_thread(input)
        return 0 if result.status in {"ready_for_review", "needs_input"} else 1


async def _cmd_profile_import(args: argparse.Namespace) -> int:
    ensure_data_dirs()
    llm = OpenAICompatClient(base_url=args.llm_url, model=args.model)
    try:
        result = await import_resume(args.resume, llm)
    except Exception as exc:  # noqa: BLE001
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await llm.aclose()

    store = ProfileStore(args.db)
    store.save(result.profile)
    dump_profile(result.profile, args.json)
    print(
        json.dumps(
            {
                "full_name": result.profile.full_name,
                "email": result.profile.email,
                "kept": result.kept,
                "rejected": result.rejected,
                "unverified": len(result.profile.facts),
                "db": str(args.db),
                "json": str(args.json),
                "note": "Facts are unverified. Review with `autoapply profile show`, then `autoapply profile verify --all`.",
            },
            indent=2,
        )
    )
    return 0


def _cmd_profile_show(args: argparse.Namespace) -> int:
    if args.json:
        profile = load_profile(args.json)
    else:
        profile = ProfileStore(args.db).load()
    if profile is None:
        print("no profile stored yet", file=sys.stderr)
        return 1
    print(f"{profile.full_name}  <{profile.email}>")
    for fact in profile.facts:
        mark = "x" if fact.verified else " "
        bits = [f"[{mark}]", fact.id, fact.type, fact.text]
        print("  " + "  ".join(bits))
    unverified = sum(1 for fact in profile.facts if not fact.verified)
    print(f"{unverified} unverified / {len(profile.facts)} total")
    return 0


def _cmd_profile_verify(args: argparse.Namespace) -> int:
    store = ProfileStore(args.db)
    profile = store.load()
    if profile is None:
        print("no profile stored yet", file=sys.stderr)
        return 1
    if not args.all and not args.ids:
        print("pass --all or --id FACT_ID", file=sys.stderr)
        return 1
    profile = verify_facts(profile, None if args.all else args.ids, today_iso())
    store.save(profile)
    dump_profile(profile, args.json)
    print(f"verified {len(profile.verified_facts())}/{len(profile.facts)} facts")
    return 0


async def _cmd_docs_build(args: argparse.Namespace) -> int:
    try:
        profile = _load_profile_from_args(args)
        job = load_job(args.job)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    llm = OpenAICompatClient(base_url=args.llm_url, model=args.model)
    try:
        result = await build_documents(profile, job, llm, out_dir=args.out)
        from autoapply.jobs.eligibility import check_eligibility
        from autoapply.jobs.fit import explain_fit

        eligibility = check_eligibility(job, profile)
        fit = await explain_fit(profile=profile, job=job, eligibility=eligibility, llm=llm)
    except Exception as exc:  # noqa: BLE001
        print(f"Document build failed: {exc}", file=sys.stderr)
        return 1
    finally:
        await llm.aclose()
    payload = result.model_dump()
    payload["eligibility"] = eligibility.model_dump()
    payload["fit"] = fit.model_dump()
    print(json.dumps(payload, indent=2))
    return 0
