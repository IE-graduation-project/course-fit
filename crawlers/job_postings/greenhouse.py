"""Greenhouse Job Board API fetcher (한국 4사 통합).

대상 (한국 본사·법인 한정):
    1. 쿠팡 (coupang)         — ~387건
    2. 크래프톤 (krafton)      — ~57건
    3. 당근 (daangn)           — ~45건
    4. Seoul Robotics (seoulrobotics) — ~7건

⚠️ 글로벌 board id 중 Naver Vietnam, Krafton Americas/India 등은 한국 본사가
아니므로 의도적으로 제외.

Greenhouse Job Board API:
    https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true
- 무인증 GET, hard rate limit 없음 (공식적으로 client-side 호출 의도).
- `content=true` 시 jobs[].content 에 HTML 본문 포함.

각 공고 dict 는 `make_record()` 로 생성되어
`data/job_posting.csv` 의 컬럼 (job_id/source/posting_url/raw_text/crawled_at)
과 1:1 매핑된다.
"""
from __future__ import annotations

import html as _html
import sys
from typing import Any

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


# board slug -> 표시용 한글명
BOARDS: list[tuple[str, str]] = [
    ("coupang", "쿠팡"),
    ("krafton", "크래프톤"),
    ("daangn", "당근"),
    ("seoulrobotics", "Seoul Robotics"),
]

API_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
MIN_RAW_TEXT_LEN = 100


def _meta_names(items: list[dict] | None, key: str = "name") -> list[str]:
    """[{name: 'Engineering'}, ...] -> ['Engineering', ...] (빈/None 제거)."""
    if not items:
        return []
    out = []
    for it in items:
        v = (it or {}).get(key)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def _location_text(job: dict) -> str:
    loc = job.get("location")
    if isinstance(loc, dict):
        name = loc.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    offices = ", ".join(_meta_names(job.get("offices")))
    return offices


def _build_raw_text(job: dict, company_kr: str) -> str:
    """메타(회사·title·부서·위치) + 본문 평문. 짧으면 메타만으로도 검색 가능."""
    title = (job.get("title") or "").strip()
    location = _location_text(job)
    departments = ", ".join(_meta_names(job.get("departments")))

    raw_html = job.get("content") or ""
    # Greenhouse 의 content 는 HTML-encoded string ("&lt;p&gt;..." 형태) 이라
    # html_to_text 직전에 한 번 unescape 해야 BeautifulSoup 가 태그를 인식한다.
    if raw_html and "&lt;" in raw_html and "<" not in raw_html:
        raw_html = _html.unescape(raw_html)
    body = html_to_text(raw_html)

    # 일부 회사(쿠팡)는 title 자체에 이미 "[쿠팡] ..." 가 들어있어 중복 방지.
    if title.startswith(f"[{company_kr}]"):
        header_lines = [title]
    else:
        header_lines = [f"[{company_kr}] {title}".strip()]
    if location:
        header_lines.append(f"위치: {location}")
    if departments:
        header_lines.append(f"부서: {departments}")
    header = "\n".join(ln for ln in header_lines if ln)

    combined = f"{header}\n\n{body}".strip() if body else header

    # 본문 짧으면 헤더만으로도 최소 검색 가능성 확보 (이미 prepend 됨)
    if len(combined) < MIN_RAW_TEXT_LEN:
        # 추가 메타 (id, updated_at) 까지 붙여 fallback
        extras = []
        gh_id = job.get("id")
        if gh_id is not None:
            extras.append(f"Greenhouse ID: {gh_id}")
        updated = job.get("updated_at")
        if updated:
            extras.append(f"updated_at: {updated}")
        if extras:
            combined = f"{combined}\n{chr(10).join(extras)}"

    return combined


def _fetch_board(board: str, company_kr: str) -> list[dict]:
    url = API_TEMPLATE.format(board=board)
    resp = http_get(url, params={"content": "true"})
    payload: dict[str, Any] = resp.json()
    jobs = payload.get("jobs") or []

    records: list[dict] = []
    source = f"Greenhouse:{board}"
    for job in jobs:
        posting_url = (job.get("absolute_url") or "").strip()
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
    """4사 통합 채용공고 수집."""
    all_records: list[dict] = []
    for idx, (board, company_kr) in enumerate(BOARDS):
        try:
            recs = _fetch_board(board, company_kr)
        except Exception as exc:  # noqa: BLE001 — fetcher 단위 격리
            print(
                f"[greenhouse] {board} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            recs = []
        print(
            f"[greenhouse] {board} ({company_kr}): {len(recs)} records",
            file=sys.stderr,
        )
        all_records.extend(recs)
        if idx < len(BOARDS) - 1:
            polite_sleep()
    return all_records
