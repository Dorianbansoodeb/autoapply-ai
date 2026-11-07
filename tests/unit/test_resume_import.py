from __future__ import annotations

from pathlib import Path

import pytest
from docx import Document

from autoapply.llm.client import MockLLMClient
from autoapply.profile.extract import extract_text
from autoapply.profile.import_resume import import_resume, verify_facts
from autoapply.profile.models import today_iso
from autoapply.profile.parse import ResumeExtraction, ExtractedFact
from autoapply.storage import ProfileStore


def _extraction() -> ResumeExtraction:
    return ResumeExtraction(
        full_name="Ada Lovelace",
        email="ada@example.com",
        location="London",
        facts=[
            ExtractedFact(
                type="experience_bullet",
                text="Wrote the first algorithm intended to be executed by a machine, using the Analytical Engine.",
                employer="Analytical Engine Co",
                title="Mathematician",
                start="1842",
                end="1843",
                technologies=["Analytical Engine"],
            ),
            ExtractedFact(
                type="skill",
                text="mathematics, algorithms, technical writing",
                technologies=["mathematics"],
            ),
            ExtractedFact(
                type="experience_bullet",
                text="Increased throughput 40% at FakeCorp using Kubernetes.",
                employer="FakeCorp",
                title="Staff Engineer",
                metrics=["40%"],
                technologies=["Kubernetes"],
            ),
        ],
    )


@pytest.mark.asyncio
async def test_import_round_trip_txt(tmp_path: Path, fixtures_dir: Path) -> None:
    llm = MockLLMClient(_extraction())
    result = await import_resume(fixtures_dir / "ada_resume.txt", llm)
    ids = {fact.id for fact in result.profile.facts}
    texts = " ".join(fact.text for fact in result.profile.facts)
    assert result.profile.full_name == "Ada Lovelace"
    assert result.profile.email == "ada@example.com"
    assert result.profile.verified_facts() == []
    assert "FakeCorp" not in texts
    assert "40%" not in texts
    assert "Analytical Engine" in texts
    assert result.rejected
    assert "exp_001" in ids

    store = ProfileStore(tmp_path / "autoapply.db")
    store.save(result.profile)
    loaded = store.load()
    assert loaded is not None
    assert loaded.email == "ada@example.com"
    verified = verify_facts(loaded, None, today_iso())
    assert all(fact.verified for fact in verified.facts)
    store.save(verified)
    again = store.load()
    assert again is not None
    assert again.verified_facts()


def test_extract_docx(tmp_path: Path, fixtures_dir: Path) -> None:
    src = (fixtures_dir / "ada_resume.txt").read_text(encoding="utf-8")
    path = tmp_path / "resume.docx"
    document = Document()
    for line in src.splitlines():
        document.add_paragraph(line)
    document.save(path)
    text = extract_text(path)
    assert "Ada Lovelace" in text
    assert "ada@example.com" in text


def test_extract_pdf(tmp_path: Path) -> None:
    path = tmp_path / "resume.pdf"
    path.write_bytes(_hello_pdf("Ada Lovelace\nada@example.com\nAnalytical Engine Co"))
    text = extract_text(path)
    assert "Ada Lovelace" in text


def _hello_pdf(payload: str) -> bytes:
    # Minimal one-page PDF with Helvetica text that pypdf can extract.
    escaped = payload.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.1\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    )
    return bytes(out)
