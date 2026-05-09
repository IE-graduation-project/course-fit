"""Ashby Public Job Posting API fetcher (한국 회사 통합).

대상 (한국 본사·법인 한정):
    1. 포티투닷 (42dot)        — 현대차 AI/자율주행, ~118건 (Pangyo 다수)
    2. 퓨리오사AI (furiosa-ai) — AI 반도체, ~48건 (Seoul HQ)
    3. Twelve Labs (twelve-labs) — Video AI, ~44건 (Seoul + SF)

Ashby Public API:
    https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true
- 무인증 GET, 공식 public job board API.
- 응답 schema: {"apiVersion": ..., "jobs": [{id,title,department,team,
  location,employmentType,jobUrl,descriptionHtml, ...}]}.

스펙 노트:
    PRD 에는 departmentName/teamName/locationName 키로 적혀 있지만 실제 응답은
    department/team/location 이라 후자에 맞춰 파싱한다.

각 공고 dict 는 `make_record()` 로 생성되어 `data/job_posting.csv` 의
컬럼 (job_id/source/posting_url/raw_text/crawled_at) 과 1:1 매핑된다.
"""
from __future__ import annotations

import sys
from typing import Any

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


# slug -> 표시용 한글명 (검증: HTTP 200 + jobs 배열 비어있지 않음)
COMPANIES: dict[str, str] = {
    "42dot": "포티투닷",
    "furiosa-ai": "퓨리오사AI",
    "twelve-labs": "Twelve Labs",
}

API_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
MIN_RAW_TEXT_LEN = 100


def _str(value: Any) -> str:
    """None/non-str safely → trimmed str."""
    if isinstance(value, str):
        return value.strip()
    return ""


def _build_raw_text(job: dict, company_kr: str) -> str:
    title = _str(job.get("title"))
    dept = _str(job.get("department")) or _str(job.get("departmentName"))
    team = _str(job.get("team")) or _str(job.get("teamName"))
    loc = _str(job.get("location")) or _str(job.get("locationName"))
    emp = _str(job.get("employmentType"))

    header_lines = [f"[{company_kr}] {title}".strip()]
    if dept:
        header_lines.append(f"부서: {dept}")
    if team:
        header_lines.append(f"팀: {team}")
    if loc:
        header_lines.append(f"위치: {loc}")
    if emp:
        header_lines.append(f"고용: {emp}")
    header = "\n".join(header_lines)

    body = html_to_text(_str(job.get("descriptionHtml")))
    combined = f"{header}\n\n{body}".strip() if body else header

    if len(combined) < MIN_RAW_TEXT_LEN:
        plain = _str(job.get("descriptionPlain"))
        if plain:
            combined = f"{header}\n\n{plain}".strip()

    return combined


def _posting_url(job: dict, slug: str) -> str:
    url = _str(job.get("jobUrl"))
    if url:
        return url
    apply_url = _str(job.get("applyUrl"))
    if apply_url:
        return apply_url
    job_id = _str(job.get("id"))
    if job_id:
        return f"https://jobs.ashbyhq.com/{slug}/{job_id}"
    return ""


def _fetch_company(slug: str, company_kr: str) -> list[dict]:
    url = API_TEMPLATE.format(slug=slug)
    resp = http_get(url, params={"includeCompensation": "true"})
    payload: dict[str, Any] = resp.json()
    jobs = payload.get("jobs") or []

    records: list[dict] = []
    source = f"Ashby:{slug}"
    for job in jobs:
        posting_url = _posting_url(job, slug)
        if not posting_url:
            continue
        raw_text = _build_raw_text(job, company_kr)
        records.append(
            make_record(
                source=source,
                posting_url=posting_url,
                raw_text=raw_text,
            )
        )
    return records


def fetch() -> list[dict]:
    """Ashby 다수 회사 통합 채용공고 수집."""
    all_records: list[dict] = []
    items = list(COMPANIES.items())
    for idx, (slug, company_kr) in enumerate(items):
        try:
            recs = _fetch_company(slug, company_kr)
        except Exception as exc:  # noqa: BLE001 — 회사 단위 격리
            print(
                f"[ashby] {slug} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            recs = []
        print(
            f"[ashby] {slug} ({company_kr}): {len(recs)} records",
            file=sys.stderr,
        )
        all_records.extend(recs)
        if idx < len(items) - 1:
            polite_sleep()
    return all_records
