"""한국 메인 IT/유통 5사 자체 채용 사이트 통합 크롤러 (best-effort).

대상 (한국 본사·법인) + 추출 방식:
    1. 무신사   — Greeting SaaS, /o/{id} 페이지의 __NEXT_DATA__.dehydratedState
                  에 openingsInfo (title/detail HTML) 인라인.
    2. 우아한   — Vue SPA, lazy-load route chunk 에서만 API 호출. SKIP.
    3. 야놀자   — Greeting 랜딩 + 외부 Workday ATS. Workday CXS API 호출 시점에
                  502/maintenance. SKIP.
    4. 두나무   — Next.js App Router RSC, /detail/{id} 페이지의 next_f stream
                  에 board 단위 모든 공고 본문 인라인.
    5. SK      — ASP.NET MVC, /Recruit/GetRecruitList POST 가 anti-bot/세션
                  검증으로 Error 페이지 반환. sitemap 도 정적 페이지만. SKIP.

robots.txt 모두 직접 확인 (2026-05-10): 5사 모두 Allow `/`. 무신사·야놀자는
`/apply` 만 Disallow — 본 크롤러는 listing/detail 만 접근하므로 매너 위반 없음.
"""
from __future__ import annotations

import html as _html
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


# 본문 길이 임계 — 헤더만 있는 빈 공고도 수록하되 너무 짧으면 메타 보강.
MIN_RAW_TEXT_LEN = 100


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------


def _extract_next_data(html: str) -> dict | None:
    """`<script id="__NEXT_DATA__">{...}</script>` 추출."""
    m = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _greeting_opening_record(
    *,
    source: str,
    posting_url: str,
    opening_info: dict,
    company_kr: str,
    division_name: str = "",
) -> dict:
    """Greeting (`openingsInfo`) → make_record."""
    title = (opening_info.get("title") or "").strip()
    detail_html = opening_info.get("detail") or ""
    body = html_to_text(_html.unescape(detail_html))

    header_lines = [f"[{company_kr}] {title}"]
    if division_name:
        header_lines.append(f"부서: {division_name}")
    open_date = opening_info.get("openDate")
    if open_date:
        header_lines.append(f"공고일: {open_date}")
    header = "\n".join(ln for ln in header_lines if ln)

    raw_text = f"{header}\n\n{body}".strip() if body else header
    if len(raw_text) < MIN_RAW_TEXT_LEN:
        # 보강: opening id 라도 붙여 최소 검색 가능성 확보.
        oid = opening_info.get("openingId")
        if oid is not None:
            raw_text = f"{raw_text}\nopeningId: {oid}"
    return make_record(
        source=source,
        posting_url=posting_url,
        raw_text=raw_text,
    )


# ---------------------------------------------------------------------------
# 1. 무신사 (Greeting SaaS, 132+ openings)
# ---------------------------------------------------------------------------


MUSINSA_BASE = "https://www.musinsacareers.com"


