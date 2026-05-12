"""잡알리오 (재정경제부 공공기관 채용정보 조회서비스) OpenAPI fetcher.

엔드포인트 (data.go.kr 15125273, swagger 기준 실측):
    list   : GET https://apis.data.go.kr/1051000/recruitment/list
    detail : GET https://apis.data.go.kr/1051000/recruitment/detail

쿼리 파라미터 (필수/선택):
    serviceKey  — 인증키 (필수)
    numOfRows   — 페이지당 결과 수 (선택, default 10 추정)
    pageNo      — 페이지 번호 (선택)
    resultType  — 'json' | 'xml' (default json)
    detail 만   — recrutPblntSn (필수, list 의 PK)

응답 구조 (공공데이터포털 표준 envelope):
    {"resultCode": "INFO-00", "resultMsg": "NORMAL SERVICE.",
     "totalCount": N, "numOfRows": ..., "pageNo": ...,
     "result": [ { 공고 row ... } ]}
    (일부 API 는 response.body.items.item 패턴이지만 잡알리오는 result 배열 평면.)

수집 전략:
    1. /list 페이지네이션 — totalCount 까지 또는 MAX_RECORDS cap.
    2. list 응답에 recrutPbancTtl·instNm·workRgnLst·hireTypeLst·acdmcrSe·
       pbancBgngYmd/EndYmd·srcUrl 등 충분한 메타가 포함됨 (공공데이터포털 코드정의서 v1.2).
       본문 HTML 은 /detail 만 제공하지만, list 메타만으로도 직군 분류·키워드 매칭에는 충분.
       트래픽(일 1,000회) 절약을 위해 detail 호출은 ENABLE_DETAIL=False default 로 skip.
    3. polite_sleep(1.0) — 공공 API 라 보수적으로.

키 보관: .env (ALIO_API_KEY) — python-dotenv 로 자동 로드.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv

from crawlers.job_postings._common import (
    DEFAULT_HEADERS,
    REQUEST_TIMEOUT_SEC,
    html_to_text,
    make_record,
    polite_sleep,
)

load_dotenv()

API_BASE = "https://apis.data.go.kr/1051000/recruitment"
LIST_PATH = "/list"
DETAIL_PATH = "/detail"

PAGE_SIZE = 100
MAX_RECORDS = 500          # 일일 1,000회 한도 안전 cap (list 5p + detail off)
ENABLE_DETAIL = False      # True 면 회사당 +1회씩 추가 트래픽 — 기본 off
SLEEP_SEC = 1.0
SOURCE = "ALIO"


# ---------- HTTP ----------

def _api_get(path: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """공공데이터포털 GET. 401/SERVICE_KEY_* 응답은 None 으로 반환 (호출측에서 skip)."""
    url = f"{API_BASE}{path}"
    final_params = {"resultType": "json", **params}
    headers = {**DEFAULT_HEADERS, "Accept": "application/json, */*"}
    try:
        resp = requests.get(
            url, params=final_params, headers=headers, timeout=REQUEST_TIMEOUT_SEC
        )
    except requests.RequestException as exc:
        print(f"[alio] HTTP 실패 {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return None

    # 401 = 키 미활성 (data.go.kr 신청 직후 propagation 1~2h 소요).
    if resp.status_code == 401:
        print(
            "[alio] 401 Unauthorized — 키가 아직 전파되지 않았거나 만료됨. "
            "발급 직후라면 1~2시간 후 재시도. 응답: "
            + resp.text.strip()[:200],
            file=sys.stderr,
        )
        return None
    if resp.status_code != 200:
        print(
            f"[alio] {path} HTTP {resp.status_code}: {resp.text[:200]}",
            file=sys.stderr,
        )
        return None

    ct = resp.headers.get("Content-Type", "")
    if "json" not in ct.lower():
        # 키 오류 시 가끔 XML 로 SERVICE_KEY_NOT_REGISTERED_ERROR 가 옴.
        body = resp.text.strip()
        print(f"[alio] {path} non-JSON ({ct}): {body[:200]}", file=sys.stderr)
        return None
    try:
        return resp.json()
    except ValueError as exc:
        print(f"[alio] JSON parse 실패: {exc}", file=sys.stderr)
        return None


# ---------- 응답 envelope unwrap ----------

def _extract_items(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    """잡알리오 응답에서 (items, totalCount) 추출. envelope 변형 모두 흡수."""
    if not isinstance(payload, dict):
        return [], 0

    # 표준 케이스 1: 평면 — {result: [...], totalCount: N}
    if isinstance(payload.get("result"), list):
        items = payload["result"]
        total = int(payload.get("totalCount") or len(items))
        return items, total

    # 표준 케이스 2: response.body.items.item — 일부 공공 API 호환 path.
    body = (payload.get("response") or {}).get("body") or {}
    items_wrap = body.get("items")
    if isinstance(items_wrap, dict):
        item = items_wrap.get("item")
        if isinstance(item, list):
            return item, int(body.get("totalCount") or len(item))
        if isinstance(item, dict):
            return [item], 1
    if isinstance(items_wrap, list):
        return items_wrap, int(body.get("totalCount") or len(items_wrap))

    return [], 0


# ---------- raw_text 빌더 ----------

def _join_meta(*parts: str) -> str:
    return "  /  ".join(p for p in parts if p)


def _build_raw_text(item: dict[str, Any], detail_text: str = "") -> str:
    inst = (item.get("instNm") or "").strip()
    title = (item.get("recrutPbancTtl") or item.get("pbancTtl") or "").strip()
    # recrutPbancTtl 은 보통 이미 "[기관명] 제목" 형태 — 중복 prefix 회피
    if title.startswith("[") and inst and inst in title.split("]")[0]:
        header = title
    else:
        header = f"[{inst}] {title}".strip()

    # *NmLst (한글명) 우선, *Lst (코드) 는 fallback
    meta = _join_meta(
        f"채용분야: {item.get('ncsCdNmLst') or item.get('recrutSeNm') or item.get('recrutSe') or ''}".strip(": ").strip(),
        f"근무지: {item.get('workRgnNmLst') or item.get('workRgnLst') or ''}".strip(": ").strip(),
        f"학력: {item.get('acdmcrSeNm') or item.get('acdmcrSe') or ''}".strip(": ").strip(),
        f"고용형태: {item.get('hireTypeNmLst') or item.get('hireTypeLst') or ''}".strip(": ").strip(),
    )
    period = ""
    bgn = (item.get("pbancBgngYmd") or "").strip()
    end = (item.get("pbancEndYmd") or "").strip()
    if bgn or end:
        period = f"접수기간: {bgn} ~ {end}"

    # recrutNope 는 int 로 옴 — str 변환 후 strip
    nope_raw = item.get("recrutNope")
    nope = str(nope_raw).strip() if nope_raw not in (None, "") else ""
    nope_line = f"채용인원: {nope}" if nope else ""

    lines = [header]
    if meta:
        lines.append(meta)
    if period:
        lines.append(period)
    if nope_line:
        lines.append(nope_line)
    if detail_text:
        lines.append("")
        lines.append(detail_text)
    return "\n".join(lines).strip()


def _posting_url(item: dict[str, Any]) -> str:
    src = (item.get("srcUrl") or "").strip()
    if src:
        return src
    sn = item.get("recrutPblntSn") or item.get("pblntSn")
    if sn:
        return f"https://job.alio.go.kr/recruitView.do?idx={sn}"
    return "https://job.alio.go.kr/"


# ---------- 페이지네이션 ----------

def _fetch_list_page(api_key: str, page_no: int) -> tuple[list[dict[str, Any]], int]:
    payload = _api_get(
        LIST_PATH,
        {"serviceKey": api_key, "numOfRows": PAGE_SIZE, "pageNo": page_no},
    )
    if payload is None:
        return [], 0
    return _extract_items(payload)


def _fetch_detail(api_key: str, recrut_sn: Any) -> str:
    if not ENABLE_DETAIL or not recrut_sn:
        return ""
    payload = _api_get(
        DETAIL_PATH, {"serviceKey": api_key, "recrutPblntSn": recrut_sn}
    )
    if payload is None:
        return ""
    items, _ = _extract_items(payload)
    if not items:
        return ""
    detail = items[0]
    # detail 응답: 채용전형단계 (aplyQlfcCn 등) 또는 본문 HTML 후보 키들 시도.
    chunks: list[str] = []
    for key in ("aplyQlfcCn", "preferentialCn", "etcCn", "recrutCn"):
        v = detail.get(key)
        if v:
            chunks.append(html_to_text(str(v)))
    return "\n\n".join(c for c in chunks if c)


# ---------- 직군 통계 (보고용) ----------

_BIZ_KEYWORDS = (
    "경영", "기획", "전략", "재무", "회계", "인사", "HR", "총무",
    "마케팅", "홍보", "영업", "구매", "감사", "사무", "행정",
)


def _is_business(item: dict[str, Any]) -> bool:
    blob = " ".join(
        str(item.get(k) or "")
        for k in (
            "recrutPbancTtl",
            "pbancTtl",
            "ncsCdNmLst",
            "recrutSe",
            "ncsCdLst",
        )
    )
    return any(kw in blob for kw in _BIZ_KEYWORDS)


# ---------- entry ----------

def fetch() -> list[dict]:
    """잡알리오 OpenAPI — 공공기관 채용공시 통합."""
    api_key = os.environ.get("ALIO_API_KEY")
    if not api_key:
        print("[alio] ALIO_API_KEY 환경변수 없음 — skip", file=sys.stderr)
        return []

    records: list[dict] = []
    biz_count = 0
    page = 1
    total_count: int | None = None

    while len(records) < MAX_RECORDS:
        items, total = _fetch_list_page(api_key, page)
        if total_count is None and total:
            total_count = total
            print(
                f"[alio] totalCount={total_count} (cap {MAX_RECORDS})",
                file=sys.stderr,
            )
        if not items:
            break

        for item in items:
            if len(records) >= MAX_RECORDS:
                break
            if _is_business(item):
                biz_count += 1
            detail_text = _fetch_detail(api_key, item.get("recrutPblntSn"))
            raw_text = _build_raw_text(item, detail_text=detail_text)
            records.append(
                make_record(
                    source=SOURCE,
                    posting_url=_posting_url(item),
                    raw_text=raw_text,
                )
            )
            if ENABLE_DETAIL:
                polite_sleep(SLEEP_SEC)

        if total_count is not None and page * PAGE_SIZE >= total_count:
            break
        if len(items) < PAGE_SIZE:
            break
        page += 1
        polite_sleep(SLEEP_SEC)

    print(
        f"[alio] 수집 {len(records)}건 / 경영 직군 추정 {biz_count}건 "
        f"({(biz_count / len(records) * 100) if records else 0:.1f}%)",
        file=sys.stderr,
    )
    return records


if __name__ == "__main__":
    rs = fetch()
    print(f"records={len(rs)}")
    if rs:
        print(rs[0]["raw_text"][:400])
