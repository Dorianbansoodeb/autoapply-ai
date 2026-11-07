"""HTML resume → PDF via Playwright Chromium; DOCX via python-docx."""

from __future__ import annotations

from html import escape
from pathlib import Path

from docx import Document
from playwright.async_api import async_playwright

from autoapply.jobs.models import JobPosting
from autoapply.profile.models import CandidateProfile, Fact


def resume_html(
    profile: CandidateProfile,
    job: JobPosting,
    facts: list[Fact],
    texts: dict[str, str],
) -> str:
    bullets = "\n".join(
        f"<li>{escape(texts.get(fact.id, fact.text))}</li>"
        for fact in facts
        if fact.type in {"experience_bullet", "education", "skill"}
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{escape(profile.full_name)} — {escape(job.title)}</title>
<style>
  body {{ font-family: Helvetica, sans-serif; margin: 48px; color: #111; }}
  h1 {{ margin-bottom: 0; font-size: 22px; }}
  p.meta {{ color: #444; margin-top: 4px; }}
  h2 {{ font-size: 14px; border-bottom: 1px solid #ddd; }}
  ul {{ padding-left: 18px; }}
  li {{ margin: 6px 0; }}
</style></head>
<body>
  <h1>{escape(profile.full_name)}</h1>
  <p class="meta">{escape(profile.email)} · tailored for {escape(job.title)} at {escape(job.company)}</p>
  <h2>Experience</h2>
  <ul>{bullets}</ul>
</body></html>
"""


def cover_html(profile: CandidateProfile, job: JobPosting, paragraphs: list[str]) -> str:
    body = "".join(f"<p>{escape(p)}</p>" for p in paragraphs)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Cover letter</title>
<style>body {{ font-family: Helvetica, sans-serif; margin: 48px; line-height: 1.4; }}</style>
</head><body>
<p>{escape(profile.full_name)}<br>{escape(profile.email)}</p>
<p>Hiring team, {escape(job.company)}</p>
<p>Re: {escape(job.title)}</p>
{body}
<p>Sincerely,<br>{escape(profile.full_name)}</p>
</body></html>
"""


async def html_to_pdf(html: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(html, wait_until="load")
        await page.pdf(path=str(dest), format="Letter", print_background=True)
        await browser.close()
    return dest


def write_docx_resume(
    dest: Path,
    profile: CandidateProfile,
    job: JobPosting,
    facts: list[Fact],
    texts: dict[str, str],
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_heading(profile.full_name, level=0)
    document.add_paragraph(f"{profile.email} · {job.title} at {job.company}")
    document.add_heading("Experience", level=1)
    for fact in facts:
        document.add_paragraph(texts.get(fact.id, fact.text), style="List Bullet")
    document.save(dest)
    return dest


def write_docx_cover(
    dest: Path, profile: CandidateProfile, job: JobPosting, paragraphs: list[str]
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_paragraph(f"{profile.full_name}\n{profile.email}")
    document.add_paragraph(f"Hiring team, {job.company}")
    document.add_paragraph(f"Re: {job.title}")
    for para in paragraphs:
        document.add_paragraph(para)
    document.add_paragraph(f"Sincerely,\n{profile.full_name}")
    document.save(dest)
    return dest
