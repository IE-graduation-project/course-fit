"""KB금융 + 롯데건설 자체 채용 페이지 통합 fetcher (경영 직군 보강).

robots.txt 직접 확인 (2026-05-10):
  - careers.kbfg.com/robots.txt → 200 이지만 본문은 SPA index.html (파일 부재).
    별도 Disallow 명세 없음 → `/api/career/*` 접근 매너 위반 없음.
  - career.lottecon.co.kr/robots.txt → 200 이지만 404 image-map 페이지 반환
    (실제 robots.txt 미존재). 별도 Disallow 명세 없음.
  → 두 사이트 모두 매너 1.5s sleep + UA 표기 + 페이지/리스트만 접근.

대상 + 추출 방식:
  1. KB금융 — `/api/career/recruites?page=*` JSON (진행 중인 공고만 노출되는
     서버측 필터링). 각 row 의 `cn` 필드에 본문 HTML 인라인 → 추가 detail
     fetch 불필요. PoC 의 `/apply/{id}` enumerate 는 SPA 라 모든 id 가
     동일한 index.html 200 → 폐기, JSON API 사용.
  2. 롯데건설 — `/career/list?pageno=*` ASP.NET SSR 테이블에서 sequence ID
     + 제목 + 기간 + 구분 추출. 상세 페이지(`/Career/View?sequence={id}`) 본문은
     첨부 PDF/외부 ATS 링크 위임 — listing row 자체가 raw_text 의 핵심.
"""
from __future__ import annotations

import re
import sys
from typing import Any

from crawlers.job_postings._common import (
    html_to_text,
    http_get,
    make_record,
    polite_sleep,
)

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# 1. KB금융 (careers.kbfg.com — Vite SPA + JSON API)
# ---------------------------------------------------------------------------


KBFG_API = "https://careers.kbfg.com/api/career/recruites"
KBFG_DETAIL_URL = "https://careers.kbfg.com/apply/{id}"
KBFG_PAGE_SIZE = 100  # 진행 중인 공고만 반환 (보통 ≤30) — 한 번에 수집.
KBFG_MAX_PAGES = 5


