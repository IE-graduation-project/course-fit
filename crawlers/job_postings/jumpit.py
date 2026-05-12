"""점핏 (jumpit.saramin.co.kr) 채용공고 fetcher.

robots.txt 기준 `/position/{id}` 는 명시적으로 허용 (Disallow 미해당).
사이트는 Next.js App Router SPA 라 정적 HTML 파싱 불가 — 대신
- 목록: 공식 sitemap (`sitemap/sitemap_position_view_1.xml`) 으로 전체 position id 수집
- 상세: 내부 JSON endpoint `https://jumpit.saramin.co.kr/api/position/{id}` 호출
  (브라우저가 동일 endpoint 로 fetch 하는 것을 모방, 무인증)

데이터/ML 직군 위주: `jobCategories[].name` 매칭으로 우선 추출, 부족하면 전체로 fallback.

본 모듈은 학술 PoC 목적이며 batch 당 최대 100건 한정.
"""
from __future__ import annotations

import re
import sys
from typing import Any
from xml.etree import ElementTree as ET

from crawlers.job_postings._common import (
    http_get,
    make_record,
    polite_sleep,
)


SITEMAP_URL = "https://jumpit.saramin.co.kr/sitemap/sitemap_position_view_1.xml"
DETAIL_API = "https://jumpit.saramin.co.kr/api/position/{pid}"
POSITION_URL = "https://jumpit.saramin.co.kr/position/{pid}"

SOURCE = "Jumpit"
MAX_POSITIONS = 100
# robots 허용이지만 사람인 자회사라 매너 우선: 다른 사이트보다 느슨한 2초 간격.
JUMPIT_INTERVAL_SEC = 2.0
MIN_RAW_TEXT_LEN = 80

# 데이터/ML 직군 식별 키워드 (jobCategories[].name 또는 title 매칭).
# 점핏 자체 분류명 + 흔한 변형 모두 포괄.
DATA_ML_KEYWORDS: tuple[str, ...] = (
    "데이터",        # 데이터 분석가, 데이터 엔지니어, 데이터 사이언티스트
    "사이언티스트",   # 데이터 사이언티스트
    "머신러닝",
    "딥러닝",
    "AI",
    "ML",
    "BI",
    "Data",
    "MLOps",
    "Machine Learning",
    "Analytics",
)


def _parse_sitemap_positions(xml_text: str) -> list[str]:
    """sitemap XML → ['53835323', ...] (lastmod 정렬 그대로 = 최신순)."""
    # ElementTree 가 namespace 를 자동 prefix 처리하지 않게 정규식으로 직접 추출.
    # (sitemap XML 은 단순 `<url><loc>...</loc></url>` 구조라 안전.)
    locs = re.findall(
        r"<loc>https://jumpit\.saramin\.co\.kr/position/(\d+)</loc>",
        xml_text,
    )
    # lxml/ET fallback (정규식이 0건일 때만)
    if not locs:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc_el in root.findall(".//sm:url/sm:loc", ns):
            text = (loc_el.text or "").strip()
            m = re.search(r"/position/(\d+)$", text)
            if m:
                locs.append(m.group(1))
    # 중복 제거하되 순서 보존
    seen: set[str] = set()
    uniq: list[str] = []
    for pid in locs:
        if pid not in seen:
            seen.add(pid)
            uniq.append(pid)
    return uniq


def _fetch_position(pid: str) -> dict | None:
    """단일 position JSON 조회. 비공개/만료 등은 None 반환."""
    try:
        resp = http_get(
            DETAIL_API.format(pid=pid),
            headers={"Accept": "application/json"},
        )
    except Exception as exc:  # noqa: BLE001 — 공고 단위 격리
        print(f"[jumpit] {pid} HTTP 실패: {exc}", file=sys.stderr)
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("status") and payload.get("status") != 200:
        return None
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    return result


def _category_names(result: dict) -> list[str]:
    cats = result.get("jobCategories") or []
    out: list[str] = []
    for c in cats:
        if isinstance(c, dict):
            name = c.get("name")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return out


def _is_data_ml(result: dict) -> bool:
    haystack_parts: list[str] = []
    haystack_parts.extend(_category_names(result))
    title = result.get("title")
    if isinstance(title, str):
        haystack_parts.append(title)
    haystack = " ".join(haystack_parts).lower()
    return any(kw.lower() in haystack for kw in DATA_ML_KEYWORDS)


def _tech_stack_names(result: dict) -> list[str]:
    stacks = result.get("techStacks") or []
    out: list[str] = []
    for s in stacks:
        if isinstance(s, dict):
            name = s.get("stack")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return out


