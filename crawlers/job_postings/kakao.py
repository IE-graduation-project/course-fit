"""카카오 (careers.kakao.com) 자체 JSON fetcher.

대상 endpoint (검증 완료 — 2026-05-10):
    GET https://careers.kakao.com/public/api/job-list
        ?skillSet=&part=&company=&keyword=&employeeType=&page={N}

응답 스키마 (요지):
    {
      "jobList": [{realId, jobOfferId, jobOfferTitle, jobType, jobTypeName,
                   jobPartName, companyName, locationName, employeeTypeName,
                   recruitCount, regDate, uptDate, endDate,
                   introduction, workContentDesc, qualification,
                   jobOfferProcessDesc, krewComment, ...}, ...],
      "jobTypeCountDtoList": [{jobType, jobCount}, ...],
      "totalJobCount": int,
      "totalPage": int
    }

설계 결정:
1) **상세 호출 불필요** — list 응답 자체에 introduction / workContentDesc /
   qualification / jobOfferProcessDesc / krewComment 가 모두 HTML(<br/> 포함)
   로 들어오므로 한 번만 호출해 raw_text 를 만든다. 별도 detail endpoint
   (/public/api/job-offer/{id} 등) 는 모두 404 로 검증됨.
2) **page 파라미터는 끝까지 순회하나 totalPage 가 1 인 경우가 많다** —
   카카오 공개 API 는 jobType / pinFlag / employeeType 필터를 적용해도 동일한
   고정 12 건 (전부 viewTypeCode=BANNER) 만 노출하는 것으로 관찰됨. 비공개
   공고나 자회사 공고는 GreetingHR fetcher 가 별도로 처리한다.
3) **자회사 제외** — 카카오뱅크 / 페이 / 모빌리티 등은 별도 도메인(GreetingHR)
   이라 이 모듈은 본사 (companyName == '카카오') 만 다룬다. 응답에 본사 외
   항목이 섞여오면 그대로 두되 `source` 는 "KakaoCareers" 로 통일.
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


LIST_URL = "https://careers.kakao.com/public/api/job-list"
JOB_PAGE_TEMPLATE = "https://careers.kakao.com/jobs/{real_id}"
SOURCE = "KakaoCareers"

# careers.kakao.com 은 SPA 라 referer 가 있어야 안정적
EXTRA_HEADERS = {
    "Referer": "https://careers.kakao.com/jobs",
    "Accept": "application/json, text/plain, */*",
}

# 무한 루프 안전망 — 실측 totalPage 는 1 이지만 변동 대비
MAX_PAGES = 30


def _join_html_blocks(blocks: list[tuple[str, str]]) -> str:
    """[(섹션라벨, html)] -> '◆ 섹션라벨\n평문' 합쳐 반환. 빈 블록 skip."""
    out: list[str] = []
    for label, raw in blocks:
        if not raw or not isinstance(raw, str):
            continue
        # 일부 필드(krewComment 등)는 entity-encoded ('&lt;br/&gt;') 가능성
        if "&lt;" in raw and "<" not in raw:
            raw = _html.unescape(raw)
        text = html_to_text(raw)
        if text:
            out.append(f"◆ {label}\n{text}")
    return "\n\n".join(out)


def _build_raw_text(job: dict) -> str:
    """list 응답 하나 -> 한국어 평문 raw_text."""
    title = (job.get("jobOfferTitle") or "").strip()
    company = (job.get("companyName") or "").strip()
    job_type = (job.get("jobTypeName") or "").strip()  # Tech/Staff/Business/Design
    job_part = (job.get("jobPartName") or "").strip()
    location = (job.get("locationName") or "").strip()
    employee_type = (job.get("employeeTypeName") or "").strip()
    recruit_count = job.get("recruitCount")
    upt = (job.get("uptDate") or "").strip()
    end = (job.get("endDate") or "").strip() if job.get("endDate") else ""

    skills = job.get("skillSetList") or []
    skill_names = [
        s.get("skillSetName") for s in skills if isinstance(s, dict) and s.get("skillSetName")
    ]

    if company and title:
        head = f"[{company}] {title}"
    else:
        head = title or company
    header_lines = [head] if head else []
    meta_pairs = [
        ("카테고리", job_type),
        ("직군", job_part),
        ("근무지", location),
        ("고용형태", employee_type),
        ("모집인원", str(recruit_count) if recruit_count not in (None, "", 0) else ""),
        ("스킬", ", ".join(skill_names)),
        ("최근수정", upt),
        ("마감일", end),
    ]
    for label, val in meta_pairs:
        if val:
            header_lines.append(f"{label}: {val}")
    header = "\n".join(header_lines)

    body = _join_html_blocks(
        [
            ("팀소개", job.get("introduction") or ""),
            ("주요업무", job.get("workContentDesc") or ""),
            ("자격요건/우대사항", job.get("qualification") or ""),
            ("전형절차", job.get("jobOfferProcessDesc") or ""),
            ("크루코멘트", job.get("krewComment") or ""),
        ]
    )

    return f"{header}\n\n{body}".strip() if body else header


def _fetch_page(page: int) -> dict[str, Any]:
    params = {
        "skillSet": "",
        "part": "",
        "company": "",
        "keyword": "",
        "employeeType": "",
        "page": str(page),
    }
    resp = http_get(LIST_URL, params=params, headers=EXTRA_HEADERS)
    return resp.json()


def fetch() -> list[dict]:
    """카카오 본사 영입 공고 (KakaoCareers public API)."""
    seen_ids: set[str] = set()
    records: list[dict] = []

    page = 1
    total_page = 1
    while page <= min(total_page, MAX_PAGES):
        try:
            payload = _fetch_page(page)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[kakao] page={page} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            break

        job_list = payload.get("jobList") or []
        total_page = int(payload.get("totalPage") or 1)
        new_in_page = 0

        for job in job_list:
            real_id = (job.get("realId") or "").strip()
            if not real_id or real_id in seen_ids:
                continue
            seen_ids.add(real_id)
            posting_url = JOB_PAGE_TEMPLATE.format(real_id=real_id)
            raw_text = _build_raw_text(job)
            if not raw_text:
                continue
            records.append(
                make_record(
                    source=SOURCE,
                    posting_url=posting_url,
                    raw_text=raw_text,
                )
            )
            new_in_page += 1

        print(
            f"[kakao] page={page}/{total_page}: jobList={len(job_list)} new={new_in_page} cum={len(records)}",
            file=sys.stderr,
        )

        # 새 항목 0 인 페이지가 나오면 (서버가 page 무시하고 동일 응답 반환)
        # totalPage 와 무관하게 즉시 종료해 무한 루프 방지
        if new_in_page == 0:
            break

        page += 1
        if page <= total_page:
            polite_sleep()

    return records