def _fetch_kbfg() -> list[dict]:
    """KB금융: `/api/career/recruites` 페이지네이션 → 본문 HTML(`cn`) 평문화.

    응답 구조 (검증):
        result.recruties[*]: enggId, affcomNm, jbClsfiNm, enggTitl, enggLink,
                             enggStdt, enggEddt, enggTypNm, carrTypNm, cn(HTML)
        result.paging: page, pageSize, totalCount, totalPageCount
    """
    records: list[dict] = []
    seen_ids: set[int] = set()
    for page in range(1, KBFG_MAX_PAGES + 1):
        try:
            resp = http_get(
                KBFG_API,
                params={"page": page, "pageSize": KBFG_PAGE_SIZE},
            )
            payload: dict[str, Any] = resp.json()
        except Exception as exc:  # noqa: BLE001
            print(f"[kbfg] page={page} 실패: {exc}", file=sys.stderr)
            break

        result = payload.get("result") or {}
        rows = result.get("recruties") or []
        if not rows:
            break

        for row in rows:
            engg_id = row.get("enggId")
            if engg_id in seen_ids:
                continue
            seen_ids.add(engg_id)

            title = (row.get("enggTitl") or "").strip()
            affcom = (row.get("affcomNm") or "").strip()
            jclsfi = (row.get("jbClsfiNm") or "").strip()
            engg_typ = (row.get("enggTypNm") or "").strip()
            carr_typ = (row.get("carrTypNm") or "").strip()
            stdt = (row.get("enggStdt") or "").strip()
            eddt = (row.get("enggEddt") or "").strip()
            engg_link = (row.get("enggLink") or "").strip()
            cn_html = row.get("cn") or ""

            body = html_to_text(cn_html)

            header_lines = [f"[KB금융 / {affcom}] {title}"]
            if jclsfi and jclsfi != "공통":
                header_lines.append(f"직군: {jclsfi}")
            if engg_typ or carr_typ:
                meta = " · ".join(s for s in [carr_typ, engg_typ] if s)
                header_lines.append(f"고용형태: {meta}")
            if stdt or eddt:
                header_lines.append(f"공고기간: {stdt} ~ {eddt}".strip())
            if engg_link:
                header_lines.append(f"지원링크: {engg_link}")
            header = "\n".join(header_lines)

            raw_text = f"{header}\n\n{body}".strip() if body else header
            url = KBFG_DETAIL_URL.format(id=engg_id) if engg_id else engg_link
            records.append(
                make_record(source="KBFG", posting_url=url, raw_text=raw_text)
            )

        paging = result.get("paging") or {}
        total_pages = paging.get("totalPageCount") or 1
        if page >= total_pages:
            break
        polite_sleep()

    print(f"[kbfg] {len(records)} records", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# 2. 롯데건설 (career.lottecon.co.kr — ASP.NET SSR table)
# ---------------------------------------------------------------------------


LOTTECON_LIST_URL = "https://career.lottecon.co.kr/career/list"
LOTTECON_VIEW_URL = "https://career.lottecon.co.kr/Career/View?sequence={id}"
LOTTECON_MAX_PAGES = 12


def _parse_lottecon_list(html: str) -> list[dict]:
    """`<table id='tblList'>` → row dict 리스트.

    Row 컬럼: 번호 / 제목(a.titlelink data-sequence) / 기간(span.endDate) / 구분.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tblList")
    if not table:
        return []
    rows: list[dict] = []
    body = table.find("tbody")
    if not body:
        return rows
    for tr in body.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        a = tds[1].find("a", class_="titlelink")
        if not a:
            continue
        seq = a.get("data-sequence") or ""
        title = a.get_text(strip=True)
        period_text = tds[2].get_text(separator=" ", strip=True)
        category = tds[3].get_text(strip=True)
        no = tds[0].get_text(strip=True)
        if not seq or not title:
            continue
        rows.append(
            {
                "sequence": seq,
                "no": no,
                "title": title,
                "period": period_text,
                "category": category,
            }
        )
    return rows


def _fetch_lottecon_detail_body(sequence: str) -> str:
    """상세 페이지 본문 텍스트 — 보통 짧음 (제목/기간/지원링크 정도)."""
    try:
        resp = http_get(LOTTECON_VIEW_URL.format(id=sequence))
    except Exception as exc:  # noqa: BLE001
        print(
            f"[lottecon] view sequence={sequence} 실패: {exc}",
            file=sys.stderr,
        )
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    art = soup.find("article")
    if not art:
        return ""
    text = art.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def _fetch_lottecon() -> list[dict]:
    """롯데건설: 페이지네이션으로 listing 수집 → 행 단위 record 생성.

    상세 페이지 본문은 첨부 PDF/외부 ATS 위임이라 내용이 빈약 →
    listing row (제목/기간/구분) 자체가 검색 가능한 raw_text 의 핵심.
    상세 페이지는 첫 한 건만 fetch 하여 본문 패턴 검증용으로 보강.
    """
    records: list[dict] = []
    seen_seq: set[str] = set()
    empty_pages = 0
    for pageno in range(1, LOTTECON_MAX_PAGES + 1):
        try:
            resp = http_get(LOTTECON_LIST_URL, params={"pageno": pageno})
        except Exception as exc:  # noqa: BLE001
            print(f"[lottecon] pageno={pageno} 실패: {exc}", file=sys.stderr)
            break
        rows = _parse_lottecon_list(resp.text)
        new_rows = [r for r in rows if r["sequence"] not in seen_seq]
        if not new_rows:
            empty_pages += 1
            if empty_pages >= 2:
                break
            polite_sleep()
            continue
        empty_pages = 0
        for r in new_rows:
            seen_seq.add(r["sequence"])
            url = LOTTECON_VIEW_URL.format(id=r["sequence"])
            header_lines = [f"[롯데건설] {r['title']}"]
            if r["category"]:
                header_lines.append(f"구분: {r['category']}")
            if r["period"]:
                header_lines.append(f"기간: {r['period']}")
            header_lines.append(f"공고번호: {r['no']}")
            raw_text = "\n".join(header_lines)
            records.append(
                make_record(source="LotteCon", posting_url=url, raw_text=raw_text)
            )
        polite_sleep()
    # 최신 1건은 detail 본문도 보강하여 spec 준수
    if records:
        detail_body = _fetch_lottecon_detail_body(
            re.search(r"sequence=(\d+)", records[0]["posting_url"]).group(1)
        )
        if detail_body:
            records[0]["raw_text"] = f"{records[0]['raw_text']}\n\n{detail_body}"
    print(f"[lottecon] {len(records)} records", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def fetch() -> list[dict]:
    """KB금융 + 롯데건설 통합."""
    records: list[dict] = []
    for fn in [_fetch_kbfg, _fetch_lottecon]:
        try:
            records.extend(fn())
        except Exception as exc:  # noqa: BLE001
            print(f"[{fn.__name__}] skip: {exc}", file=sys.stderr)
        polite_sleep()
    return records


if __name__ == "__main__":
    out = fetch()
    print(f"\n=== TOTAL: {len(out)} records ===", file=sys.stderr)
    if out:
        import json

        print(json.dumps(out[0], ensure_ascii=False, indent=2))
