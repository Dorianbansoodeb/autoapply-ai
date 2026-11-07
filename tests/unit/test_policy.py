from autoapply.policy.gate import may_auto_fill, page_looks_like_assessment
from autoapply.questions.classify import QuestionClass, classify_label


def test_sensitive_questions_are_class_e() -> None:
    assert classify_label("Do you have a disability?") is QuestionClass.SENSITIVE
    assert classify_label("Are you a veteran?") is QuestionClass.SENSITIVE
    assert not may_auto_fill("Social Security Number")


def test_assessment_is_handed_off() -> None:
    assert classify_label("Complete this HackerRank assessment") is QuestionClass.ASSESSMENT
    assert page_looks_like_assessment("Welcome to your Codility timed test")


def test_cover_letter_is_behavioral() -> None:
    assert classify_label("Why do you want this role?") is QuestionClass.BEHAVIORAL
    assert may_auto_fill("Why do you want this role?")
