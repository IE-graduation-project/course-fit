"""GreetingHR ATS SaaS fetcher (한국 다수 회사 통합).

GreetingHR 은 ATS SaaS 로, 두 도메인 패턴을 동시에 지원:
    A. 표준 서브도메인: https://{slug}.career.greetinghr.com/
    B. 커스텀 도메인:    https://careers.kakaoent.com/  (회사가 직접 별칭 도메인 사용)

대상 (한국 본사·법인 한정, 라운드 4 검증 슬러그 포함):
    표준 슬러그
        - kurly (컬리)             - kakaopay (카카오페이)
        - kakaomobility (카카오모빌리티) - kakaoenterprise (카카오엔터프라이즈)
        - upstage (Upstage)         - rebellions (Rebellions)
        - makinarocks (MakinaRocks)  - 11st (11번가, 가능성)
        - socar (쏘카, 가능성)
    커스텀 도메인
        - 카카오엔터테인먼트  https://careers.kakaoent.com
        - 카카오게임즈        https://recruit.kakaogames.com
        - 데브시스터즈        https://careers.devsisters.com

robots.txt (모든 GreetingHR 호스트 공통 패턴):
    Allow:    /
    Disallow: /o/*/apply, /ko/o/*/apply, /en/o/*/apply, /m/*, /a/*
즉 공고 상세 (`/o/{id}`, `/ko/o/{id}`) 자체는 허용. 지원 페이지만 차단.

회사별 fetch 단위 try/except 로 격리 — 한 회사 실패가 전체를 죽이지 않음
(슬러그/도메인 추측 일부는 실측에서 fail 가능성 있음).

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


# slug -> {"name": 한글명, "base": optional custom base URL}
# base 가 없으면 표준 패턴 https://{slug}.career.greetinghr.com 사용
COMPANIES: dict[str, dict] = {
    # 라운드 1 (검증)
    "kurly": {"name": "컬리"},
    "kakaopay": {"name": "카카오페이"},
    "kakaomobility": {"name": "카카오모빌리티"},
    # 라운드 4 — 표준 슬러그
    "upstage": {"name": "Upstage"},
    "rebellions": {"name": "Rebellions"},
    "makinarocks": {"name": "MakinaRocks"},
    "kakaoenterprise": {"name": "카카오엔터프라이즈"},
    "11st": {"name": "11번가"},
    # 라운드 4 — 커스텀 도메인
    "kakaoent": {"name": "카카오엔터테인먼트", "base": "https://careers.kakaoent.com"},
    "kakaogames": {"name": "카카오게임즈", "base": "https://recruit.kakaogames.com"},
    "devsisters": {"name": "데브시스터즈", "base": "https://careers.devsisters.com"},
    # 라운드 6 신규 — 엔터·콘텐츠
    "hybe": {"name": "하이브"},
    "wavve": {"name": "웨이브"},
    "seoulauction": {"name": "서울옥션"},
    # 라운드 6 신규 — 패션·이커머스·D2C
    "musinsa": {"name": "무신사"},
    "wconcept": {"name": "W컨셉"},
    "idus": {"name": "아이디어스"},
    "craver-corp": {"name": "크레이버"},
    # 라운드 6 신규 — 트래블·항공
    "myrealtrip": {"name": "마이리얼트립"},
    "tripbtoz": {"name": "트립비토즈"},
    "gccompany": {"name": "여기어때"},
    "aerok-recruiter": {"name": "에어로케이항공"},
    # 라운드 6 신규 — 핀테크·증권·암호화폐·송금
    "wadiz": {"name": "와디즈"},
    "finda": {"name": "핀다"},
    "kbsec": {"name": "KB증권"},
    "korbit": {"name": "코빗"},
    "gme": {"name": "글로벌머니익스프레스"},
    # 라운드 6 신규 — AI·에듀테크
    "scatterlab": {"name": "스캐터랩(이루다)"},
    "qanda": {"name": "QANDA(매스프레소)"},
    # 라운드 6 신규 — 광고·마케팅·미디어
    "buzzvil": {"name": "버즈빌"},
    "dable": {"name": "데이블"},
    "echomarketing": {"name": "에코마케팅"},
    "playd": {"name": "플레이디"},
    # 라운드 6 신규 — 게임
    "epidgames": {"name": "에피드게임즈"},
    # 라운드 6 신규 — 그룹사·대기업·산업
    "lf": {"name": "LF그룹"},
    "oci": {"name": "OCI그룹"},
    "hecto": {"name": "Hecto Group"},
    "dongkuk": {"name": "동국제강그룹"},
    "phcgroup": {"name": "PHC Group"},
    "gsitm": {"name": "GS ITM"},
    "kovahr": {"name": "벤처기업협회 HR브릿지"},
    "nice": {"name": "NICE그룹"},
    "enf-recruit": {"name": "한국알콜그룹"},
    "kcenc": {"name": "KC E&C"},
    "daangnservice": {"name": "당근서비스"},
    "cj-recruit": {"name": "CJ"},
    # 라운드 6 신규 — 학습·법률
    "yanadoo": {"name": "야나두"},
    "lbox": {"name": "엘박스"},
    # 라운드 6 신규 — ATS 본사·기타
    "doodlin": {"name": "두들린(그리팅 본사)"},
    "ablelabs": {"name": "에이블랩스"},
}


def _base_url(slug: str, conf: dict) -> str:
    base = conf.get("base")
    if base:
        return base.rstrip("/")
    return f"https://{slug}.career.greetinghr.com"

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
OPENING_PATH_RE = re.compile(r"/o/(\d+)$")
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)
MIN_RAW_TEXT_LEN = 80


def _collect_opening_ids(base: str) -> list[str]:
    """sitemap.xml 에서 `/o/{id}` 경로의 ID 만 추려 정렬 반환."""
    url = f"{base}/sitemap.xml"
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


def _fetch_company(slug: str, conf: dict) -> list[dict]:
    company_kr = conf["name"]
    base = _base_url(slug, conf)
    ids = _collect_opening_ids(base)
    print(
        f"[greetinghr] {slug} ({company_kr}): sitemap openings = {len(ids)}",
        file=sys.stderr,
    )

    records: list[dict] = []
    source = f"Greeting:{slug}"
    for idx, opening_id in enumerate(ids):
        polite_sleep()  # 첫 호출 직전에도 대기 (sitemap 직후라서 OK)
        detail_url = f"{base}/ko/o/{opening_id}"
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
    """GreetingHR 다수 회사 통합 채용공고 수집."""
    all_records: list[dict] = []
    items = list(COMPANIES.items())
    for idx, (slug, conf) in enumerate(items):
        try:
            recs = _fetch_company(slug, conf)
        except Exception as exc:  # noqa: BLE001 — 회사 단위 격리
            print(
                f"[greetinghr] {slug} 실패: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            recs = []
        print(
            f"[greetinghr] {slug} ({conf['name']}): {len(recs)} records",
            file=sys.stderr,
        )
        all_records.extend(recs)
        if idx < len(items) - 1:
            polite_sleep()
    return all_records
