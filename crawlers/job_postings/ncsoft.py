"""NCSOFT 자체 채용 (NC Careers, careers.ncsoft.com) fetcher.

대상 endpoint (검증 — 2026-05-10):
- 메인 SSR: GET https://careers.ncsoft.com/career/list  (CSRF 토큰/세션 쿠키 발급)
- 목록 API: POST https://careers.ncsoft.com/interface/apply/list
    Content-Type: application/x-www-form-urlencoded; charset=UTF-8
    헤더: X-CSRF-TOKEN, Cookie(nextrct-web-session), X-Requested-With: XMLHttpRequest,
          Referer: https://careers.ncsoft.com/career/list
    body (DEFAULT_PARAMS): order_type=ORDER_ETC, order_direction=desc, page=1,
          pagesize=20(또는 200으로 한 번에), channelCds=, keywords=, job_group_cd=,
          search_text=, job_type_cd=, companyIds=
    응답: {"result":{"data":{"record_count":N, "record":[ {jopenId, jopenNm,
          jobGroupName, jobTypeName, jobName, channelNm, companyNm, startDt,
          endDt, regOpId, dday, ...}, ... ]}}}
- 상세 SSR: GET https://careers.ncsoft.com/apply/view?jopenId={id}&companyId={regOpId}
    본문은 ``<article>`` 노드(주요업무·지원자격·우대사항 등 평문 섹션 포함)에 들어 있음.
    헤더 요약은 ``.recruit-summary`` 또는 ``.apply-detail-header-wrap``.

설계 결정
1) **목록은 한 번에** — `pagesize=200` 으로 단일 호출. 실측 record_count=105 (2026-05-10),
   서버가 잘라내지 않고 전체 record 반환. 페이지네이션 안전망은 `MAX_PAGES` 로 둠.
2) **CSRF 처리** — 메인 페이지 GET → `<meta name="_csrf">` 토큰 + `nextrct-web-session`
   쿠키 채취 → 후속 POST에 `X-CSRF-TOKEN` 헤더 + 쿠키 부착. 토큰 없으면 404 HTML 반환.
3) **상세는 jopenId+regOpId 페어** — 목록 응답의 `regOpId` (대부분 ``"NCH"``) 가
   companyId 로 사용됨. URL 추정: ``/apply/view?jopenId=...&companyId=...``.
4) **raw_text 구조** — header 줄(회사/카테고리/타이틀/직군/모집기간/dday) + 빈줄 + 본문
   article 평문. 상세 추출 실패 시 메타만으로 fallback.

매너
- robots.txt: HTTP 404 (확인 2026-05-10) — disallow 명시 없음.
- User-Agent: _common.DEFAULT_HEADERS (HongikCapstone-CourseFit/0.1).
- 호출 간 polite_sleep() ≥ 1.5s. 한 번 batch 만 호출.
"""
from __future__ import annotations

import sys
from typing import Any

import requests
from bs4 import BeautifulSoup

from crawlers.job_postings._common import (
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT_SEC,
    html_to_text,
    make_record,
    polite_sleep,
)


BASE = "https://careers.ncsoft.com"
LIST_PAGE_URL = f"{BASE}/career/list"
LIST_API_URL = f"{BASE}/interface/apply/list"
DETAIL_URL_TEMPLATE = f"{BASE}/apply/view?jopenId={{jopen_id}}&companyId={{reg_op_id}}"
SOURCE = "NCSOFT"

PAGE_SIZE = 200  # 실측 record_count=105 (2026-05-10) — 한 번에 받도록 충분히 큼
MAX_PAGES = 20   # 안전망: pagesize=200 기준 ~4000건까지 커버


