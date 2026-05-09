"""GreetingHR ATS SaaS fetcher (한국 3사 통합).

대상 (한국 본사·법인 한정):
    1. 컬리 (kurly)               — sitemap.xml 기반
    2. 카카오페이 (kakaopay)        — sitemap.xml 기반
    3. 카카오모빌리티 (kakaomobility) — sitemap.xml 기반

GreetingHR 은 ATS SaaS 로 호스팅 도메인이 회사별로 분리된다.
    https://{slug}.career.greetinghr.com/

robots.txt (3사 공통):
    Allow:    /
    Disallow: /o/*/apply, /ko/o/*/apply, /en/o/*/apply, /m/*, /a/*
즉 공고 상세 (`/o/{id}`, `/ko/o/{id}`) 자체는 허용. 지원 페이지만 차단.

수집 전략 (정적 HTML 만 사용 — selenium 불필요):
    1. `https://{slug}.career.greetinghr.com/sitemap.xml` 에서 `/o/{id}` URL 수집
       (이때 정적 페이지 — `/main`, `/process` 등 — 는 정규식으로 제외)
    2. 각 공고 상세 페이지 `https://{slug}.career.greetinghr.com/ko/o/{id}` 를
       GET → Next.js `__NEXT_DATA__` 인라인 JSON 파싱
    3. `props.pageProps.dehydratedState.queries[?].state.data.data` 에서 opening
       객체 추출 (queryKey 가 'getOpeningById' 인 항목)

Opening 객체 구조 (실측 2026-05):
    - openingsInfo.title                — 공고 제목 (str)
    - openingsInfo.detail               — 본문 HTML (rich text)
    - jobPositionSetting.jobPositions[] — 직무 메타 (field/occupation/place/employment)
    - groupInfo.name                    — 워크스페이스명 (예: '컬리 채용(Kurly Talent)')

각 공고 dict 는 `make_record()` 로 생성되어
`data/job_posting.csv` 의 컬럼 (job_id/source/posting_url/raw_text/crawled_at)
과 1:1 매핑된다.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any
from xml.etree import ElementTree as ET

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


# slug -> 표시용 한글명
COMPANIES: dict[str, str] = {
    "kurly": "컬리",
    "kakaopay": "카카오페이",
    "kakaomobility": "카카오모빌리티",
}

BASE_TEMPLATE = "https://{slug}.career.greetinghr.com"
SITEMAP_TEMPLATE = BASE_TEMPLATE + "/sitemap.xml"
DETAIL_TEMPLATE = BASE_TEMPLATE + "/ko/o/{opening_id}"

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
OPENING_PATH_RE = re.compile(r"/o/(\d+)$")
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
MIN_RAW_TEXT_LEN = 80


def _collect_opening_ids(slug: str) -> list[str]:
    """sitemap.xml 에서 `/o/{id}` 경로의 ID 만 추려 정렬 반환."""
    url = SITEMAP_TEMPLATE.format(slug=slug)
    resp = http_get(url, headers={"Accept": "application/xml, text/xml, */*"})
    root = ET.fromstring(resp.content)

    ids: list[str] = []
    for url_el in root.findall("sm:url", SITEMAP_NS):
        loc = url_el.findtext("sm:loc", default="", namespaces=SITEMAP_NS) or ""
        m = OPENING_PATH_RE.search(loc.strip())
        if m:
            ids.append(m.group(1))
    # sitemap 중복 제거 (순서 유지)
    seen: set[str] = set()
    uniq: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


def _extract_next_data(html_text: str) -> dict[str, Any] | None:
    m = NEXT_DATA_RE.search(html_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _find_opening_payload(next_data: dict[str, Any]) -> dict[str, Any] | None:
    """dehydratedState.queries 에서 getOpeningById 결과의 .data.data 반환."""
    try:
        queries = (
            next_data.get("props", {})
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [])
        )
    except AttributeError:
        return None

    for q in queries:
        key = q.get("queryKey") or []
        if any(isinstance(k, str) and "getOpeningById" in k for k in key):
            payload = (q.get("state") or {}).get("data") or {}
            inner = payload.get("data")
            if isinstance(inner, dict):
                return inner
    return None


def _job_position_meta(opening: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    """jobPositions → (직군 리스트, 직무 리스트, 근무지 리스트)."""
    jps = (opening.get("jobPositionSetting") or {}).get("jobPositions") or []
    fields: list[str] = []
    occupations: list[str] = []
    places: list[str] = []
    for jp in jps:
        f = ((jp or {}).get("workspaceField") or {}).get("field")
        o = ((jp or {}).get("workspaceOccupation") or {}).get("occupation")
        # workspaceJob (직무 세부) 도 있으면 함께
        j = ((jp or {}).get("workspaceJob") or {}).get("job")
        p_obj = (jp or {}).get("workspacePlace") or {}
        loc = p_obj.get("location") or p_obj.get("place")
        if isinstance(f, str) and f.strip():
            fields.append(f.strip())
        if isinstance(o, str) and o.strip():
            occupations.append(o.strip())
        if isinstance(j, str) and j.strip():
            occupations.append(j.strip())
        if isinstance(loc, str) and loc.strip():
            places.append(loc.strip())
    # dedup, 순서 유지
    return (
        list(dict.fromkeys(fields)),
        list(dict.fromkeys(occupations)),
        list(dict.fromkeys(places)),
    )


def _build_raw_text(opening: dict[str, Any], company_kr: str) -> str:
    info = opening.get("openingsInfo") or {}
    title = (info.get("title") or "").strip()
    detail_html = info.get("detail") or ""
    body = html_to_text(detail_html)

    fields, occupations, places = _job_position_meta(opening)

    header_lines = [f"[{company_kr}] {title}".strip()]
    if fields:
        header_lines.append(f"직군: {', '.join(fields)}")
    if occupations:
        header_lines.append(f"직무: {', '.join(occupations)}")
    if places:
        header_lines.append(f"근무지: {', '.join(places)}")
    header = "\n".join(ln for ln in header_lines if ln)

    combined = f"{header}\n\n{body}".strip() if body else header

    if len(combined) < MIN_RAW_TEXT_LEN:
        extras = []
        oid = info.get("openingId")
        if oid is not None:
            extras.append(f"opening_id: {oid}")
        opened = info.get("openDate")
        if opened:
            extras.append(f"openDate: {opened}")
        if extras:
            combined = f"{combined}\n" + "\n".join(extras)

    return combined


def _fetch_company(slug: str, company_kr: str) -> list[dict]:
    ids = _collect_opening_ids(slug)
    print(
        f"[greetinghr] {slug} ({company_kr}): sitemap openings = {len(ids)}",
        file=sys.stderr,
    )

    records: list[dict] = []
    source = f"Greeting:{slug}"
    for idx, opening_id in enumerate(ids):
        polite_sleep()  # 첫 호출 직전에도 대기 (sitemap 직후라서 OK)
        detail_url = DETAIL_TEMPLATE.format(slug=slug, opening_id=opening_id)
        try:
            resp = http_get(detail_url)
        except Exception as exc:  # noqa: BLE001 — 단건 격리
            print(
                f"[greetinghr] {slug}/{opening_id} GET 실패: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue

        next_data = _extract_next_data(resp.text)
        if not next_data:
            print(
                f"[greetinghr] {slug}/{opening_id} __NEXT_DATA__ 없음, skip",
                file=sys.stderr,
            )
            continue

        opening = _find_opening_payload(next_data)
        if not opening:
            print(
                f"[greetinghr] {slug}/{opening_id} opening payload 없음, skip",
                file=sys.stderr,
            )
            continue

        # 비공개/내려간 공고 (status != 'OPEN') 도 raw_text 는 만들 수 있지만,
        # GreetingHR 의 공개 sitemap 에 들어오는 시점에서 사실상 OPEN 만 노출됨.
        raw_text = _build_raw_text(opening, company_kr)
        records.append(
            make_record(
                source=source,
                posting_url=detail_url,
                raw_text=raw_text,
            )
        )
        # 진행 표시 (긴 회사 대비)
        if (idx + 1) % 25 == 0:
            print(
                f"[greetinghr] {slug}: {idx + 1}/{len(ids)} 진행",
                file=sys.stderr,
            )

    return records


def fetch() -> list[dict]:
    """GreetingHR 3사 통합 채용공고 수집."""
    all_records: list[dict] = []
    slugs = list(COMPANIES.items())
    for idx, (slug, company_kr) in enumerate(slugs):
        try:
            recs = _fetch_company(slug, company_kr)
        except Exception as exc:  # noqa: BLE001 — fetcher 단위 격리
            print(
                f"[greetinghr] {slug} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            recs = []
        print(
            f"[greetinghr] {slug} ({company_kr}): {len(recs)} records",
            file=sys.stderr,
        )
        all_records.extend(recs)
        if idx < len(slugs) - 1:
            polite_sleep()
    return all_records
