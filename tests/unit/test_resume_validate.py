from pathlib import Path

from autoapply.profile.ids import assign_ids
from autoapply.profile.models import Fact
from autoapply.profile.validate import filter_facts, validate_fact

SOURCE = (Path(__file__).resolve().parents[1] / "fixtures" / "ada_resume.txt").read_text(
    encoding="utf-8"
)


def _fact(**kwargs) -> Fact:
    base = dict(
        id="tmp",
        type="experience_bullet",
        text="Wrote the first algorithm intended to be executed by a machine, using the Analytical Engine.",
        employer="Analytical Engine Co",
        title="Mathematician",
        start="1842",
        end="1843",
        technologies=["Analytical Engine"],
        metrics=[],
        verified=False,
    )
    base.update(kwargs)
    return Fact.model_validate(base)


def test_supported_bullet_is_kept() -> None:
    assert validate_fact(_fact(), SOURCE) == []


def test_fabricated_metric_is_rejected() -> None:
    fact = _fact(text="Wrote algorithms, reducing runtime by 40%.", metrics=["40%"])
    assert validate_fact(fact, SOURCE)


def test_fabricated_employer_is_rejected() -> None:
    fact = _fact(employer="MIT")
    assert any("employer" in reason for reason in validate_fact(fact, SOURCE))


def test_fabricated_degree_is_rejected() -> None:
    fact = _fact(
        type="education",
        text="PhD in Computer Science from MIT, 2019",
        employer="MIT",
        title="PhD",
        start="2019",
        technologies=[],
    )
    kept, rejected = filter_facts(assign_ids([fact]), SOURCE)
    assert kept == []
    assert rejected