# ─────────────────────────────────────────────────────────────────────────────
# Session bootstrap
# ─────────────────────────────────────────────────────────────────────────────
def _bootstrap_session() -> tuple[requests.Session, str]:
    """메인 페이지 GET → CSRF 토큰 + session 쿠키 확보.

    NC Careers 서버는 ``Accept: application/json`` 가 선호되면 빈 body 를 반환하므로
    HTML 명시 Accept 헤더로 GET 한다.

    Returns: (session, csrf_token). 토큰 추출 실패 시 RuntimeError.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    resp = session.get(
        LIST_PAGE_URL,
        headers={
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            )
        },
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", attrs={"name": "_csrf"})
    token = (meta.get("content") if meta else "") or ""
    token = token.strip()
    if not token:
        raise RuntimeError("NCSOFT: _csrf meta 태그를 찾지 못함 — 페이지 구조 변경 의심")
    return session, token


# ─────────────────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────────────────
def _post_list_page(
    session: requests.Session, csrf: str, page: int, pagesize: int
) -> dict[str, Any]:
    headers = {
        "X-CSRF-TOKEN": csrf,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": LIST_PAGE_URL,
        "Origin": BASE,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    data = {
        "order_type": "ORDER_ETC",
        "order_direction": "desc",
        "page": str(page),
        "pagesize": str(pagesize),
        "channelCds": "",
        "keywords": "",
        "job_group_cd": "",
        "search_text": "",
        "job_type_cd": "",
        "companyIds": "",
    }
    resp = session.post(
        LIST_API_URL, headers=headers, data=data, timeout=REQUEST_TIMEOUT_SEC
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_all_records(
    session: requests.Session, csrf: str
) -> list[dict[str, Any]]:
    """전체 공고 메타 리스트 수집 (pagesize=PAGE_SIZE 페이지네이션)."""
    items: list[dict[str, Any]] = []
    seen: set[int] = set()

    for page in range(1, MAX_PAGES + 1):
        try:
            payload = _post_list_page(session, csrf, page=page, pagesize=PAGE_SIZE)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[ncsoft] list page={page} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            break

        result = (payload or {}).get("result") or {}
        data = result.get("data") or {}
        record = data.get("record") or []
        total = int(data.get("record_count") or 0)

        new_in_page = 0
        for it in record:
            jid = it.get("jopenId")
            if jid is None or jid in seen:
                continue
            seen.add(jid)
            items.append(it)
            new_in_page += 1

        print(
            f"[ncsoft] list page={page}: total={total} got={len(record)} new={new_in_page} cum={len(items)}",
            file=sys.stderr,
        )

        if new_in_page == 0:
            break
        if total and len(items) >= total:
            break
        if len(record) < PAGE_SIZE:
            break
        polite_sleep()

    return items


# ─────────────────────────────────────────────────────────────────────────────
# Detail
# ─────────────────────────────────────────────────────────────────────────────
def _extract_detail_text(html: str) -> str:
    """상세 페이지 article 본문(주요업무/자격요건/우대사항/전형) 평문 추출."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    art = soup.select_one("article")
    if art is None:
        # fallback: apply-detail-content 영역
        art = soup.select_one(".apply-detail-content, .apply-detail-content-wrap")
    if art is None:
        return ""
    return html_to_text(str(art))


def _build_raw_text(item: dict[str, Any], detail_text: str) -> str:
    """[NCSOFT] title\n직군: ...\n경력: ...\n\n본문 형식."""
    title = (item.get("jopenNm") or "").strip()
    company = (item.get("companyNm") or "").strip()
    channel = (item.get("channelNm") or "").strip()
    job_group = (item.get("jobGroupName") or "").strip()
    job_type = (item.get("jobTypeName") or "").strip()
    job_name = (item.get("jobName") or "").strip()
    start_dt = (item.get("startDt") or "").strip()
    end_dt = (item.get("endDt") or "").strip()
    dday = item.get("dday")

    head_label = company or "NCSOFT"
    head = f"[{head_label}] {title}" if title else f"[{head_label}]"
    lines: list[str] = [head]

    cat_parts = [p for p in (job_group, job_type, job_name) if p]
    if cat_parts:
        lines.append("직군: " + " > ".join(cat_parts))
    if channel:
        lines.append(f"채용유형: {channel}")
    if start_dt and end_dt:
        lines.append(f"모집기간: {start_dt} ~ {end_dt}")
    elif end_dt:
        lines.append(f"마감일: {end_dt}")
    if isinstance(dday, int):
        lines.append(f"D-day: {dday}")

    header_block = "\n".join(lines)
    if detail_text:
        return f"{header_block}\n\n{detail_text}".strip()
    return header_block


def _fetch_detail(
    session: requests.Session, jopen_id: int, reg_op_id: str
) -> str:
    url = DETAIL_URL_TEMPLATE.format(jopen_id=jopen_id, reg_op_id=reg_op_id or "NCH")
    resp = session.get(
        url,
        headers={
            "Referer": LIST_PAGE_URL,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            ),
        },
        timeout=REQUEST_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return _extract_detail_text(resp.text)


# ─────────────────────────────────────────────────────────────────────────────
# Public entrypoint
# ─────────────────────────────────────────────────────────────────────────────
def fetch() -> list[dict]:
    """NCSOFT 자체 채용 (Spring SSR + /interface/apply/list JSON API)."""
    session, csrf = _bootstrap_session()
    items = _fetch_all_records(session, csrf)
    records: list[dict] = []

    for item in items:
        jid = item.get("jopenId")
        if jid is None:
            continue
        reg_op_id = (item.get("regOpId") or "NCH").strip() or "NCH"
        posting_url = DETAIL_URL_TEMPLATE.format(jopen_id=jid, reg_op_id=reg_op_id)

        detail_text = ""
        try:
            detail_text = _fetch_detail(session, jid, reg_op_id)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[ncsoft] detail jopenId={jid} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        polite_sleep()

        raw_text = _build_raw_text(item, detail_text)
        if not raw_text:
            continue
        records.append(
            make_record(
                source=SOURCE,
                posting_url=posting_url,
                raw_text=raw_text,
            )
        )

    print(f"[ncsoft] done: records={len(records)}", file=sys.stderr)
    return records
