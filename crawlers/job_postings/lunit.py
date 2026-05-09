"""Lunit (의료영상 AI) 채용공고 fetcher.

ATS:
    Workable Job Board API (apply.workable.com)
    - 공식 careers 페이지(`https://www.lunit.io/en/careers/`)가 Greenhouse 가 아닌
      Workable 로 연결됨 → 모든 공고는 `apply.workable.com/lunit/` 산하에 있음.
    - Greenhouse 신도메인(`job-boards.greenhouse.io/lunit`)·표준 API 모두 404 확인.

엔드포인트 (둘 다 무인증):
    1) 목록  : POST https://apply.workable.com/api/v3/accounts/lunit/jobs
       body : {} 로 첫 페이지, 이후 {"token": <nextPage>} 로 페이지네이션.
       응답 : {"total": int, "results": [...], "nextPage": str|null}
    2) 상세  : GET  https://apply.workable.com/api/v1/accounts/lunit/jobs/{shortcode}
       응답 : {"description": HTML, "requirements": HTML, "benefits": HTML, ...}

매너:
    - User-Agent 명시, polite_sleep ≥ 1.5s.
    - Workable 의 client-side 위젯 자체가 동일 엔드포인트를 호출하므로 공개 API.
"""
from __future__ import annotations

import sys
from typing import Any

import requests

from crawlers.job_postings._common import (
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT_SEC,
    html_to_text,
    make_record,
    polite_sleep,
)


SUBDOMAIN = "lunit"
COMPANY_KR = "Lunit"  # 영문 그대로 (한국어 표기도 'Lunit'으로 통용)
LIST_URL = f"https://apply.workable.com/api/v3/accounts/{SUBDOMAIN}/jobs"
DETAIL_URL_TEMPLATE = (
    f"https://apply.workable.com/api/v1/accounts/{SUBDOMAIN}/jobs/{{shortcode}}"
)
POSTING_URL_TEMPLATE = f"https://apply.workable.com/{SUBDOMAIN}/j/{{shortcode}}/"
SOURCE = f"Workable:{SUBDOMAIN}"

MAX_PAGES = 20  # 안전 상한 (Lunit 은 통상 ~11건)


def _post_jobs(token: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"token": token} if token else {}
    headers = {**DEFAULT_HEADERS, "Content-Type": "application/json"}
    resp = requests.post(
        LIST_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SEC
    )
    resp.raise_for_status()
    return resp.json()


def _get_detail(shortcode: str) -> dict[str, Any]:
    headers = {**DEFAULT_HEADERS, "Accept": "application/json"}
    resp = requests.get(
        DETAIL_URL_TEMPLATE.format(shortcode=shortcode),
        headers=headers,
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return resp.json()


def _location_text(job: dict) -> str:
    loc = job.get("location") or {}
    parts = [
        loc.get("city"),
        loc.get("region"),
        loc.get("country"),
    ]
    return ", ".join(p for p in parts if isinstance(p, str) and p.strip())


def _build_raw_text(summary: dict, detail: dict) -> str:
    title = (summary.get("title") or detail.get("title") or "").strip()
    location = _location_text(detail or summary)
    dept = detail.get("department") or summary.get("department") or []
    if isinstance(dept, list):
        dept_text = ", ".join(d for d in dept if isinstance(d, str) and d.strip())
    else:
        dept_text = str(dept).strip()

    sections: list[str] = []
    for key in ("description", "requirements", "benefits"):
        body = html_to_text(detail.get(key) or "")
        if body:
            sections.append(body)
    body_text = "\n\n".join(sections)

    header_lines = [f"[{COMPANY_KR}] {title}".strip()]
    if dept_text:
        header_lines.append(f"부서: {dept_text}")
    if location:
        header_lines.append(f"위치: {location}")
    header = "\n".join(header_lines)

    return f"{header}\n\n{body_text}".strip() if body_text else header


def _list_all_jobs() -> list[dict]:
    """Workable list API 를 페이지네이션으로 모두 수집."""
    out: list[dict] = []
    token: str | None = None
    for page in range(MAX_PAGES):
        data = _post_jobs(token)
        results = data.get("results") or []
        out.extend(results)
        token = data.get("nextPage")
        if not token or not results:
            break
        polite_sleep()
    else:
        print(
            f"[lunit] MAX_PAGES={MAX_PAGES} 도달, 잘렸을 수 있음", file=sys.stderr
        )
    return out


def fetch() -> list[dict]:
    """Lunit (의료 AI) 채용공고 수집."""
    try:
        summaries = _list_all_jobs()
    except Exception as exc:  # noqa: BLE001
        print(
            f"[lunit] 목록 수집 실패: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        return []

    records: list[dict] = []
    for idx, summary in enumerate(summaries):
        shortcode = summary.get("shortcode")
        if not shortcode:
            continue
        try:
            detail = _get_detail(shortcode)
        except Exception as exc:  # noqa: BLE001 — 공고 단위 격리
            print(
                f"[lunit] 상세 실패 ({shortcode}): {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            detail = {}
        raw_text = _build_raw_text(summary, detail or summary)
        posting_url = POSTING_URL_TEMPLATE.format(shortcode=shortcode)
        records.append(
            make_record(source=SOURCE, posting_url=posting_url, raw_text=raw_text)
        )
        if idx < len(summaries) - 1:
            polite_sleep()

    print(f"[lunit] {COMPANY_KR}: {len(records)} records", file=sys.stderr)
    return records