def _fetch_musinsa() -> list[dict]:
    """무신사: 홈에서 `/o/{id}` 수집 → 각 상세 페이지 __NEXT_DATA__ 파싱."""
    home = http_get(MUSINSA_BASE + "/").text
    opening_ids: list[str] = sorted(
        set(re.findall(r"/o/(\d+)", home)),
        key=lambda s: -int(s),  # 최신부터
    )
    if not opening_ids:
        raise RuntimeError("musinsa: opening id를 찾지 못함 (/o/{id} 패턴 0건)")
    print(
        f"[musinsa] 홈에서 {len(opening_ids)}건 opening id 발견",
        file=sys.stderr,
    )

    records: list[dict] = []
    for idx, oid in enumerate(opening_ids):
        url = f"{MUSINSA_BASE}/o/{oid}"
        try:
            resp = http_get(url)
            data = _extract_next_data(resp.text)
            if not data:
                continue
            queries = (
                data.get("props", {})
                .get("pageProps", {})
                .get("dehydratedState", {})
                .get("queries", [])
            )
            opening_info: dict[str, Any] | None = None
            for q in queries:
                qk = q.get("queryKey") or []
                if isinstance(qk, list) and "getOpeningById" in qk:
                    body = q.get("state", {}).get("data")
                    if isinstance(body, dict):
                        inner = body.get("data") or {}
                        if isinstance(inner, dict):
                            opening_info = inner.get("openingsInfo")
                    break
            if not opening_info:
                continue
            # workspaceDivision.division 은 케이스에 따라 str 또는 {"id","name"} dict.
            ws_div_raw = (opening_info.get("workspaceDivision") or {}).get("division")
            if isinstance(ws_div_raw, dict):
                division = ws_div_raw.get("name") or ""
            elif isinstance(ws_div_raw, str):
                division = ws_div_raw
            else:
                division = ""
            records.append(
                _greeting_opening_record(
                    source="Musinsa",
                    posting_url=url,
                    opening_info=opening_info,
                    company_kr="무신사",
                    division_name=division,
                )
            )
        except Exception as exc:  # noqa: BLE001 — per-opening 격리
            print(
                f"[musinsa] /o/{oid} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        finally:
            polite_sleep()

        # 매너: 너무 많은 페이지 fetch 방지. 130개 가량이면 ~3분 — OK.
    print(f"[musinsa] {len(records)} records", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# 2. 우아한형제들 (Vue SPA — SKIP)
# ---------------------------------------------------------------------------


def _fetch_woowahan() -> list[dict]:
    """우아한: Vue SPA, lazy-load route chunk 에서만 API 호출 — selenium 필요. SKIP."""
    raise RuntimeError(
        "woowahan: client-side SPA — 정적 HTML/CDN 에 공고 데이터 없음 (selenium 필요)"
    )


# ---------------------------------------------------------------------------
# 3. 야놀자 (Greeting landing → Workday ATS)
# ---------------------------------------------------------------------------


YANOLJA_BASE = "https://careers.yanolja.co"


def _fetch_yanolja() -> list[dict]:
    """야놀자: careers.yanolja.co 는 Greeting Career 랜딩이지만 페이지 sections
    안에 opening list 가 없고, '지원하기' 버튼이 외부 Workday ATS
    (yanolja.wd102.myworkdayjobs.com/External_Yanolja) 로 보냄.

    Workday CXS API (`/wday/cxs/yanolja/External_Yanolja/jobs`) 호출 시도했으나
    크롤링 시점 (2026-05-10) 502 + maintenance redirect 응답. robots 자체는 Allow
    이므로 점검 종료 후 재시도 가능. 현재는 skip.
    """
    home = http_get(YANOLJA_BASE + "/").text
    next_data = _extract_next_data(home)
    apply_url = ""
    if next_data:
        try:
            page = (
                next_data["props"]["pageProps"]["dehydratedState"]["queries"][1][
                    "state"
                ]["data"]["page"]
            )
            for s in page.get("sections", []):
                if s.get("name") == "지원하기":
                    apply_url = (
                        s["layouts"][0]["columns"][0]["blocks"][0]
                        .get("link", {})
                        .get("url", "")
                    )
                    break
        except (KeyError, IndexError, TypeError):
            pass
    raise RuntimeError(
        f"yanolja: ATS 가 외부 Workday ({apply_url or 'unresolved'}) 로 위임. "
        "Workday CXS API 시도 시 502/maintenance — skip"
    )


# ---------------------------------------------------------------------------
# 4. 두나무 (Next.js App Router, RSC payload)
# ---------------------------------------------------------------------------


DUNAMU_BASE = "https://careers.dunamu.com"


def _dunamu_decode_flow(html: str) -> str:
    """`self.__next_f.push([1,"..."])` payload 들을 이어붙이고 JS string 이스케이프
    해제. RSC chunk 의 `<id>:T<hex_len>,<content>` 표기를 인덱싱하기 위함."""
    pushes = re.findall(
        r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)+)"\]\)',
        html,
    )
    flow = ""
    for p in pushes:
        try:
            decoded = (
                bytes(p, "utf-8")
                .decode("unicode_escape")
                .encode("latin-1", "replace")
                .decode("utf-8", "replace")
            )
        except Exception:  # noqa: BLE001
            decoded = p
        flow += decoded
    return flow


