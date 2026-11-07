import pytest

from autoapply.urls import UrlNotAllowed, assert_browser_url, assert_localhost_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8765/",
        "http://localhost:8765/apply",
        "https://localhost/form",
        "http://[::1]:9/",
    ],
)
def test_localhost_urls_allowed_for_llm(url: str) -> None:
    assert_localhost_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "https://api.openai.com/v1/chat/completions",
        "https://chatgpt.com/",
        "file:///etc/passwd",
        "http://evil.example/steal",
        "http://user:pass@127.0.0.1/",
        "ftp://127.0.0.1/x",
    ],
)
def test_non_local_urls_denied_for_llm(url: str) -> None:
    with pytest.raises(UrlNotAllowed):
        assert_localhost_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/acme/jobs/1",
        "https://jobs.lever.co/acme/abc",
        "https://jobs.ashbyhq.com/acme/abc",
        "https://acme.wd1.myworkdayjobs.com/en-US/Careers/job/x",
        "http://127.0.0.1:8765/",
    ],
)
def test_job_urls_allowed_for_browser(url: str) -> None:
    assert_browser_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://chatgpt.com/",
        "https://api.openai.com/v1",
        "https://cursor.com/",
        "file:///etc/passwd",
        "http://user:pass@example.com/",
    ],
)
def test_inference_and_file_urls_denied_for_browser(url: str) -> None:
    with pytest.raises(UrlNotAllowed):
        assert_browser_url(url)
