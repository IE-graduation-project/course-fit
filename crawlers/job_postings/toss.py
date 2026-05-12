"""Toss (viva republica) careers fetcher.

토스 그룹(토스/토스뱅크/토스증권/토스페이먼츠/토스인슈어런스/토스씨엑스/토스플레이스 등)의
careers 페이지(`https://toss.im/career/jobs`)는 Next.js SSR 화면이며 실제 데이터는
클라이언트가 토스 자체 public JSON API(Greenhouse 백엔드를 그대로 프록시)로 호출한다.

API (브라우저 트래픽으로 확인 — `_app` 번들의 모듈 32346 에 상수로 들어 있음):

    LIST   GET https://api-public.toss.im/api/v3/ipd-eggnog/career/jobs
    DETAIL GET https://api-public.toss.im/api/v3/ipd-eggnog/career/jobs/{id}

응답 envelope: ``{"resultType": "...", "error": ..., "success": <list|dict>}``.
``success`` 안의 각 job 은 Greenhouse 스키마 그대로 (`id`, `title`, `absolute_url`,
`departments`, `offices`, `content` HTML-escaped).

robots.txt:
    Allow:    /career/jobs (목록)
    Disallow: /career/jobs?* (필터 파라미터), /career/contents/, /career/apply-admin/
    이 모듈은 공식 API + 무파라미터 목록만 호출하므로 정책 범위 안에 있다.

회사명 분리: top-level `company_name` 은 모두 "Toss" 라 무의미. `departments[0].name`
(예: '토스페이먼츠') 으로 그룹사를 식별해 ``source = "Toss:토스페이먼츠"`` 로 기록.
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


API_BASE = "https://api-public.toss.im/api/v3/ipd-eggnog/career"
LIST_URL = f"{API_BASE}/jobs"
DETAIL_URL_TEMPLATE = f"{API_BASE}/jobs/{{job_id}}"

# 본문 너무 짧은 placeholder('#LI-DNI', '인재풀' 등) 는 매칭 노이즈만 만들어 제외.
MIN_BODY_LEN = 80
SKIP_TITLE_KEYWORDS = ("인재풀", "채용 소식지", "talent pool")


def _names(items: list[dict] | None) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    for it in items:
        v = (it or {}).get("name")
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


def _extract_envelope(payload: dict) -> Any:
    """toss API 는 항상 ``{"resultType","error","success"}`` envelope."""
    if not isinstance(payload, dict):
        return None
    if "success" in payload:
        return payload["success"]
    return payload


def _decode_html_content(raw: str) -> str:
    """Greenhouse content 는 HTML-encoded ('&lt;p&gt;...') 형태로 오기도 하므로 unescape."""
    if not raw:
        return ""
    if "&lt;" in raw and "<" not in raw:
        raw = _html.unescape(raw)
    return raw


def _subsidiary(job: dict) -> str:
    """토스 그룹사 이름. departments 가 가장 정확 (e.g. '토스페이먼츠'). 없으면 'Toss'."""
    depts = _names(job.get("departments"))
    for name in depts:
        if name and name.lower() != "toss":
            return name
    return "Toss"


def _location(job: dict) -> str:
    loc = job.get("location")
    if isinstance(loc, dict):
        name = loc.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    offices = ", ".join(_names(job.get("offices")))
    return offices


def _is_skippable(title: str, body_len: int) -> bool:
    t = title.lower()
    if any(kw.lower() in t for kw in SKIP_TITLE_KEYWORDS):
        return True
    return body_len < MIN_BODY_LEN


def _build_raw_text(detail: dict, subsidiary: str) -> str:
    title = (detail.get("title") or "").strip()
    location = _location(detail)
    departments = ", ".join(_names(detail.get("departments")))
    body = html_to_text(_decode_html_content(detail.get("content") or ""))

    header_lines = [f"[{subsidiary}] {title}".strip()]
    if departments:
        header_lines.append(f"부서: {departments}")
    if location:
        header_lines.append(f"위치: {location}")
    header = "\n".join(ln for ln in header_lines if ln)
    return f"{header}\n\n{body}".strip() if body else header


def _fetch_list() -> list[dict]:
    resp = http_get(LIST_URL)
    payload = resp.json()
    jobs = _extract_envelope(payload) or []
    return jobs if isinstance(jobs, list) else []


def _fetch_detail(job_id: int | str) -> dict | None:
    url = DETAIL_URL_TEMPLATE.format(job_id=job_id)
    try:
        resp = http_get(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[toss] detail {job_id} 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None
    data = _extract_envelope(resp.json())
    return data if isinstance(data, dict) else None


def fetch() -> list[dict]:
    """토스 그룹 careers 공고 통합 수집."""
    try:
        listings = _fetch_list()
    except Exception as exc:  # noqa: BLE001
        print(f"[toss] list 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
        return []

    print(f"[toss] list: {len(listings)} jobs", file=sys.stderr)

    records: list[dict] = []
    skipped = 0
    for idx, job in enumerate(listings):
        job_id = job.get("id")
        if job_id is None:
            continue
        polite_sleep()
        detail = _fetch_detail(job_id)
        if detail is None:
            continue

        title = (detail.get("title") or "").strip()
        body = html_to_text(_decode_html_content(detail.get("content") or ""))
        if _is_skippable(title, len(body)):
            skipped += 1
            continue

        subsidiary = _subsidiary(detail)
        posting_url = (
            (detail.get("absolute_url") or job.get("absolute_url") or "").strip()
        )
        if not posting_url:
            posting_url = f"https://toss.im/career/job-detail?gh_jid={job_id}"

        records.append(
            make_record(
                source=f"Toss:{subsidiary}" if subsidiary != "Toss" else "Toss",
                posting_url=posting_url,
                raw_text=_build_raw_text(detail, subsidiary),
            )
        )
        if (idx + 1) % 50 == 0:
            print(
                f"[toss] progress {idx + 1}/{len(listings)} (kept={len(records)}, skipped={skipped})",
                file=sys.stderr,
            )

    print(
        f"[toss] done: kept {len(records)}, skipped {skipped} of {len(listings)}",
        file=sys.stderr,
    )
    return records