def _dunamu_parse_chunks(flow: str) -> dict[str, str]:
    """RSC 스트림에서 `<chunkId>:T<hexLen>,<content>` 패턴 추출 → dict."""
    chunks: dict[str, str] = {}
    for m in re.finditer(r"([0-9a-f]+):T([0-9a-f]+),", flow):
        cid = m.group(1)
        clen = int(m.group(2), 16)
        start = m.end()
        chunks[cid] = flow[start : start + clen]
    return chunks


def _dunamu_extract_positions(flow: str) -> list[dict]:
    """dehydratedState 안의 모든 `content` 객체를 정규식으로 골라낸다.

    각 content 는 `{"jobNoticeId":...,"positionId":...,"jobNoticeName":...,
    "jobNoticeContent":"$<chunkId>","jobGroupCode":...,"experienceLevel":...,
    "employmentType":..., "workLocation":{"street":...,"detail":...}, ...}`.
    JSON parser 대신 필요한 필드만 정규식으로 뽑아 안전성 확보.
    """
    out: list[dict] = []
    pattern = re.compile(
        r'"jobNoticeId":(\d+),'
        r'"positionId":(\d+),'
        r'"jobNoticeName":"([^"]+)",'
        r'"jobNoticeContent":"\$([0-9a-f]+)",'
        r'"jobGroupCode":"([^"]+)",'
        r'"experienceLevel":"([^"]+)",'
        r'"employmentType":"([^"]+)"'
        r'(?:,"workLocationName":"([^"]*)")?'
    )
    seen: set[str] = set()
    for m in pattern.finditer(flow):
        position_id = m.group(2)
        if position_id in seen:
            continue
        seen.add(position_id)
        out.append(
            {
                "jobNoticeId": m.group(1),
                "positionId": position_id,
                "jobNoticeName": m.group(3),
                "contentChunkId": m.group(4),
                "jobGroupCode": m.group(5),
                "experienceLevel": m.group(6),
                "employmentType": m.group(7),
                "workLocationName": m.group(8) or "",
            }
        )
    return out


