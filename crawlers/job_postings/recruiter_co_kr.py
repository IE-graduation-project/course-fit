"""recruiter.co.kr (마이다스인) 한국 채용 SaaS 통합 fetcher.

recruiter.co.kr 은 마이다스인이 운영하는 ATS SaaS 로, 다수의 한국 대기업·금융사가
같은 플랫폼을 사용한다. 슬러그가 다를 뿐 API 스펙은 동일하므로 단일 어댑터로 처리.

수집 전략 (실측 2026-05):
    1. 회사별 공개 robots.txt 확인 — 본 모듈 대상은 모두 `Allow: /` (Disallow 미해당)
    2. 목록 API: ``POST https://api-recruiter.recruiter.co.kr/position/v1/jobflex``
       - 헤더 ``prefix: {slug}.recruiter.co.kr`` 로 테넌트 라우팅
       - body ``{"pageableRq": {"page", "size", "sort": ["CREATED_DATE_TIME"]},
         "filter": {"keyword": "", "tagSnList": [], ...}}``
       - response ``{"pagination": {"totalCount", "totalPages"},
         "list": [{"positionSn", "title", ...}]}``
    3. 상세 API: ``GET /position/v2/jobflex/{positionSn}``
       - response ``{"title", "jobDescription"(HTML), "tagList", "careerType",
         "classificationCode", "recruitmentType", "startDateTime", "endDateTime", ...}``
    4. 사용자용 URL: ``https://{slug}.recruiter.co.kr/career/jobs/{positionSn}``
       (Next.js SPA. 사용자에게는 raw_text 보다 이쪽이 의미 있음.)

회사별 try/except 격리 — 한 회사 fail (slug 변경, 시즌 종료 등) 이 전체를 죽이지 않음.

검증된 슬러그 (실측 — 200 OK + 공고 1+ 또는 정기 운영 SaaS):
    금융·증권: shinhan / nhqv / busanbank / knbank / hanabank / meritz
    제약·바이오: celltrion / hanmi / jeil / yuhan
    제조·산업: hd (HD현대) / hwasung
    IT·게임·통신: kt / com2us
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
import requests

from crawlers.job_postings._common import DEFAULT_HEADERS, REQUEST_TIMEOUT_SEC

API_BASE = "https://api-recruiter.recruiter.co.kr"
LIST_PATH = "/position/v1/jobflex"
DETAIL_PATH = "/position/v2/jobflex/{position_sn}"

PAGE_SIZE = 50
MIN_RAW_TEXT_LEN = 80

# slug -> 한글 회사명. 실측 200 OK 슬러그만 등재 (totalCount 0 이어도 시즌성 고려해 유지).
COMPANIES: dict[str, str] = {
    # 금융·증권
    "shinhan": "신한은행",
    "hanabank": "하나은행",
    "nhqv": "NH투자증권",
    "busanbank": "BNK부산은행",
    "knbank": "BNK경남은행",
    "meritz": "메리츠금융",
    # 제약·바이오
    "celltrion": "셀트리온",
    "hanmi": "한미약품그룹",
    "jeil": "제일약품",
    "yuhan": "유한양행",
    # 제조·산업
    "hd": "HD현대",
    "hwasung": "HS화성",
    # IT·게임·통신
    "kt": "KT그룹",
    "com2us": "컴투스",
}


def _api_post(slug: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
    headers = {
        **DEFAULT_HEADERS,
        "prefix": f"{slug}.recruiter.co.kr",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://{slug}.recruiter.co.kr/career/jobs",
        "Origin": f"https://{slug}.recruiter.co.kr",
    }
    resp = requests.post(
        f"{API_BASE}{path}",
        json=body,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return resp.json()


def _api_get(slug: str, path: str) -> dict[str, Any]:
    headers = {
        **DEFAULT_HEADERS,
        "prefix": f"{slug}.recruiter.co.kr",
        "Accept": "application/json, text/plain, */*",
        "Referer": f"https://{slug}.recruiter.co.kr/career/jobs",
        "Origin": f"https://{slug}.recruiter.co.kr",
    }
    return http_get(f"{API_BASE}{path}", headers=headers).json()


def _empty_filter() -> dict[str, list]:
    return {
        "keyword": "",
        "tagSnList": [],
        "jobGroupSnList": [],
        "careerTypeList": [],
        "regionSnList": [],
        "submissionStatusList": [],
        "openStatusList": [],
        "resumeLanguageTypeList": [],
    }


def _list_postings(slug: str) -> list[dict[str, Any]]:
    """페이지네이션 따라 모든 공고 메타 수집."""
    page = 1
    out: list[dict[str, Any]] = []
    while True:
        body = {
            "pageableRq": {
                "page": page,
                "size": PAGE_SIZE,
                "sort": ["CREATED_DATE_TIME"],
            },
            "filter": _empty_filter(),
        }
        data = _api_post(slug, LIST_PATH, body)
        items = data.get("list") or []
        out.extend(items)
        pagination = data.get("pagination") or {}
        total_pages = int(pagination.get("totalPages") or 0)
        if page >= total_pages or not items:
            break
        page += 1
        polite_sleep()
    return out


def _career_type_label(code: str | None) -> str:
    return {
        "NEW": "신입",
        "CAREER": "경력",
        "NEW_CAREER": "신입/경력",
    }.get(code or "", code or "")


def _build_raw_text(
    company_kr: str, summary: dict[str, Any], detail: dict[str, Any]
) -> str:
    title = (detail.get("title") or summary.get("title") or "").strip()
    # 일부 회사 제목에는 이미 ``[회사명]`` 접두가 들어있어 중복 방지
    bracket = f"[{company_kr}]"
    display_title = title if title.startswith(bracket) else f"{bracket} {title}".strip()
    body = html_to_text(detail.get("jobDescription") or "")

    # tagList 는 분류·고용형태·직군 등 자유 형식 키워드 — 직군 매칭에 유용.
    tag_names = [
        (t.get("tagName") or "").strip()
        for t in (detail.get("tagList") or summary.get("tagList") or [])
        if t.get("tagName")
    ]
    career_label = _career_type_label(detail.get("careerType") or summary.get("careerType"))
    classification = (detail.get("classificationCode") or "").strip()
    recruitment = (detail.get("recruitmentType") or "").strip()
    start = (detail.get("startDateTime") or "").strip()
    end = (detail.get("endDateTime") or "").strip()

    header_lines = [display_title]
    meta_bits: list[str] = []
    if career_label:
        meta_bits.append(career_label)
    if classification:
        meta_bits.append(classification)
    if recruitment and recruitment.upper() != "GENERAL":
        meta_bits.append(recruitment)
    if meta_bits:
        header_lines.append(" · ".join(meta_bits))
    if tag_names:
        # 중복 제거, 순서 유지
        uniq = list(dict.fromkeys(tag_names))
        header_lines.append("태그: " + ", ".join(uniq))
    if start or end:
        header_lines.append(f"공고기간: {start} ~ {end}".strip())

    header = "\n".join(ln for ln in header_lines if ln)
    combined = f"{header}\n\n{body}".strip() if body else header

    if len(combined) < MIN_RAW_TEXT_LEN:
        # 본문 부재시에도 최소 식별 정보 보존
        sn = detail.get("positionSn") or summary.get("positionSn")
        if sn:
            combined = f"{combined}\npositionSn: {sn}"
    return combined


def _fetch_company(slug: str, company_kr: str) -> list[dict]:
    summaries = _list_postings(slug)
    print(
        f"[recruiter] {slug} ({company_kr}): list count = {len(summaries)}",
        file=sys.stderr,
    )

    records: list[dict] = []
    source = f"Recruiter:{slug}"
    for idx, summary in enumerate(summaries):
        position_sn = summary.get("positionSn")
        if position_sn is None:
            continue
        polite_sleep()
        try:
            detail = _api_get(slug, DETAIL_PATH.format(position_sn=position_sn))
        except Exception as exc:  # noqa: BLE001 — 단건 격리
            print(
                f"[recruiter] {slug}/{position_sn} GET 실패: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue

        posting_url = f"https://{slug}.recruiter.co.kr/career/jobs/{position_sn}"
        raw_text = _build_raw_text(company_kr, summary, detail)
        records.append(
            make_record(
                source=source,
                posting_url=posting_url,
                raw_text=raw_text,
            )
        )
        if (idx + 1) % 25 == 0:
            print(
                f"[recruiter] {slug}: {idx + 1}/{len(summaries)} 진행",
                file=sys.stderr,
            )
    return records


def fetch() -> list[dict]:
    """recruiter.co.kr SaaS 다수 회사 통합 채용공고 수집."""
    all_records: list[dict] = []
    items = list(COMPANIES.items())
    for idx, (slug, company_kr) in enumerate(items):
        try:
            recs = _fetch_company(slug, company_kr)
        except Exception as exc:  # noqa: BLE001 — 회사 단위 격리
            print(
                f"[recruiter] {slug} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            recs = []
        print(
            f"[recruiter] {slug} ({company_kr}): {len(recs)} records",
            file=sys.stderr,
        )
        all_records.extend(recs)
        if idx < len(items) - 1:
            polite_sleep()
    return all_records
