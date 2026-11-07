from autoapply.docs.validate import coerce_bullet, unsupported_bits
from autoapply.profile.models import Fact


def _source() -> Fact:
    return Fact(
        id="exp_001",
        type="experience_bullet",
        text="Wrote the first algorithm intended to be executed by a machine, using the Analytical Engine.",
        employer="Analytical Engine Co",
        title="Mathematician",
        technologies=["Analytical Engine"],
        verified=True,
    )


def test_seeded_fabrication_falls_back() -> None:
    source = _source()
    proposed = "Built the Analytical Engine at Analytical Engine Co, reducing runtime by 40%."
    assert unsupported_bits(proposed, source)
    assert coerce_bullet(proposed, source) == source.text


def test_faithful_rewrite_kept() -> None:
    source = _source()
    proposed = "Wrote the first algorithm for a machine using the Analytical Engine."
    assert unsupported_bits(proposed, source) == []
    assert coerce_bullet(proposed, source) == proposed