def _build_raw_text(result: dict) -> str:
    """title + 회사명 + 직무 카테고리 + 기술스택 + 본문 → 한국어 평문."""
    title = (result.get("title") or "").strip()
    company = (result.get("companyName") or "").strip()
    categories = ", ".join(_category_names(result))
    stacks = ", ".join(_tech_stack_names(result))
    location = (result.get("location") or "").strip()

    header_lines: list[str] = []
    if title or company:
        header_lines.append(f"[{company}] {title}".strip())
    if categories:
        header_lines.append(f"직무 카테고리: {categories}")
    if stacks:
        header_lines.append(f"기술스택: {stacks}")
    if location:
        header_lines.append(f"근무지: {location}")
    header = "\n".join(ln for ln in header_lines if ln)

    # 본문 섹션 (점핏 JSON 키 — HTML 아닌 평문/줄바꿈 포함 텍스트)
    sections: list[tuple[str, str]] = [
        ("주요업무", (result.get("responsibility") or "").strip()),
        ("자격요건", (result.get("qualifications") or "").strip()),
        ("우대사항", (result.get("preferredRequirements") or "").strip()),
        ("복지/혜택", (result.get("welfares") or "").strip()),
        ("회사 소개", (result.get("serviceInfo") or "").strip()),
    ]
    body_parts: list[str] = []
    for label, content in sections:
        if content:
            # 점핏 본문은 \r\n 혼재 → 정규화
            normalized = content.replace("\r\n", "\n").replace("\r", "\n")
            # 연속 빈 줄 축약
            normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
            body_parts.append(f"[{label}]\n{normalized}")
    body = "\n\n".join(body_parts)

    combined = f"{header}\n\n{body}".strip() if body else header
    return combined


def fetch() -> list[dict]:
    """점핏 데이터/ML 직군 위주 최대 MAX_POSITIONS 건 수집."""
    # 1. sitemap 으로 전체 position id 수집 (최신순 = 파일 앞쪽)
    try:
        resp = http_get(SITEMAP_URL, headers={"Accept": "application/xml"})
    except Exception as exc:  # noqa: BLE001
        print(f"[jumpit] sitemap 실패: {exc}", file=sys.stderr)
        return []
    pids = _parse_sitemap_positions(resp.text)
    if not pids:
        print("[jumpit] sitemap 에서 position id 0건", file=sys.stderr)
        return []
    print(f"[jumpit] sitemap: {len(pids)} positions", file=sys.stderr)

    polite_sleep(JUMPIT_INTERVAL_SEC)

    # 2. 데이터/ML 우선 / 일반 fallback 두 버킷으로 분리해 가며 100건 채움.
    #    sitemap 순회는 lastmod 최신순이므로 신선도 우선 자연 충족.
    #    상한선: 후보 탐색에 너무 많이 호출하지 않도록 sitemap 의 앞쪽 일부만 본다.
    SCAN_LIMIT = min(len(pids), MAX_POSITIONS * 4)

    primary: list[dict] = []   # 데이터/ML 매칭
    secondary: list[dict] = [] # fallback 일반

    for idx, pid in enumerate(pids[:SCAN_LIMIT]):
        if len(primary) >= MAX_POSITIONS:
            break
        result = _fetch_position(pid)
        polite_sleep(JUMPIT_INTERVAL_SEC)
        if result is None:
            continue
        raw_text = _build_raw_text(result)
        if len(raw_text) < MIN_RAW_TEXT_LEN:
            continue
        rec = make_record(
            source=SOURCE,
            posting_url=POSITION_URL.format(pid=pid),
            raw_text=raw_text,
        )
        if _is_data_ml(result):
            primary.append(rec)
        elif len(secondary) < MAX_POSITIONS:
            secondary.append(rec)

        if (idx + 1) % 20 == 0:
            print(
                f"[jumpit] scan {idx + 1}/{SCAN_LIMIT} | "
                f"data/ML {len(primary)} | other {len(secondary)}",
                file=sys.stderr,
            )

    # 3. 데이터/ML 우선, 부족하면 일반으로 채움. 총 MAX_POSITIONS 한정.
    records = primary[:MAX_POSITIONS]
    if len(records) < MAX_POSITIONS:
        records.extend(secondary[: MAX_POSITIONS - len(records)])

    print(
        f"[jumpit] 최종: {len(records)} (data/ML {len(primary)} + "
        f"fallback {len(records) - min(len(primary), MAX_POSITIONS)})",
        file=sys.stderr,
    )
    return records


if __name__ == "__main__":
    recs = fetch()
    print(f"records: {len(recs)}")
    if recs:
        print("--- sample[0] raw_text[:400] ---")
        print(recs[0]["raw_text"][:400])