def _fetch_dunamu() -> list[dict]:
    """두나무: 홈에서 모든 position 발견 → 한 detail 페이지만 fetch 해도 같은
    jobBoardCode 안의 모든 공고 데이터가 RSC 에 인라인됨. 다만 board 가 여러 개일
    수 있으므로 각 positionId 의 `/detail/{id}` 를 한 번씩 fetch 해 보강.

    URL convention: 사용자가 보는 detail URL 은 `/detail/{positionId}` 이며,
    `/jobs/{id}` 는 marketing redirect (307→/tech2026 등). robots.txt 는 fully open.
    """
    home = http_get(DUNAMU_BASE + "/").text
    home_flow = _dunamu_decode_flow(home)
    home_positions = _dunamu_extract_positions(home_flow)

    # fallback: 홈 페이지는 jobBoard 의 단순 listing (`{"id":...}`) 만 가진 경우가
    # 많다. 본문은 /detail/{positionId} 에서 보강한다.
    if not home_positions:
        simple = re.findall(
            r'\{"id":(\d+),"name":"([^"]+)","jobGroupCode":"([^"]+)",'
            r'"experienceLevel":"([^"]+)","employmentType":"([^"]+)"\}',
            home_flow,
        )
        if not simple:
            raise RuntimeError("dunamu: 홈 RSC 에서 jobs/positions 패턴 미발견")
        for jid, name, jg, exp, emp in simple:
            home_positions.append(
                {
                    "jobNoticeId": "",
                    "positionId": jid,
                    "jobNoticeName": name,
                    "contentChunkId": "",
                    "jobGroupCode": jg,
                    "experienceLevel": exp,
                    "employmentType": emp,
                    "workLocationName": "",
                }
            )

    print(
        f"[dunamu] 홈에서 {len(home_positions)}개 position 발견",
        file=sys.stderr,
    )

    # 한 detail 페이지로 jobBoard 단위 본문을 수집
    seen_boards_by_first_pid: dict[str, dict[str, str]] = {}
    records: list[dict] = []

    for p in home_positions:
        pid = p["positionId"]
        url = f"{DUNAMU_BASE}/detail/{pid}"
        body_html = ""
        full_meta = p

        try:
            detail = http_get(url).text
            flow = _dunamu_decode_flow(detail)
            chunks = _dunamu_parse_chunks(flow)
            # 동일 board 의 모든 position 메타도 같이 들어있을 수 있음
            board_positions = _dunamu_extract_positions(flow)
            for bp in board_positions:
                if bp["positionId"] == pid:
                    full_meta = bp
                    break
            cid = full_meta.get("contentChunkId") or ""
            body_html = chunks.get(cid, "")
        except Exception as exc:  # noqa: BLE001
            print(
                f"[dunamu] /detail/{pid} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        finally:
            polite_sleep()

        body = html_to_text(body_html) if body_html else ""
        title = full_meta.get("jobNoticeName") or p["jobNoticeName"]
        header_lines = [f"[두나무] {title}"]
        jg = full_meta.get("jobGroupCode") or p["jobGroupCode"]
        if jg:
            header_lines.append(f"직군: {jg.replace('T_','').replace('_',' ').title()}")
        exp = full_meta.get("experienceLevel") or p["experienceLevel"]
        if exp and exp != "NONE":
            header_lines.append(f"경력: {exp}")
        emp = full_meta.get("employmentType") or p["employmentType"]
        if emp and emp != "NONE":
            header_lines.append(f"고용형태: {emp}")
        loc = full_meta.get("workLocationName") or ""
        if loc:
            header_lines.append(f"근무지: {loc}")
        header = "\n".join(header_lines)
        raw_text = f"{header}\n\n{body}".strip() if body else header
        if len(raw_text) < MIN_RAW_TEXT_LEN:
            raw_text = f"{raw_text}\npositionId: {pid}"
        records.append(
            make_record(
                source="Dunamu",
                posting_url=url,
                raw_text=raw_text,
            )
        )
    print(f"[dunamu] {len(records)} records", file=sys.stderr)
    return records


# ---------------------------------------------------------------------------
# 5. SK Careers (ASP.NET — SKIP)
# ---------------------------------------------------------------------------


def _fetch_sk() -> list[dict]:
    """SK Careers: `/Recruit/GetRecruitList` 가 ASP.NET MVC 컨트롤러로
    `$.post` 호출. 모든 form 필드 + Referer + X-Requested-With + 세션 쿠키를
    셋업해 호출해도 302 → /Error/Index 로 리다이렉트 (anti-bot 가능성).
    sitemap.xml 도 정적 페이지만 노출 — 개별 recruit URL 미포함. skip."""
    raise RuntimeError(
        "sk: GetRecruitList POST 가 anti-bot/세션 검증으로 Error 페이지 반환. "
        "sitemap 에도 개별 공고 URL 없음 — skip"
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def fetch() -> list[dict]:
    """무신사·우아한·야놀자·두나무·SK 5사 best-effort 통합."""
    records: list[dict] = []
    for company_fn in [
        _fetch_musinsa,
        _fetch_woowahan,
        _fetch_yanolja,
        _fetch_dunamu,
        _fetch_sk,
    ]:
        try:
            recs = company_fn()
            records.extend(recs)
        except Exception as exc:  # noqa: BLE001
            print(f"[{company_fn.__name__}] skip: {exc}", file=sys.stderr)
        polite_sleep()
    return records


if __name__ == "__main__":
    out = fetch()
    print(f"\n=== TOTAL: {len(out)} records ===", file=sys.stderr)
    if out:
        print(json.dumps(out[0], ensure_ascii=False, indent=2))
