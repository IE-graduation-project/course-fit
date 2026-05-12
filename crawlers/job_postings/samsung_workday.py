"""삼성전자 Workday CXS Public API fetcher.

대상: Samsung Electronics 글로벌 채용 (한국 대기업 자체 페이지 중 유일하게
표준 Workday CXS API 노출). 경영 직군 backbone — 사업기획/마케팅/HR/재무/
전략/CSM/B2B 영업 + 엔지니어링 다수.

Workday CXS Public API (무인증):
    POST {tenant}/wday/cxs/sec/{site}/jobs
         body {"appliedFacets":{}, "limit":20, "offset":N, "searchText":""}
    GET  {tenant}/wday/cxs/sec/{site}{externalPath}
- 페이지네이션 limit/offset (limit=20 권장), Accept 에 application/xml 포함 필수.
- Accept-Language: ko 시 location/country/remoteType 등 일부 필드 한국어 번역.

스펙 노트 (검증 결과):
    - 같은 tenant 의 다른 site (Samsung_Jobs/External/Korea 등) 모두 비활성.
      Samsung_Careers 단일 site 만 사용 가능.
    - 한국 location 은 Workday 에 노출되지 않음 (US 306/Türkiye 42/France 27/
      Germany 19/India 16/Brazil 12 ...) — 삼성 한국 채용은 samsungcareers.com
      별도 시스템. 본 fetcher 는 글로벌 영문 공고를 수집 후 region 라벨링.

각 공고 dict 는 `make_record()` 로 `data/job_posting.csv` 컬럼과 1:1 매핑.
"""
from __future__ import annotations

import sys
import time
from typing import Any

import requests

from crawlers.job_postings._common import (
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT_SEC,
    html_to_text,
    make_record,
    polite_sleep,
)


WORKDAY_TENANT_BASE = "https://sec.wd3.myworkdayjobs.com/wday/cxs/sec"
SITE_NAME = "Samsung_Careers"
PAGE_SIZE = 20
MAX_RECORDS = 200  # PoC batch 상한 (전체 500+ 중)
DETAIL_DELAY_SEC = 0.3

LIST_ENDPOINT = f"{WORKDAY_TENANT_BASE}/{SITE_NAME}/jobs"
DETAIL_ENDPOINT_TPL = f"{WORKDAY_TENANT_BASE}/{SITE_NAME}{{external_path}}"
PUBLIC_URL_TPL = f"https://sec.wd3.myworkdayjobs.com/{SITE_NAME}{{external_path}}"

# Workday CXS 는 Accept 에 application/xml 가 포함돼야 200 (검증).
WORKDAY_HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "application/json,application/xml",
    "Content-Type": "application/json",
}

# 한국 location 식별 (ko 번역 + 영문 둘 다 cover).
KR_KEYWORDS = (
    "korea", "south korea", "republic of korea",
    "suwon", "seoul", "gumi", "asan", "hwaseong", "giheung",
    "수원", "서울", "구미", "아산", "화성", "기흥", "한국", "대한민국",
)


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_korea(*texts: str) -> bool:
    blob = " ".join(t for t in texts if t).lower()
    return any(k in blob for k in KR_KEYWORDS)


def _list_page(offset: int) -> dict[str, Any]:
    body = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""}
    resp = requests.post(
        LIST_ENDPOINT, json=body, headers=WORKDAY_HEADERS, timeout=REQUEST_TIMEOUT_SEC
    )
    resp.raise_for_status()
    return resp.json()


def _fetch_detail(external_path: str) -> dict[str, Any]:
    url = DETAIL_ENDPOINT_TPL.format(external_path=external_path)
    resp = requests.get(url, headers=WORKDAY_HEADERS, timeout=REQUEST_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.json()


def _build_raw_text(jpi: dict, stub: dict) -> str:
    title = _str(jpi.get("title")) or _str(stub.get("title"))
    location = _str(jpi.get("location")) or _str(stub.get("locationsText"))
    country = jpi.get("country")
    country_desc = _str(country.get("descriptor")) if isinstance(country, dict) else ""
    job_req_id = _str(jpi.get("jobReqId"))
    time_type = _str(jpi.get("timeType"))
    remote_type = _str(jpi.get("remoteType")) or _str(stub.get("remoteType"))
    posted_on = _str(jpi.get("postedOn")) or _str(stub.get("postedOn"))

    header_lines = [f"[삼성전자] {title}".strip()]
    if location:
        header_lines.append(f"위치: {location}")
    if country_desc and country_desc not in location:
        header_lines.append(f"국가: {country_desc}")
    if time_type:
        header_lines.append(f"고용형태: {time_type}")
    if remote_type:
        header_lines.append(f"근무방식: {remote_type}")
    if posted_on:
        header_lines.append(f"공고일: {posted_on}")
    if job_req_id:
        header_lines.append(f"공고번호: {job_req_id}")
    header = "\n".join(header_lines)

    body = html_to_text(_str(jpi.get("jobDescription")))
    return f"{header}\n\n{body}".strip() if body else header


def _process_posting(stub: dict, idx: int) -> dict | None:
    external_path = _str(stub.get("externalPath"))
    if not external_path:
        return None
    try:
        detail = _fetch_detail(external_path)
    except Exception as exc:  # noqa: BLE001 — 공고 단위 격리
        print(
            f"[samsung_workday] detail #{idx} 실패 ({external_path}): "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None

    jpi = detail.get("jobPostingInfo") or {}
    raw_text = _build_raw_text(jpi, stub)
    posting_url = _str(jpi.get("externalUrl")) or PUBLIC_URL_TPL.format(
        external_path=external_path
    )

    location = _str(jpi.get("location")) or _str(stub.get("locationsText"))
    country = jpi.get("country")
    country_desc = _str(country.get("descriptor")) if isinstance(country, dict) else ""
    region = "KR" if _is_korea(location, country_desc) else "Global"

    return make_record(
        source=f"SamsungWorkday:{region}",
        posting_url=posting_url,
        raw_text=raw_text,
    )


def fetch() -> list[dict]:
    """삼성전자 Workday Public API → list[record].

    PoC 배치 상한: MAX_RECORDS (=200) 건. 전체 500+ 중. 한국 location 비중은
    글로벌 tenant 특성상 0 ~ 소수 (별도 samsungcareers.com 보완 필요).
    """
    records: list[dict] = []
    offset = 0
    total: int | None = None
    seen_kr = 0
    seen_global = 0

    while len(records) < MAX_RECORDS:
        try:
            page = _list_page(offset)
        except Exception as exc:  # noqa: BLE001 — 페이지 단위 격리
            print(
                f"[samsung_workday] list offset={offset} 실패: "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            break

        if total is None:
            total = int(page.get("total") or 0)
            print(
                f"[samsung_workday] tenant total={total} (PoC cap={MAX_RECORDS})",
                file=sys.stderr,
            )

        postings = page.get("jobPostings") or []
        if not postings:
            break

        for stub in postings:
            if len(records) >= MAX_RECORDS:
                break
            rec = _process_posting(stub, len(records) + 1)
            if rec is None:
                continue
            if rec["source"].endswith(":KR"):
                seen_kr += 1
            else:
                seen_global += 1
            records.append(rec)
            time.sleep(DETAIL_DELAY_SEC)

        offset += PAGE_SIZE
        if total is not None and offset >= total:
            break
        polite_sleep()

    print(
        f"[samsung_workday] 완료: total_collected={len(records)} "
        f"(KR={seen_kr}, Global={seen_global}, tenant_total={total})",
        file=sys.stderr,
    )
    return records
