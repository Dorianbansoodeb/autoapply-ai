"""Public Greenhouse, Lever, and Ashby posting fetch. No profile data leaves the machine."""

from __future__ import annotations

import re
from collections.abc import Callable
from urllib.parse import urlparse

from autoapply.jobs.models import JobPosting
from autoapply.urls import UrlNotAllowed

_TAG = re.compile(r"<[^>]+>")

ALLOWED_ATS_HOSTS = frozenset(
    {
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "boards-api.greenhouse.io",
        "jobs.lever.co",
        "api.lever.co",
        "jobs.ashbyhq.com",
        "api.ashbyhq.com",
    }
)


def _strip_html(value: str) -> str:
    text = _TAG.sub(" ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def detect_ats(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    if "myworkdayjobs.com" in host or host.endswith("workday.com"):
        return "workday"
    return "unknown"


def assert_ats_fetch_url(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_ATS_HOSTS:
        raise UrlNotAllowed(
            f"job fetch only allows Greenhouse, Lever, and Ashby hosts; got {host!r}"
        )


def _parts(url: str) -> list[str]:
    return [part for part in urlparse(url).path.split("/") if part]


def api_url_for(url: str) -> str:
    """Map a public posting URL to the vendor's read-only JSON API."""
    assert_ats_fetch_url(url)
    kind = detect_ats(url)
    parts = _parts(url)
    if kind == "greenhouse":
        if "jobs" not in parts:
            raise UrlNotAllowed("Greenhouse URL is missing a job id")
        board = parts[0]
        job_id = parts[parts.index("jobs") + 1]
        return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    if kind == "lever":
        if len(parts) < 2:
            raise UrlNotAllowed("Lever URL is missing a posting id")
        site, posting = parts[0], parts[1]
        return f"https://api.lever.co/v0/postings/{site}/{posting}"
    if len(parts) < 1:
        raise UrlNotAllowed("Ashby URL is missing a board")
    return f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}?includeCompensation=true"


def parse_greenhouse(payload: dict, page_url: str = "") -> JobPosting:
    location = payload.get("location") or {}
    loc_name = location.get("name", "") if isinstance(location, dict) else str(location)
    content = _strip_html(str(payload.get("content") or payload.get("description") or ""))
    return JobPosting(
        company=str(payload.get("company_name") or payload.get("company") or "Unknown company"),
        title=str(payload.get("title") or "Unknown role"),
        location=loc_name,
        description=content,
        application_url=str(payload.get("absolute_url") or page_url),
        job_id=str(payload.get("id") or ""),
        requisition_id=str(payload.get("requisition_id") or ""),
        ats_type="greenhouse",
        source="greenhouse",
    )


def parse_lever(payload: dict, page_url: str = "") -> JobPosting:
    categories = payload.get("categories") or {}
    return JobPosting(
        company=str(payload.get("company") or categories.get("team") or "Unknown company"),
        title=str(payload.get("text") or payload.get("title") or "Unknown role"),
        location=str(categories.get("location") or ""),
        employment_type=str(categories.get("commitment") or ""),
        description=_strip_html(str(payload.get("descriptionPlain") or payload.get("description") or "")),
        application_url=str(payload.get("hostedUrl") or page_url),
        job_id=str(payload.get("id") or ""),
        ats_type="lever",
        source="lever",
    )


def parse_ashby(payload: dict, page_url: str = "") -> JobPosting:
    jobs = payload.get("jobs")
    chosen = payload
    if isinstance(jobs, list):
        wanted = _parts(page_url)[-1] if page_url else ""
        chosen = next((job for job in jobs if str(job.get("id")) == wanted), jobs[0] if jobs else {})
    compensation = chosen.get("compensation") or {}
    return JobPosting(
        company=str(payload.get("organizationName") or chosen.get("company") or "Unknown company"),
        title=str(chosen.get("title") or "Unknown role"),
        location=str(chosen.get("location") or ""),
        employment_type=str(chosen.get("employmentType") or ""),
        description=_strip_html(
            str(chosen.get("descriptionPlain") or chosen.get("descriptionHtml") or "")
        ),
        application_url=str(chosen.get("jobUrl") or page_url),
        job_id=str(chosen.get("id") or ""),
        salary_min=_money(compensation.get("min")),
        salary_max=_money(compensation.get("max")),
        ats_type="ashby",
        source="ashby",
    )


def _money(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def posting_from_response(page_url: str, payload: dict) -> JobPosting:
    kind = detect_ats(page_url)
    if kind == "greenhouse":
        return parse_greenhouse(payload, page_url)
    if kind == "lever":
        return parse_lever(payload, page_url)
    if kind == "ashby":
        return parse_ashby(payload, page_url)
    raise UrlNotAllowed(f"no public posting API for {page_url}")


def fetch_posting(url: str, get: Callable[[str], dict] | None = None) -> JobPosting:
    """Fetch one posting. `get` is injectable so tests never touch the network."""
    api = api_url_for(url)
    if get is None:
        import httpx

        response = httpx.get(api, timeout=30.0, follow_redirects=True)
        response.raise_for_status()
        payload = response.json()
    else:
        payload = get(api)
    return posting_from_response(url, payload)
