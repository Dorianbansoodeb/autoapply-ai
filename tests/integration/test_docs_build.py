from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from autoapply.docs.build import build_documents
from autoapply.docs.select import BulletRewrite, CoverLetterDraft, FactSelection
from autoapply.jobs.models import load_job
from autoapply.llm.client import MockLLMClient
from autoapply.profile import load_profile


def _handler(messages, schema):
    if schema is FactSelection:
        return FactSelection(fact_ids=["exp_001", "skill_001"])
    if schema is BulletRewrite:
        return BulletRewrite(
            fact_id="exp_001",
            text="Wrote algorithms at Analytical Engine Co, cutting cost 40%.",
        )
    if schema is CoverLetterDraft:
        return CoverLetterDraft(
            paragraphs=[
                "I wrote the first algorithm at Analytical Engine Co using the Analytical Engine."
            ],
            cited_fact_ids=["exp_001"],
        )
    raise AssertionError(schema)


@pytest.mark.asyncio
async def test_build_pdf_and_docx_and_drops_fabrication(
    tmp_path: Path, fixtures_dir: Path
) -> None:
    profile = load_profile(fixtures_dir / "profile.json")
    job = load_job(fixtures_dir / "job.txt")
    llm = MockLLMClient(_handler)
    result = await build_documents(profile, job, llm, out_dir=tmp_path)

    assert Path(result.resume_pdf).is_file()
    assert Path(result.resume_docx).is_file()
    assert Path(result.cover_pdf).is_file()
    text = "".join((page.extract_text() or "") for page in PdfReader(result.resume_pdf).pages)
    assert "Ada Lovelace" in text
    assert "Analytical Engine" in text
    assert "40%" not in text
    assert "Example Co" in text
