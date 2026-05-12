"""Job posting crawler 공통 헬퍼.

각 fetcher 모듈은 `def fetch() -> list[dict]` 시그니처를 따름.

Returned dict keys (data/README.md `job_posting.csv` 스펙과 1:1):
- job_id: str       ("" placeholder — mapping/map_postings.py 가 추후 채움)
- source: str       ("Greenhouse:krafton", "NaverCareers" 등)
- posting_url: str
- raw_text: str     (본문 전체 평문, HTML 제거)
- crawled_at: str   (ISO 8601 UTC)
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Protocol

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "HongikCapstone-CourseFit/0.1 "
    "(+https://github.com/IE-graduation-project/course-fit)"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT_SEC = 15
REQUEST_INTERVAL_SEC = 1.5


class JobPostingFetcher(Protocol):
    def fetch(self) -> list[dict]: ...


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = REQUEST_TIMEOUT_SEC,
) -> requests.Response:
    final_headers = {**DEFAULT_HEADERS, **(headers or {})}
    resp = requests.get(url, params=params, headers=final_headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def polite_sleep(seconds: float = REQUEST_INTERVAL_SEC) -> None:
    time.sleep(seconds)


def html_to_text(html: str) -> str:
    """HTML → 줄바꿈 보존된 평문. 공고 본문 추출용."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def make_record(
    *,
    source: str,
    posting_url: str,
    raw_text: str,
    job_id: str = "",
    crawled_at: str | None = None,
) -> dict:
    """job_posting.csv 한 행 dict."""
    return {
        "job_id": job_id,
        "source": source,
        "posting_url": posting_url,
        "raw_text": raw_text,
        "crawled_at": crawled_at or now_iso_utc(),
    }
