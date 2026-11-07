from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from autoapply.cancel import CancelToken
from autoapply.docs.render import (
    cover_html,
    html_to_pdf,
    resume_html,
    write_docx_cover,
    write_docx_resume,
)
from autoapply.docs.select import draft_cover_letter, rewrite_bullets, select_facts
from autoapply.jobs.models import JobPosting
from autoapply.llm.client import LLMClient
from autoapply.paths import DOCUMENTS_DIR
from autoapply.profile.models import CandidateProfile


class BuildResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_pdf: str
    resume_docx: str
    cover_pdf: str
    cover_docx: str
    fact_ids: list[str]


async def build_documents(
    profile: CandidateProfile,
    job: JobPosting,
    llm: LLMClient,
    out_dir: Path | None = None,
    *,
    cancel: CancelToken | None = None,
) -> BuildResult:
    dest = out_dir or (DOCUMENTS_DIR / job.company.replace(" ", "_"))
    dest.mkdir(parents=True, exist_ok=True)
    facts = await select_facts(job, profile, llm, cancel=cancel)
    texts = await rewrite_bullets(job, facts, llm, cancel=cancel)
    cover = await draft_cover_letter(job, facts, profile, llm, cancel=cancel)

    resume_pdf = dest / "resume.pdf"
    resume_docx = dest / "resume.docx"
    cover_pdf = dest / "cover_letter.pdf"
    cover_docx = dest / "cover_letter.docx"

    html = resume_html(profile, job, facts, texts)
    await html_to_pdf(html, resume_pdf)
    write_docx_resume(resume_docx, profile, job, facts, texts)
    await html_to_pdf(cover_html(profile, job, cover.paragraphs), cover_pdf)
    write_docx_cover(cover_docx, profile, job, cover.paragraphs)

    return BuildResult(
        resume_pdf=str(resume_pdf),
        resume_docx=str(resume_docx),
        cover_pdf=str(cover_pdf),
        cover_docx=str(cover_docx),
        fact_ids=[fact.id for fact in facts],
    )
