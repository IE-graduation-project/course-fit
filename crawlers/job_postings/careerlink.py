"""careerlink.kr (InHR) ATS SaaS fetcher — 한국 금융·대기업 채용.

대상: https://{slug}.careerlink.kr/jobs  (Next.js SSR, 테넌트별 서브도메인)

robots.txt 정책 (실측 2026-05-10):
    - **Disallow: /**  ← wooribank/kbfg/samsung/posco/kdb/shinhan/hana/sk/
      sktelecom/lotte/cj/kt/lg/kia/nh ... (대부분) → 본 모듈에서 제외
    - /admin·/my-page 등만 차단 ← **ibk, hyundai** → /jobs 허용

수집: /jobs GET → __NEXT_DATA__ → 빈 테넌트(subDmn=='') skip →
자기 호스트 `/jobs/{RC + 14자리}` 패턴 추출 → 상세 GET → page-builder
텍스트 노드 평문화. 본문 rich-text 는 CSR 로딩이라 SSR 셸만 잡힘 (추후
권한 API 키 또는 Playwright 확장으로 본문 보강 + 막힌 슬러그도 허가 후 추가).
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)


# slug -> 한글 회사명. robots.txt 가 /jobs 를 허용하는 슬러그만 등재.
COMPANIES: dict[str, str] = {
    "ibk": "IBK기업은행",
    "hyundai": "현대그룹",
}

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
SOURCE_PREFIX = "Careerlink"
MIN_RAW_TEXT_LEN = 60
TEXT_NODE_TYPES = {"TEXT", "RICH-TEXT", "TITLE", "PARAGRAPH", "STRING"}


def _parse_next_data(html_text: str) -> dict[str, Any] | None:
    m = NEXT_DATA_RE.search(html_text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _company_info(next_data: dict[str, Any]) -> dict[str, str]:
    """coInf dict (coNm/grpCoNo/subDmn) 또는 빈 dict."""
    try:
        coinf = (
            next_data.get("props", {})
            .get("pageProps", {})
            .get("middlewareData", {})
            .get("companyDataFromSubdomain", {})
            .get("coInf", {})
        )
    except AttributeError:
        return {}
    if not isinstance(coinf, dict):
        return {}
    return {k: v for k, v in coinf.items() if isinstance(v, str)}


def _collect_rcrt_ids(html_text: str, slug: str) -> list[str]:
    """SSR HTML 에서 자기 호스트 `/jobs/{RC...}` 만 추려 정렬 반환."""
    own_host = f"{slug}.careerlink.kr"
    ids: list[str] = []
    seen: set[str] = set()
    patterns = [
        re.compile(rf"https?://{re.escape(own_host)}/jobs/(RC\d{{14}})"),
        re.compile(r'"/jobs/(RC\d{14})"'),
    ]
    for pat in patterns:
        for m in pat.finditer(html_text):
            rid = m.group(1)
            if rid not in seen:
                seen.add(rid)
                ids.append(rid)
    return ids


def _extract_text_nodes(obj: Any, sink: list[str]) -> None:
    """page-builder 스키마에서 type ∈ TEXT_NODE_TYPES 인 value 만 수집."""
    if isinstance(obj, dict):
        t = obj.get("type")
        v = obj.get("value")
        if (
            isinstance(t, str)
            and t.upper() in TEXT_NODE_TYPES
            and isinstance(v, str)
            and v.strip()
        ):
            cleaned = html_to_text(v) if "<" in v else v.strip()
            if cleaned:
                sink.append(cleaned)
        for vv in obj.values():
            _extract_text_nodes(vv, sink)
    elif isinstance(obj, list):
        for vv in obj:
            _extract_text_nodes(vv, sink)


def _build_raw_text(
    *, company_kr: str, rcrt_no: str, posting_url: str, html_text: str
) -> str:
    next_data = _parse_next_data(html_text) or {}
    pp = next_data.get("props", {}).get("pageProps", {}) if isinstance(next_data, dict) else {}

    chunks: list[str] = []
    _extract_text_nodes(pp, chunks)

    seen: set[str] = set()
    uniq: list[str] = []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    body = "\n".join(uniq)

    header = "\n".join([
        f"[{company_kr}] {rcrt_no}",
        f"채용공고 ID: {rcrt_no}",
        f"공고 URL: {posting_url}",
    ])
    return f"{header}\n\n{body}".strip() if body else header


def _fetch_company(slug: str, company_kr: str) -> list[dict]:
    base = f"https://{slug}.careerlink.kr"
    list_url = f"{base}/jobs"
    try:
        resp = http_get(list_url)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[careerlink] {slug} jobs GET 실패: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []

    next_data = _parse_next_data(resp.text)
    if not next_data:
        print(f"[careerlink] {slug}: __NEXT_DATA__ 없음, skip", file=sys.stderr)
        return []

    coinf = _company_info(next_data)
    if not coinf.get("subDmn"):
        print(f"[careerlink] {slug}: 빈 테넌트 skip", file=sys.stderr)
        return []

    display_name = (coinf.get("coNm") or "").strip() or company_kr
    rcrt_ids = _collect_rcrt_ids(resp.text, slug)
    print(
        f"[careerlink] {slug} ({display_name}): rcrtNo={len(rcrt_ids)}",
        file=sys.stderr,
    )

    records: list[dict] = []
    source = f"{SOURCE_PREFIX}:{slug}"
    for rid in rcrt_ids:
        polite_sleep()
        detail_url = f"{base}/jobs/{rid}"
        try:
            detail_resp = http_get(detail_url)
        except Exception as exc:  # noqa: BLE001 — 단건 격리
            print(
                f"[careerlink] {slug}/{rid} GET 실패: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            continue

        raw_text = _build_raw_text(
            company_kr=display_name,
            rcrt_no=rid,
            posting_url=detail_url,
            html_text=detail_resp.text,
        )
        if len(raw_text) < MIN_RAW_TEXT_LEN:
            continue
        records.append(
            make_record(source=source, posting_url=detail_url, raw_text=raw_text)
        )

    return records


def fetch() -> list[dict]:
    """careerlink.kr (InHR) 다수 회사 통합 채용공고 수집."""
    all_records: list[dict] = []
    items = list(COMPANIES.items())
    for idx, (slug, company_kr) in enumerate(items):
        try:
            recs = _fetch_company(slug, company_kr)
        except Exception as exc:  # noqa: BLE001 — 회사 단위 격리
            print(
                f"[careerlink] {slug} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            recs = []
        print(
            f"[careerlink] {slug} ({company_kr}): {len(recs)} records",
            file=sys.stderr,
        )
        all_records.extend(recs)
        if idx < len(items) - 1:
            polite_sleep()
    return all_records
